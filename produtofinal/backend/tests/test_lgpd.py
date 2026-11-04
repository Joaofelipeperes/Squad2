"""Varredura LGPD (motor do detector3) e tela Riscos de Dados Pessoais — dados fictícios, sem rede."""
import io
import json
from datetime import UTC, datetime

import httpx
import pytest
from openpyxl import Workbook

from app.core.db import SessionLocal
from app.integrations.ai.providers import ollama
from app.integrations.ckan.client import CkanClient
from app.modules.inventario.models import Coleta, Dataset, Recurso
from app.modules.lgpd import deteccao, leitura, regras, service
from app.modules.lgpd.models import Achado, DecisaoTriagem, Varredura
from app.modules.parametros.models import Parametro

SEDUC = 1                            # organização criada no conftest
DS, REC_CSV, REC_PDF = 10, 11, 12    # `id` próprios (o ID do CKAN fica em `id_ckan`)


def cpf(base: str) -> str:
    d = [int(c) for c in base]
    for n in (9, 10):
        d.append(sum(d[i] * (n + 1 - i) for i in range(n)) * 10 % 11 % 10)
    s = "".join(map(str, d))
    return f"{s[:3]}.{s[3:6]}.{s[6:9]}-{s[9:]}"


CPF_A, CPF_B = cpf("529982247"), cpf("111444777")
ESCOLAS = ["Escola Estadual Lyceu", "Colégio Militar Hugo", "Instituto Basileu França",
           "Escola Estadual Pedro Gomes", "CEPI Jardim América"]


def csv_alunos() -> bytes:
    linhas = ["nome;cpf;contato;escola;observacao"]
    for i in range(30):
        obs = "mora perto do shopping Flamboyant" if i == 7 else "faltou à aula"
        escola = "62998765432" if i == 12 else ESCOLAS[i % 5]  # telefone fora do lugar
        doc = CPF_A if i % 2 == 0 else CPF_B
        linhas.append(f"Aluno {i};{doc};aluno{i}@email.com;{escola};{obs}")
    return "\n".join(linhas).encode("latin-1")


# ------------------------------------------------------------------ motor e regras puras
def test_motor_igual_ao_detector3():
    a = deteccao.montar_analisador(0.5)
    r = a.analisar(f"CPF {CPF_A} e cel (62) 99876-5432")
    assert [(x.tipo, x.score) for x in r] == [("CPF", 1.0), ("TELEFONE", 1.0)]
    assert a.analisar("2024-2025") == [] and a.analisar("111.111.111-11") == []
    # coluna de códigos de 11 dígitos: CPF "válido por acaso" é descartado
    codigos = [(i, f"{10000000000 + i * 7919}") for i in range(200)]
    achados = deteccao.analisar_coluna(a, codigos)
    assert all(r.tipo != "CPF" for _, _, _, rs in achados for r in rs)


def test_endereco_pelo_modelo_com_filtro_semantico():
    def embed(textos):  # "endereço" = 1º eixo; demais = 2º eixo
        return [[1.0, 0.0] if any(k in t.lower() for k in ("mora", "rua", "casa", "qd", "fica"))
                else [0.0, 1.0] for t in textos]

    perguntas = []

    def chat(prompt):
        perguntas.append(prompt)
        texto = prompt.rsplit('TEXTO: """', 1)[1].rstrip('"')
        if "lixo" in texto:
            return "não sei"
        return json.dumps({"endereco": "mora" in texto, "trecho": "perto do shopping"})

    filtro = deteccao.FiltroEmbeddings(embed, margem=0.1)
    a = deteccao.montar_analisador(0.6, chat, filtro, nome_modelo="qwen3:8b")
    valores = [(i + 2, "faltou à aula") for i in range(20)] + [(30, "mora perto do shopping")]
    achados = deteccao.analisar_coluna(a, valores)
    assert len(achados) == 1 and achados[0][0] == 30
    r = achados[0][3][0]
    assert r.tipo == "ENDERECO" and r.score == 0.85 and "confirmado por qwen3:8b" in r.explicacao
    assert len(perguntas) == 1                       # "faltou à aula" barrado pelo filtro
    assert "- faltou à aula" in perguntas[0]          # amostra da coluna vai no prompt
    erro = a.analisar("casa lixo")                   # resposta fora do formato → revisar
    assert erro[0].score == 0.6 and "REVISAR" in erro[0].explicacao[-1]


def test_leitura_csv_latin1_e_xlsx():
    (t,) = leitura.ler(b"a;a;;b\n1;2;3;4\n;;;\n5;6;7;8\n".decode().encode("latin-1"), "CSV")
    assert t.colunas == ["a (#1)", "a (#2)", "coluna (#3)", "b"]
    assert [n for bloco in t.blocos for n, _ in bloco] == [2, 4]   # linha vazia pulada
    wb = Workbook()
    ws = wb.active
    ws.title = "Alunos"
    ws.append([None])
    ws.append(["nome", "telefone"])
    ws.append(["Ana", 62998765432])
    wb.create_sheet("Vazia")
    buf = io.BytesIO()
    wb.save(buf)
    (x,) = leitura.ler(buf.getvalue(), "XLSX")
    assert x.colunas == ["nome", "telefone"]
    assert list(x.blocos) == [[(3, ["Ana", "62998765432"])]]
    with pytest.raises(leitura.FormatoNaoSuportado):
        leitura.ler(b"%PDF", "PDF")
    assert leitura.formato_do_recurso("", "http://x/arq.XLSX?d=1") == "XLSX"
    assert leitura.formato_do_recurso("text/csv", None) == "CSV"


def test_regras_de_prioridade_e_agregacao():
    assert regras.prioridade("cpf", 40) == "Alta"
    assert regras.prioridade("email", 96) == "Alta" and regras.prioridade("email", 75) == "Média"
    assert regras.prioridade("cnpj", 100) == "Média" and regras.prioridade("telefone", 55) == "Baixa"
    R = deteccao.Resultado
    celulas = [(5, "x", None, [R("CPF", 0, 1, 1.0, "CpfReconhecedor", ["forte"])]),
               (3, "y", None, [R("CPF", 0, 1, 1.0, "CpfReconhecedor", ["forte"]),
                               R("CEP", 2, 3, 0.85, "CepReconhecedor", ["cep"])])]
    ag = regras.agregar("doc", celulas, tipos_ativos={"cpf"})
    assert list(ag) == ["cpf"] and (ag["cpf"].linha, ag["cpf"].ocorrencias) == (3, 2)


# ------------------------------------------------------------------ varredura pela API
@pytest.fixture
def portal(monkeypatch):
    """Inventário com um CSV e um PDF; CKAN e Ollama simulados."""
    with SessionLocal() as db:
        c = Coleta(status="ok", finalizada_em=datetime.now(UTC))
        db.add(c)
        db.flush()
        db.add(Dataset(id=DS, id_ckan="ds-alunos", name="alunos", titulo="Alunos da Rede",
                       organizacao_id=SEDUC, ultima_coleta_id=c.id))
        db.add(Recurso(id=REC_CSV, id_ckan="rec-csv", dataset_id=DS, nome="alunos.csv", formato="CSV",
                       url="http://localhost:5000/dataset/ds-alunos/resource/rec-csv/download/alunos.csv",
                       url_type="upload", last_modified=datetime(2026, 9, 1, tzinfo=UTC),
                       ultima_coleta_id=c.id))
        db.add(Recurso(id=REC_PDF, id_ckan="rec-pdf", dataset_id=DS, nome="relatorio.pdf",
                       formato="PDF", url="http://outro.site/relatorio.pdf",
                       ultima_coleta_id=c.id))
        # o embedding falso só separa "mora"/"Rua" do resto: margem > 0 barra o empate
        db.add(Parametro(chave="margem_embeddings_lgpd", valor=0.1))
        db.commit()

    baixados = []

    def ckan(req: httpx.Request):
        baixados.append(str(req.url))
        return httpx.Response(200, content=csv_alunos())

    transporte = httpx.MockTransport(ckan)
    monkeypatch.setattr(service, "CkanClient",
                        lambda: CkanClient("http://ckan-interno:5000", transport=transporte))

    perguntas = []

    def ollama_falso(url, *, json, headers, timeout):
        if url.endswith("/api/embed"):
            return {"embeddings": [[1.0, 0.0] if "mora" in t or "Rua" in t else [0.0, 1.0]
                                   for t in json["input"]]}, 3
        texto = json["messages"][-1]["content"].rsplit('TEXTO: """', 1)[1]
        perguntas.append(texto)
        eh = "mora" in texto
        return {"message": {"content": __import__("json").dumps(
            {"endereco": eh, "trecho": "perto do shopping Flamboyant" if eh else ""})},
            "model": json["model"]}, 9

    monkeypatch.setattr(ollama, "post_json", ollama_falso)
    return {"baixados": baixados, "perguntas": perguntas}


def _configurar_ia(client, admin):
    def perfil(nome, modelo):
        return client.post("/api/v1/ia/perfis", headers=admin, json={
            "nome": nome, "tipo": "ollama", "modelo": modelo, "execucao_local": True}).json()["id"]
    client.put("/api/v1/ia/tarefas/classificacao_dp", headers=admin,
               json={"perfil_id": perfil("Qwen", "qwen2.5:7b-instruct")})
    client.put("/api/v1/ia/tarefas/embeddings_dp", headers=admin,
               json={"perfil_id": perfil("BGE", "bge-m3")})


def _varrer(client, headers, **pedido):
    """Pede pela API (só enfileira) e roda o ciclo do worker que executa a fila (ADR-0025)."""
    r = client.post("/api/v1/lgpd/varreduras", headers=headers, json=pedido)
    service.job_executar_fila()
    return r


def test_varredura_completa_triagem_e_reprocessamento(client, admin, gerente, portal):
    _configurar_ia(client, admin)
    r = _varrer(client, gerente, escopo="dataset", id=DS)
    assert r.status_code == 202 and r.json()["criadas"] == 2
    # o arquivo enviado ao CKAN é baixado pelo endereço interno, não pela URL pública
    assert portal["baixados"] == [
        "http://ckan-interno:5000/dataset/ds-alunos/resource/rec-csv/download/alunos.csv"]
    vs = {v["recurso_id"]: v for v in
          client.get("/api/v1/lgpd/varreduras", headers=gerente).json()["varreduras"]}
    assert vs[REC_PDF]["status"] == "ignorado" and "PDF" in vs[REC_PDF]["aviso"]
    v = vs[REC_CSV]
    assert v["status"] == "ok", v
    assert v["linhas_analisadas"] == 30 and v["aviso"] is None
    assert v["modelo"] == "qwen2.5:7b-instruct + bge-m3"
    assert v["chamadas_ia"] == 1  # só o endereço; o resto barrado pelo filtro (sem letras: regras)

    dados = client.get("/api/v1/lgpd/achados", headers=gerente).json()
    por_tipo = {(a["coluna"], a["tipo"]): a for a in dados["achados"]}
    # parâmetro padrão tipos_dado_pessoal: cpf, email, telefone, endereco (sem cnpj e cep)
    assert set(por_tipo) == {("cpf", "cpf"), ("contato", "email"), ("escola", "telefone"),
                             ("observacao", "endereco")}
    assert por_tipo[("cpf", "cpf")]["ocorrencias"] == 30 and por_tipo[("cpf", "cpf")]["linha"] == 2
    assert por_tipo[("cpf", "cpf")]["prioridade"] == "Alta"
    end = por_tipo[("observacao", "endereco")]
    assert (end["linha"], end["metodo"], end["confianca"]) == (9, "ia", 85)
    assert "atípico" in client.get(f"/api/v1/lgpd/achados/{por_tipo[('escola', 'telefone')]['id']}",
                                   headers=gerente).json()["explicacao"]
    assert dados["kpis"] == {"recursos_analisados": 1, "recursos_com_achados": 1,
                             "alertas_criticos": 2, "alertas_para_revisao": 4}

    # nenhum valor encontrado é gravado no banco (PBI-35)
    with SessionLocal() as db:
        gravado = " ".join(f"{a.coluna} {a.explicacao}" for a in db.query(Achado))
        gravado += " ".join(f"{x.aviso} {x.erro}" for x in db.query(Varredura))
    for valor in (CPF_A, CPF_B, "aluno1@email.com", "62998765432", "Flamboyant"):
        assert valor not in gravado

    # triagem: falso positivo com justificativa; histórico imutável
    tel = por_tipo[("escola", "telefone")]["id"]
    r = client.post(f"/api/v1/lgpd/achados/{tel}/decisao", headers=gerente,
                    json={"decisao": "falso_positivo", "justificativa": "Código da escola"})
    assert r.status_code == 200 and r.json()["status"] == "falso_positivo"
    assert r.json()["decisoes"][0]["usuario"] == "paloma@cge.go.gov.br"

    # nova varredura: a decisão é preservada (PBI-41) e o achado não volta como novo
    _varrer(client, gerente, escopo="recurso", id=REC_CSV)
    dados = client.get("/api/v1/lgpd/achados?status=falso_positivo", headers=gerente).json()
    assert [a["id"] for a in dados["achados"]] == [tel]
    with SessionLocal() as db:
        assert db.query(DecisaoTriagem).count() == 1 and db.query(Achado).count() == 4


def test_pendentes_so_recursos_novos_ou_alterados(client, admin, gerente, portal):
    _configurar_ia(client, admin)
    assert _varrer(client, gerente, escopo="pendentes").json()["criadas"] == 1   # só o CSV
    assert _varrer(client, gerente, escopo="pendentes").json()["criadas"] == 0   # nada mudou
    with SessionLocal() as db:
        db.get(Recurso, REC_CSV).last_modified = datetime.now(UTC)
        db.commit()
    assert _varrer(client, gerente, escopo="pendentes").json()["criadas"] == 1


def test_sem_modelo_vinculado_varre_so_regras_com_aviso(client, gerente, portal):
    _varrer(client, gerente, escopo="recurso", id=REC_CSV)
    v = client.get("/api/v1/lgpd/varreduras", headers=gerente).json()["varreduras"][0]
    assert v["status"] == "ok" and "Endereço não verificado" in v["aviso"]
    tipos = {a["tipo"] for a in client.get("/api/v1/lgpd/achados", headers=gerente).json()["achados"]}
    assert tipos == {"cpf", "email", "telefone"} and portal["perguntas"] == []


def test_modelo_fora_do_ar_interrompe_sem_gravar(client, admin, gerente, portal, monkeypatch):
    _configurar_ia(client, admin)

    def caiu(url, **_):
        from app.integrations.ai.base import AIProviderError
        raise AIProviderError(f"Não foi possível conectar a {url}")

    monkeypatch.setattr(ollama, "post_json", caiu)
    _varrer(client, gerente, escopo="recurso", id=REC_CSV)
    v = client.get("/api/v1/lgpd/varreduras", headers=gerente).json()["varreduras"][0]
    assert v["status"] == "erro" and "Modelo local indisponível" in v["erro"]
    assert client.get("/api/v1/lgpd/achados", headers=gerente).json()["total"] == 0


def test_permissoes(client, analista, orgao, portal):
    assert client.get("/api/v1/lgpd/achados", headers=analista).status_code == 200
    assert client.post("/api/v1/lgpd/varreduras", headers=analista,
                       json={"escopo": "pendentes"}).status_code == 403
    assert client.post("/api/v1/lgpd/achados/1/decisao", headers=analista,
                       json={"decisao": "confirmado"}).status_code == 403
    assert client.get("/api/v1/lgpd/achados", headers=orgao).status_code == 403


def test_cancelar_fila_e_mensagens_de_download(client, gerente, portal):
    # a API só enfileira: sem o ciclo do worker, tudo continua na fila
    client.post("/api/v1/lgpd/varreduras", headers=gerente, json={"escopo": "dataset", "id": DS})
    r = client.post("/api/v1/lgpd/varreduras/cancelar", headers=gerente)
    assert r.json() == {"canceladas": 2}
    vs = client.get("/api/v1/lgpd/varreduras", headers=gerente).json()
    assert vs["em_andamento"] == 0 and {v["status"] for v in vs["varreduras"]} == {"cancelada"}
    service.job_executar_fila()   # cancelada não é executada
    assert portal["baixados"] == []

    with SessionLocal() as db:
        r404 = service._explicar_download(service.CkanError("HTTP 404 ao baixar x", 404),
                                          db.get(Recurso, REC_PDF))
    assert "link quebrado" in r404 and "link do recurso" in r404
    with pytest.raises(leitura.FormatoNaoSuportado, match="ZIP"):
        leitura.ler(b"PK\x03\x04resto", "CSV")


def test_worker_retoma_varredura_interrompida_uma_vez(client, gerente, portal):
    """ADR-0025: varredura em "executando" no início do ciclo é de um worker que caiu."""
    def cair_no_meio():
        with SessionLocal() as db:
            v = db.query(Varredura).filter_by(recurso_id=REC_CSV, status="pendente").one()
            v.status, v.iniciada_em = "executando", datetime.now(UTC)
            db.commit()

    client.post("/api/v1/lgpd/varreduras", headers=gerente,
                json={"escopo": "recurso", "id": REC_CSV})
    cair_no_meio()
    service.job_executar_fila()   # 1ª interrupção: vira erro e o recurso volta à fila
    with SessionLocal() as db:
        vs = db.query(Varredura).order_by(Varredura.id).all()
    assert [(v.status, v.erro) for v in vs] == [("erro", service.INTERROMPIDA), ("ok", None)]
    assert vs[1].solicitada_por == "paloma@cge.go.gov.br"

    client.post("/api/v1/lgpd/varreduras", headers=gerente,
                json={"escopo": "recurso", "id": REC_CSV})
    cair_no_meio()
    service.job_executar_fila()   # 2ª interrupção do mesmo recurso: fica o erro, sem laço
    with SessionLocal() as db:
        assert db.query(Varredura).filter_by(status="pendente").count() == 0
        assert db.query(Varredura).filter_by(erro=service.INTERROMPIDA).count() == 2


def test_download_espera_no_http_429(monkeypatch):
    from app.integrations.ckan import client as ckan

    pausas, vezes = [], []
    respostas = [httpx.Response(429, headers={"Retry-After": "7"}), httpx.Response(429),
                 httpx.Response(200, content=b"a;b")]
    monkeypatch.setattr(ckan.time, "sleep", pausas.append)
    monkeypatch.setattr(ckan, "_aguardar_vez", lambda host, intervalo: vezes.append(host))
    c = CkanClient("http://portal", transport=httpx.MockTransport(lambda req: respostas.pop(0)))
    assert c.baixar("http://portal/x.csv", 1000) == b"a;b"
    assert pausas == [7.0, 120] and vezes == ["portal"] * 3  # Retry-After; sem ele, 60 s × 2^n

    c.esperas_429 = 0
    respostas.append(httpx.Response(429))
    with pytest.raises(ckan.CkanLimiteDeRequisicoes):
        c.baixar("http://portal/y.csv", 1000)


def test_download_intervalo_minimo_por_host(monkeypatch):
    from app.integrations.ckan import client as ckan

    relogio, pausas = [100.0], []

    def dormir(s):
        pausas.append(s)
        relogio[0] += s

    monkeypatch.setattr(ckan.time, "monotonic", lambda: relogio[0])
    monkeypatch.setattr(ckan.time, "sleep", dormir)
    for host in ("a.gov", "a.gov", "a.gov", "b.gov"):
        ckan._aguardar_vez(host, 2.0)
    ckan._aguardar_vez("a.gov", 0)   # intervalo 0 desliga
    assert pausas == [2.0, 2.0]
