"""Módulo LGPD — responsável: Luiza (Eixo 2). Varredura de dados pessoais (US11/US12) e triagem.

Pipeline de uma varredura (um recurso por vez):
    1. baixa o arquivo do recurso pelo cliente CKAN (PBI-32); CSV e XLSX (`leitura.py`)
    2. motor do detector3 (`deteccao.py`), coluna a coluna, em blocos de 50 mil linhas:
       regras determinísticas (CPF/CNPJ com dígito verificador, e-mail, telefone, CEP) +
       endereço pelo modelo LOCAL (tarefa `classificacao_dp`), com o filtro semântico
       (tarefa `embeddings_dp`) escolhendo quais células vão ao modelo
    3. um achado por (recurso, coluna, tipo), com score e prioridade (PBI-86, PBI-36)
    4. grava só local e tipo — nunca o valor (PBI-35); decisão já tomada é preservada (PBI-41)

Falha do modelo local para a varredura com erro (nada é gravado pela metade). Etapa sem modelo
configurado é pulada com AVISO registrado na varredura — nunca em silêncio.

A fila fica no banco (`lgpd_varredura` com status `pendente`): a API só enfileira e o worker é o
único executor (`job_executar_fila`, a cada minuto — ADR-0025), o que sobrevive a reinícios.
"""
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import SessionLocal, utcnow
from app.core.deps import UsuarioAtual, exigir_mesmo_orgao
from app.integrations.ai.base import AIProviderError, ChatMessage, ChatRequest
from app.integrations.ai.policy import TarefaIA
from app.integrations.ckan.client import CkanClient, CkanError
from app.modules.ia.gateway import AIGateway, IANaoConfigurada
from app.modules.inventario.models import Dataset, Organizacao, Recurso
from app.modules.inventario.service import recursos_atuais
from app.modules.lgpd import deteccao, leitura, regras
from app.modules.lgpd.dao import LgpdDao
from app.modules.lgpd.models import Achado, DecisaoTriagem, Varredura
from app.modules.lgpd.schemas import (
    AchadoDetalheOut,
    AchadoOut,
    AchadosOut,
    DecisaoIn,
    DecisaoOut,
    KpisOut,
    OpcaoOut,
    OpcoesAchadosOut,
    PedidoVarreduraOut,
    VarreduraOut,
    VarredurasOut,
)
from app.modules.parametros.router import obter as obter_parametro

log = logging.getLogger(__name__)

INTERROMPIDA = "Varredura interrompida: o worker foi reiniciado durante a execução."
RETOMADAS_POR_RECURSO = 1  # um arquivo que derruba o processo não pode prender a fila em laço


class ErroLgpd(Exception):
    pass


class NaoEncontrado(ErroLgpd):
    pass


class Invalido(ErroLgpd):
    pass


# ------------------------------------------------------------------ achados (tela)
def _achado_out(a: Achado, r: Recurso, ds: Dataset, orgaos: dict[int, Organizacao]) -> AchadoOut:
    org = orgaos.get(ds.organizacao_id) if ds.organizacao_id is not None else None
    return AchadoOut(
        id=a.id, prioridade=a.prioridade, orgao_id=ds.organizacao_id,
        orgao_sigla=(org.sigla if org else None), orgao_nome=(org.titulo.strip() if org else None),
        dataset_id=ds.id, dataset_titulo=ds.titulo.strip(), recurso_id=r.id,
        recurso_nome=r.nome, tipo=a.tipo, tipo_rotulo=regras.rotulo_tipo(a.tipo), coluna=a.coluna,
        linha=a.linha, ocorrencias=a.ocorrencias, confianca=a.confianca, metodo=a.metodo,
        status=a.status, atualizado_em=a.changed)


def _kpis(dao: LgpdDao, user: UsuarioAtual, linhas: list[AchadoOut]) -> KpisOut:
    return KpisOut(
        recursos_analisados=dao.recursos_analisados(user),
        recursos_com_achados=len({a.recurso_id for a in linhas if a.status != "falso_positivo"}),
        alertas_criticos=sum(1 for a in linhas
                             if a.prioridade == regras.ALTA and a.status == "revisar"),
        alertas_para_revisao=sum(1 for a in linhas if a.status == "revisar"))


def listar_achados(db: Session, user: UsuarioAtual, *, prioridade: str | None = None,
                   tipo: str | None = None, orgao: str | None = None,
                   status: str | None = None) -> AchadosOut:
    """Tela Riscos de Dados Pessoais: KPIs, opções dos filtros e achados ordenados por prioridade
    e confiança. Filtros: prioridade (Alta|Média|Baixa), tipo (código), órgão (ID), status."""
    dao = LgpdDao.de(db, user)
    orgaos = dao.organizacoes()
    todas = [_achado_out(a, r, ds, orgaos) for a, r, ds in dao.achados_visiveis(user)]
    ordem = {p: i for i, p in enumerate(regras.PRIORIDADES)}
    todas.sort(key=lambda a: (ordem.get(a.prioridade, 9), -a.confianca, a.dataset_titulo, a.id))
    filtradas = [a for a in todas
                 if (not prioridade or a.prioridade == prioridade)
                 and (not tipo or a.tipo == tipo)
                 and (not orgao or str(a.orgao_id) == orgao)
                 and (not status or a.status == status)]
    presentes_org = {a.orgao_id for a in todas if a.orgao_id}
    opcoes = OpcoesAchadosOut(
        prioridades=list(regras.PRIORIDADES),
        tipos=[OpcaoOut(valor=t, rotulo=regras.rotulo_tipo(t))
               for t in sorted({a.tipo for a in todas}, key=regras.rotulo_tipo)],
        orgaos=sorted((OpcaoOut(valor=str(i), rotulo=(orgaos[i].sigla or orgaos[i].titulo).strip())
                       for i in presentes_org if i in orgaos), key=lambda o: o.rotulo.lower()),
        status=[OpcaoOut(valor=k, rotulo=v) for k, v in regras.STATUS.items()])
    return AchadosOut(kpis=_kpis(dao, user, todas), opcoes=opcoes, total=len(todas),
                      achados=filtradas)


def obter_achado(db: Session, achado_id: int, user: UsuarioAtual) -> AchadoDetalheOut:
    dao = LgpdDao.de(db, user)
    linha = dao.achado_visivel(achado_id, user)
    if linha is None:
        raise NaoEncontrado("Achado não encontrado.")
    a, r, ds = linha
    decisoes = dao.decisoes(a.id)
    return AchadoDetalheOut(
        **_achado_out(a, r, ds, dao.organizacoes()).model_dump(), explicacao=a.explicacao,
        recurso_url=r.url, recurso_formato=r.formato,
        decisoes=[DecisaoOut(decisao=d.decisao, justificativa=d.justificativa, usuario=d.usuario,
                             momento=d.momento) for d in decisoes])


def decidir(db: Session, achado_id: int, dados: DecisaoIn, user: UsuarioAtual) -> AchadoDetalheOut:
    """PBI-40/42 — decisão humana: muda o status e grava no histórico imutável (`lgpd_decisao`)."""
    dao = LgpdDao.de(db, user)
    linha = dao.achado_visivel(achado_id, user)
    if linha is None:
        raise NaoEncontrado("Achado não encontrado.")
    a, _r, ds = linha
    exigir_mesmo_orgao(user, ds.organizacao_id)
    justificativa = (dados.justificativa or "").strip() or None
    a.status = dados.decisao
    dao.save_generic(DecisaoTriagem(achado_id=a.id, decisao=dados.decisao,
                                    justificativa=justificativa, usuario=user.email,
                                    momento=utcnow()), a)
    dao.commit()
    return obter_achado(db, a.id, user)


# ------------------------------------------------------------------ varreduras
def _varredura_out(v: Varredura, r: Recurso | None, ds: Dataset | None) -> VarreduraOut:
    return VarreduraOut(
        id=v.id, recurso_id=v.recurso_id, recurso_nome=r.nome if r else None,
        dataset_titulo=ds.titulo.strip() if ds else None, status=v.status, origem=v.origem,
        solicitada_por=v.solicitada_por, solicitada_em=v.solicitada_em, iniciada_em=v.iniciada_em,
        finalizada_em=v.finalizada_em, linhas_analisadas=v.linhas_analisadas,
        chamadas_ia=v.chamadas_ia, achados=v.achados, modelo=v.modelo, aviso=v.aviso, erro=v.erro)


def listar_varreduras(db: Session, user: UsuarioAtual, limite: int = 30) -> VarredurasOut:
    dao = LgpdDao.de(db, user)
    linhas = dao.varreduras(user, min(limite, 200))
    return VarredurasOut(em_andamento=dao.varreduras_em_andamento(user),
                         varreduras=[_varredura_out(v, r, ds) for v, r, ds in linhas])


def _varrivel(r: Recurso) -> bool:
    return (not r.eh_dicionario_dados and bool(r.url)
            and leitura.formato_do_recurso(r.formato, r.url) in leitura.FORMATOS_SUPORTADOS)


def _utc(d: datetime | None) -> datetime | None:
    return d.replace(tzinfo=UTC) if d is not None and d.tzinfo is None else d


def recursos_do_escopo(db: Session, escopo: str, alvo: int | None, user: UsuarioAtual | None,
                       limite: int | None = None) -> list[Recurso]:
    """Recursos que a varredura vai ler. `pendentes` = CSV/XLSX de datasets ativos nunca varridos
    ou modificados (last_modified) depois da última varredura; `dataset` = todos os recursos
    atuais do dataset (os de formato não suportado ficam registrados como ignorados);
    `recurso` = um recurso."""
    dao = LgpdDao(db)
    if escopo == "recurso":
        par = dao.recurso_e_dataset(alvo or 0, user)
        r, ds = par if par else (None, None)
        if r is None or not ds.ativo_no_portal or r not in recursos_atuais(ds):
            raise NaoEncontrado("Recurso não encontrado entre os recursos atuais do portal.")
        return [r]
    if escopo == "dataset":
        dss = dao.datasets_ativos(user, alvo or 0)
        if not dss:
            raise NaoEncontrado("Dataset não encontrado ou fora do portal.")
        return [r for r in recursos_atuais(dss[0]) if not r.eh_dicionario_dados and r.url]
    if escopo != "pendentes":
        raise Invalido("Escopo inválido.")
    ultima = dao.ultima_varredura_concluida()
    saida = []
    for ds in dao.datasets_ativos(user):
        for r in recursos_atuais(ds):
            if not _varrivel(r):
                continue
            feita = _utc(ultima.get(r.id))
            mudou = _utc(r.last_modified or r.created_ckan)
            if feita is None or (mudou is not None and mudou > feita):
                saida.append(r)
    saida.sort(key=lambda r: r.id)
    return saida[:limite] if limite else saida


def solicitar(db: Session, escopo: str, alvo: int | None, user: UsuarioAtual | None,
              origem: str = "manual", limite: int | None = None) -> tuple[list[Varredura], int]:
    """Cria varreduras `pendente` para o escopo; o worker as executa (ADR-0025). Recurso que já
    está na fila não é duplicado. Devolve (criadas, quantas já estavam na fila)."""
    dao = LgpdDao.de(db, user)
    recursos = recursos_do_escopo(db, escopo, alvo, user, limite)
    na_fila = {v.recurso_id for v in dao.em_fila()}
    criadas = [Varredura(recurso_id=r.id, origem=origem,
                         solicitada_por=user.email if user else None)
               for r in recursos if r.id not in na_fila]
    if criadas:
        dao.save_generic(*criadas)
    dao.commit()
    return criadas, len(recursos) - len(criadas)


def pedido_out(db: Session, criadas: list[Varredura], ja_na_fila: int) -> PedidoVarreduraOut:
    dao = LgpdDao(db)
    out = []
    for v in criadas:
        r = dao.recurso(v.recurso_id)
        out.append(_varredura_out(v, r, dao.dataset(r.dataset_id) if r else None))
    return PedidoVarreduraOut(criadas=len(criadas), ja_na_fila=ja_na_fila, varreduras=out)


# ------------------------------------------------------------------ execução
@dataclass
class _Motor:
    analisador: deteccao.Analisador
    avisos: list[str]
    modelos: str | None

    def chamadas_ia(self) -> int:
        rec = self.analisador.reconhecedores.get("EnderecoLLMReconhecedor")
        return rec.stats["chamadas"] if rec else 0


def _modelo_da_tarefa(db: Session, tarefa: TarefaIA) -> str | None:
    return LgpdDao(db).modelo_da_tarefa(tarefa.value)


def montar_motor(db: Session) -> _Motor:
    """Analisador do detector3 com as funções de IA ligadas ao gateway (modelo LOCAL, política
    das tarefas sensíveis). Etapas sem modelo configurado são puladas com aviso."""
    limiar = int(obter_parametro(db, "confianca_minima_lgpd")) / 100
    g = AIGateway(db)
    avisos: list[str] = []
    modelos: list[str] = []
    chat_fn = filtro = None
    modelo_chat = _modelo_da_tarefa(db, TarefaIA.CLASSIFICACAO_DADO_PESSOAL)

    if g.configurada(TarefaIA.CLASSIFICACAO_DADO_PESSOAL):
        def chat_fn(prompt: str) -> str:
            resp, _p, _fb = g.chat(TarefaIA.CLASSIFICACAO_DADO_PESSOAL, ChatRequest(
                messages=[ChatMessage(role="user", content=prompt)], json_mode=True,
                temperature=0, max_tokens=300))
            return resp.text
        modelos.append(modelo_chat or "modelo local")
    else:
        avisos.append("Endereço não verificado: nenhum modelo local vinculado à tarefa "
                      "'Classificação de dados pessoais' (Administração › Modelos de IA).")

    if chat_fn and g.configurada(TarefaIA.EMBEDDINGS_DADO_PESSOAL):
        def embed_fn(textos: list[str]) -> list[list[float]]:
            return g.embed(TarefaIA.EMBEDDINGS_DADO_PESSOAL, textos)[0].vectors
        filtro = deteccao.FiltroEmbeddings(
            embed_fn, margem=float(obter_parametro(db, "margem_embeddings_lgpd")))
        modelos.append(_modelo_da_tarefa(db, TarefaIA.EMBEDDINGS_DADO_PESSOAL) or "embeddings")
    elif chat_fn:
        avisos.append("Filtro semântico não configurado (tarefa 'Filtro semântico da varredura "
                      "LGPD'): só valores atípicos das colunas foram enviados ao modelo de "
                      "endereço.")
    analisador = deteccao.montar_analisador(limiar, chat_fn, filtro,
                                            nome_modelo=modelo_chat or "modelo local")
    return _Motor(analisador, avisos, " + ".join(modelos) or None)


def _gravar_achados(dao: LgpdDao, recurso_id: int, agregados: list[regras.AchadoColuna]) -> int:
    """Upsert pela impressão digital: achado já existente mantém o status e o histórico (PBI-41);
    achado que sumiu do arquivo e ainda não foi avaliado por ninguém é excluído (logicamente)."""
    existentes = {a.impressao_digital: a for a in dao.achados_do_recurso(recurso_id)}
    vistos = set()
    for ag in agregados:
        dig = regras.impressao_digital(recurso_id, ag.coluna, ag.tipo)
        vistos.add(dig)
        a = existentes.get(dig) or Achado(recurso_id=recurso_id, coluna=ag.coluna, tipo=ag.tipo,
                                          impressao_digital=dig, status="revisar")
        a.linha, a.ocorrencias, a.confianca = ag.linha, ag.ocorrencias, ag.confianca
        a.metodo, a.explicacao = ag.metodo, ag.explicacao
        a.prioridade = regras.prioridade(ag.tipo, ag.confianca)
        dao.save_generic(a)
    avaliados = dao.achados_com_decisao([a.id for a in existentes.values()])
    for dig, a in existentes.items():
        if dig not in vistos and a.status == "revisar" and a.id not in avaliados:
            dao.delete_generic(a)
    return len(agregados)


def _finalizar(dao: LgpdDao, v: Varredura, status: str, **campos) -> None:
    v.status, v.finalizada_em = status, utcnow()
    for k, val in campos.items():
        setattr(v, k, val)
    dao.save_generic(v)
    dao.commit()


def _explicar_download(exc: CkanError, r: Recurso) -> str:
    """Mensagem para a GEDA: link quebrado é um achado em si (o órgão precisa corrigir)."""
    onde = ("arquivo enviado ao portal" if r.url_type == "upload"
            else "link do recurso (arquivo hospedado fora do portal ou importado só como link)")
    if exc.status_http == 404:
        return f"Arquivo não encontrado (HTTP 404) no {onde}: link quebrado. {exc}"
    if exc.status_http in (401, 403):
        return f"Acesso negado (HTTP {exc.status_http}) ao baixar pelo {onde}. {exc}"
    return str(exc)


def cancelar_fila(db: Session, user: UsuarioAtual) -> int:
    """Cancela as varreduras que ainda não começaram (a que está rodando termina normalmente)."""
    dao = LgpdDao.de(db, user)
    pendentes = dao.pendentes_do_escopo(user)
    for v in pendentes:
        v.status, v.finalizada_em = "cancelada", utcnow()
        v.aviso = f"Cancelada por {user.email} antes de começar."
    if pendentes:
        dao.save_generic(*pendentes)
    dao.commit()
    return len(pendentes)


def executar_varredura(db: Session, v: Varredura, client: CkanClient | None = None) -> None:
    """Executa UMA varredura e grava o resultado. Nunca levanta: erro fica no registro."""
    dao = LgpdDao(db)
    v.status, v.iniciada_em = "executando", utcnow()
    dao.save_generic(v)
    dao.commit()
    r = dao.recurso(v.recurso_id)
    ds = dao.dataset(r.dataset_id)
    formato = leitura.formato_do_recurso(r.formato, r.nome or r.url)
    if formato not in leitura.FORMATOS_SUPORTADOS:
        return _finalizar(dao, v, "ignorado", aviso=(
            f"Formato {formato or 'desconhecido'} ainda não é varrido (suportados: "
            f"{', '.join(sorted(leitura.FORMATOS_SUPORTADOS))})."))
    limite_mb = int(obter_parametro(db, "tamanho_maximo_recurso_lgpd_mb"))
    proprio = client is None
    client = client or CkanClient()
    try:
        url = client.url_download(r.id_ckan, ds.id_ckan if ds else None, r.url, r.url_type)
        if not url:
            return _finalizar(dao, v, "ignorado", aviso="Recurso sem URL de arquivo.")
        conteudo = client.baixar(url, limite_mb * 1024 * 1024)
        tabelas = leitura.ler(conteudo, formato)
        del conteudo
        motor = montar_motor(db)
        tipos_ativos = {str(t).strip().lower()
                        for t in obter_parametro(db, "tipos_dado_pessoal") or []}
        por_coluna: dict[str, dict[str, regras.AchadoColuna]] = {}
        cache: dict = {}
        linhas = 0
        for tab in tabelas:
            for bloco in tab.blocos:
                linhas += len(bloco)
                for i, col in enumerate(tab.colunas):
                    nome = regras.nome_da_coluna(tab.nome, col)
                    celulas = deteccao.analisar_coluna(
                        motor.analisador, [(n, valores[i]) for n, valores in bloco],
                        cache=cache, chave_coluna=nome)
                    por_coluna[nome] = regras.agregar(nome, celulas, tipos_ativos,
                                                      por_coluna.get(nome))
        agregados = [a for col in por_coluna.values() for a in col.values()]
        n = _gravar_achados(dao, r.id, agregados)
        _finalizar(dao, v, "ok", linhas_analisadas=linhas, chamadas_ia=motor.chamadas_ia(),
                   achados=n, modelo=motor.modelos, aviso="\n".join(motor.avisos) or None)
    except leitura.FormatoNaoSuportado as exc:
        dao.rollback()
        _finalizar(dao, v, "ignorado", aviso=str(exc)[:2000])
    except CkanError as exc:
        dao.rollback()
        _finalizar(dao, v, "erro", erro=_explicar_download(exc, r)[:2000])
    except leitura.ArquivoInvalido as exc:
        dao.rollback()
        _finalizar(dao, v, "erro", erro=str(exc)[:2000])
    except (AIProviderError, IANaoConfigurada) as exc:
        dao.rollback()
        _finalizar(dao, v, "erro", erro=f"Modelo local indisponível; varredura interrompida sem "
                                       f"gravar resultados. {exc}"[:2000])
    except Exception as exc:  # registro do erro sem derrubar a fila (o log tem o traceback)
        log.exception("Varredura %s falhou", v.id)
        dao.rollback()
        _finalizar(dao, v, "erro", erro=f"Erro inesperado: {type(exc).__name__}: {exc}"[:2000])
    finally:
        if proprio:
            client.close()


def _retomar_interrompidas(dao: LgpdDao) -> None:
    """O worker é o único executor e um ciclo nunca roda junto de outro: varredura ainda em
    `executando` no início do ciclo é de um processo que caiu. Ela vira erro e o recurso volta
    à fila — uma vez só; se já tinha sido interrompido antes, fica o erro."""
    for v in dao.executando():
        retomadas = dao.interrupcoes_do_recurso(v.recurso_id, INTERROMPIDA)
        v.status, v.finalizada_em, v.erro = "erro", utcnow(), INTERROMPIDA
        dao.save_generic(v)
        if retomadas < RETOMADAS_POR_RECURSO:
            dao.save_generic(Varredura(recurso_id=v.recurso_id, origem=v.origem,
                                       solicitada_por=v.solicitada_por))
        log.warning("Varredura %s interrompida; recurso %s %s", v.id, v.recurso_id,
                    "de volta à fila" if retomadas < RETOMADAS_POR_RECURSO else "não volta à fila")
    dao.commit()


def job_executar_fila() -> None:
    """ADR-0025 — job do worker (a cada minuto): retoma as interrompidas e executa as pendentes,
    a mais antiga primeiro, até a fila esvaziar; pedidos feitos no meio entram no mesmo ciclo."""
    feitas = 0
    with SessionLocal() as db:
        dao = LgpdDao(db)
        _retomar_interrompidas(dao)
        while (v := dao.proxima_pendente()) is not None:
            executar_varredura(db, v)
            feitas += 1
    if feitas:
        log.info("Fila LGPD: %s varredura(s) executada(s)", feitas)


def job_varredura_incremental() -> None:
    """PBI-34 — depois da coleta: enfileira recursos novos ou alterados, até o limite configurado
    (o job da fila os executa)."""
    with SessionLocal() as db:
        criadas, _ = solicitar(db, "pendentes", None, None, origem="agendada",
                               limite=get_settings().lgpd_varredura_max_recursos)
    log.info("Varredura LGPD agendada: %s recurso(s) na fila", len(criadas))


# ------------------------------------------------------------------ apoio legado (ADR-0010)
@dataclass
class AmostraColuna:
    nome: str
    valores: list[str]  # poucas linhas (ex.: 10); nunca persistidas


@dataclass
class ClassificacaoColuna:
    coluna: str
    tipo: str | None     # None = não é dado pessoal
    confianca: int


_PROMPT = (
    "Você classifica colunas de planilhas publicadas em portal de dados abertos. Para cada coluna, "
    "diga se contém dado pessoal de pessoa física identificável. Tipos: nome, endereco, "
    "data_nascimento, outro_pessoal, ou null. Responda APENAS JSON no formato "
    '{"colunas":[{"coluna":"...","tipo":"nome|endereco|data_nascimento|outro_pessoal|null",'
    '"confianca":0-100}]}'
)


def classificar_colunas_ambiguas(db: Session, colunas: list[AmostraColuna]) -> list[ClassificacaoColuna]:
    """Classificação por COLUNA (nome + amostra). Não é usada pela varredura, que segue o detector3
    célula a célula; fica disponível para tipos sem regra (nome, data de nascimento)."""
    if not colunas:
        return []
    corpo = [{"coluna": c.nome, "amostra": c.valores[:10]} for c in colunas]
    resp, _perfil, _fb = AIGateway(db).chat(TarefaIA.CLASSIFICACAO_DADO_PESSOAL, ChatRequest(
        messages=[ChatMessage(role="system", content=_PROMPT),
                  ChatMessage(role="user", content=json.dumps(corpo, ensure_ascii=False))],
        json_mode=True, temperature=0,
    ))
    try:
        itens = json.loads(resp.text).get("colunas", [])
    except (json.JSONDecodeError, AttributeError):
        return []  # resposta inválida → nenhuma classificação (a regra determinística prevalece)
    return [ClassificacaoColuna(coluna=i.get("coluna", ""),
                                tipo=None if i.get("tipo") in (None, "null") else i["tipo"],
                                confianca=int(i.get("confianca", 0))) for i in itens]
