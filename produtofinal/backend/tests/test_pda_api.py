"""API do módulo pda — planilhas FICTÍCIAS geradas no próprio teste (CSV e XLSX em memória)."""
import io
from datetime import UTC, date, datetime

import pytest
from openpyxl import Workbook
from sqlalchemy import func, select

from app.core.db import SessionLocal
from app.modules.inventario.models import Dataset, Recurso
from app.modules.pda import service
from app.modules.pda.models import BasePrevista, PlanoPda
from tests.conftest import SENHA, login

API = "/api/v1/pda"
HOJE = date(2026, 10, 7)
CABECALHO = ["Orgão", "Base de Dados", "Descrição", "Unidade Responsável", "Atualização",
             "Políticas Públicas", "Possui Conteúdo Sigiloso?", "Disponível no Portal", "Prazo"]
URL = "https://dadosabertos.go.gov.br/dataset/"

# Linhas 2..7 da planilha (linha 1 = cabeçalho)
LINHAS_CSV = [
    ["SEDUC", "Escolas estaduais", "Lista de escolas", "Gerência de Rede", "Mensal", "Educação",
     "Não", URL + "escolas-estaduais/", ""],
    ["SEDUC", "Matrículas", "Matrículas por escola", "Gerência de Matrícula", "Mnsal", "Educação",
     "Não", URL + "matriculas-2026?aba=dados", "31/12/2026"],
    ["SES", "Leitos hospitalares", "Leitos por unidade", "Superintendência", "Semstral", "Saúde",
     "Sim", "Não", "2026-10-20"],
    ["", "Base sem órgão", "", "", "Anual", "", "Não", "Não", ""],
    ["AGEHAB", "Programas habitacionais", "", "", "Bianual", "N/A", "Não", "Não", "01/01/2026"],
    ["Total", "", "", "", "", "", "", "", ""],
]


@pytest.fixture(autouse=True)
def _hoje(monkeypatch):
    monkeypatch.setattr(service, "hoje_local", lambda: HOJE)


@pytest.fixture
def inventario():
    """Dataset publicado com um recurso normal e um dicionário de dados (que nunca conta)."""
    with SessionLocal() as db:
        db.add(Dataset(ckan_id="7f3e9a10-escolas", name="escolas-estaduais",
                       titulo="Escolas Estaduais", organizacao_id="org-seduc"))
        db.add_all([
            Recurso(ckan_id="r-escolas-csv", dataset_id="7f3e9a10-escolas", nome="escolas.csv",
                    last_modified=datetime(2026, 9, 1, 8, 0, tzinfo=UTC)),
            Recurso(ckan_id="r-escolas-dic", dataset_id="7f3e9a10-escolas",
                    nome="Dicionário de dados", eh_dicionario_dados=True,
                    last_modified=datetime(2026, 10, 1, 8, 0, tzinfo=UTC)),
        ])
        db.commit()


def _csv(linhas, cabecalho=CABECALHO) -> bytes:
    texto = "\n".join(";".join(c) for c in [cabecalho, *linhas]) + "\n"
    return ("﻿" + texto).encode("utf-8")  # UTF-8 com BOM, separador ";"


def _xlsx(linhas, cabecalho=CABECALHO) -> bytes:
    wb = Workbook()
    wb.active.title = "Leia-me"
    wb.active.append(["Planilha fictícia para testes"])
    ws = wb.create_sheet("PDA")
    ws.append(cabecalho)
    for linha in linhas:
        ws.append(linha)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _importar(client, h, nome, conteudo=None, arquivo="pda.csv", **campos):
    dados = {"nome": nome, **{k: str(v).lower() if isinstance(v, bool) else v
                              for k, v in campos.items()}}
    return client.post(f"{API}/planos", headers=h, data=dados,
                       files={"arquivo": (arquivo, conteudo or _csv(LINHAS_CSV),
                                          "application/octet-stream")})


def _bases(client, h, **params):
    r = client.get(f"{API}/bases", headers=h, params=params)
    assert r.status_code == 200, r.text
    return r.json()


def _por_nome(corpo):
    return {b["nome_previsto"]: b for b in corpo["bases"]}


# ---------------------------------------------------------- importação
def test_importar_csv_resumo_e_vinculo_pelo_id(client, gerente, inventario):
    r = _importar(client, gerente, "PDA 2025-2027", vigencia_inicio="2025-01-01",
                  vigencia_fim="2027-12-31")
    assert r.status_code == 201, r.text
    resumo = r.json()
    assert resumo["bases_importadas"] == 4
    assert resumo["linhas_ignoradas"] == [{"linha": 5, "motivo": "Sem Órgão."}]
    assert (resumo["vinculos_resolvidos"], resumo["vinculos_pendentes"],
            resumo["sem_vinculo"]) == (1, 1, 2)
    assert resumo["orgaos_sem_correspondencia"] == ["AGEHAB"]
    plano = resumo["plano"]
    assert plano["vigente"] is True  # primeiro PDA vira vigente
    assert plano["importado_por"] == "Paloma" and plano["arquivo_nome"] == "pda.csv"
    assert (plano["total_bases"], plano["vinculos_resolvidos"], plano["vinculos_pendentes"]) == (
        4, 1, 1)
    assert plano["vigencia_inicio"] == "2025-01-01"

    with SessionLocal() as db:
        escolas = db.scalar(select(BasePrevista).where(
            BasePrevista.nome_previsto == "Escolas estaduais"))
        assert escolas.dataset_id == "7f3e9a10-escolas"  # ID do CKAN, nunca o name
        assert escolas.dataset_name_planilha == "escolas-estaduais"
        assert escolas.organizacao_id == "org-seduc" and escolas.linha_planilha == 2
        matriculas = db.scalar(select(BasePrevista).where(
            BasePrevista.nome_previsto == "Matrículas"))
        assert matriculas.dataset_id is None
        assert matriculas.dataset_name_planilha == "matriculas-2026"
        assert (matriculas.periodicidade, matriculas.periodicidade_original) == ("Mensal", "Mnsal")
        assert matriculas.prazo_abertura == date(2026, 12, 31)
        assert matriculas.organizacao_id == "org-seduc"  # casada pela sigla


def test_importar_xlsx(client, gerente, inventario):
    with SessionLocal() as db:  # dataset inativo no portal e dataset só com dicionário
        db.add_all([
            Dataset(ckan_id="9b1c-removido", name="obras-removidas", titulo="Obras",
                    organizacao_id="org-ses", ativo_no_portal=False),
            Recurso(ckan_id="r-obras", dataset_id="9b1c-removido", nome="obras.csv"),
            Dataset(ckan_id="5d2e-so-dicionario", name="so-dicionario", titulo="Só dicionário",
                    organizacao_id="org-ses"),
            Recurso(ckan_id="r-dic", dataset_id="5d2e-so-dicionario",
                    nome="Dicionário de dados", eh_dicionario_dados=True),
        ])
        db.commit()
    linhas = [
        ["SEDUC", "Escolas estaduais", "Escolas\nda rede", None, "Mensal", "Educação", "Não",
         URL + "escolas-estaduais", date(2026, 6, 30)],
        ["SES", "Obras", None, None, "Anual", "Saúde", "Não", URL + "obras-removidas",
         date(2026, 9, 1)],
        [None, None, None, None, None, None, None, None, None],
        ["SES", None, None, None, None, None, None, None, None],
        ["SES", "Só dicionário", None, None, "N/A", None, None, URL + "so-dicionario", None],
        ["SES", "Inexistente", None, None, "Sob Demanda", None, "Sim", URL + "nao-existe", None],
        ["Total", 4, None, None, None, None, None, None, None],
    ]
    r = _importar(client, gerente, "PDA xlsx", _xlsx(linhas), arquivo="PDA.XLSX")
    assert r.status_code == 201, r.text
    resumo = r.json()
    assert resumo["bases_importadas"] == 4
    assert resumo["linhas_ignoradas"] == [{"linha": 5, "motivo": "Sem Base de Dados."}]
    assert (resumo["vinculos_resolvidos"], resumo["vinculos_pendentes"],
            resumo["sem_vinculo"]) == (3, 1, 0)

    bases = _por_nome(_bases(client, gerente))
    assert bases["Escolas estaduais"]["situacao"] == "Publicado"
    assert bases["Escolas estaduais"]["descricao"] == "Escolas\nda rede"
    assert bases["Obras"]["dataset_ativo"] is False  # PBI-15: sumiu do portal
    assert bases["Obras"]["situacao"] == "Em atraso"
    assert bases["Só dicionário"]["situacao"] == "Sem recurso"
    assert bases["Só dicionário"]["recursos_validos"] == 0
    assert bases["Inexistente"]["vinculo"] == "pendente"
    assert bases["Inexistente"]["situacao"] == "Não publicado"
    assert bases["Inexistente"]["periodicidade"] == "Eventual"
    assert bases["Inexistente"]["possui_conteudo_sigiloso"] is True


def test_cabecalho_obrigatorio_ausente_nada_gravado(client, gerente):
    sem_base = [c for c in CABECALHO if c != "Base de Dados"]
    r = _importar(client, gerente, "PDA ruim", _csv([["SEDUC", "x"]], cabecalho=sem_base))
    assert r.status_code == 422 and "Base de Dados" in r.json()["detail"]
    assert client.get(f"{API}/planos", headers=gerente).json() == []
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(BasePrevista)) == 0


def test_extensao_tamanho_e_vigencia_invalidos(client, gerente):
    assert _importar(client, gerente, "PDA txt", b"x", arquivo="pda.txt").status_code == 422
    grande = _csv(LINHAS_CSV) + b" " * (5 * 1024 * 1024)
    assert _importar(client, gerente, "PDA grande", grande).status_code == 413
    r = _importar(client, gerente, "PDA datas", vigencia_inicio="2027-01-01",
                  vigencia_fim="2025-01-01")
    assert r.status_code == 422
    assert client.get(f"{API}/planos", headers=gerente).json() == []


def test_nome_repetido(client, gerente):
    assert _importar(client, gerente, "PDA 2025-2027").status_code == 201
    r = _importar(client, gerente, "  pda 2025-2027 ")
    assert r.status_code == 409


# ---------------------------------------------------------- vigente e exclusão
def test_segundo_pda_vigente_e_exclusao(client, gerente):
    p1 = _importar(client, gerente, "PDA 2023-2025").json()["plano"]
    p2 = _importar(client, gerente, "PDA 2025-2027", definir_vigente=True).json()["plano"]
    p3 = _importar(client, gerente, "PDA rascunho").json()["plano"]
    assert p2["vigente"] is True and p3["vigente"] is False
    planos = client.get(f"{API}/planos", headers=gerente).json()
    assert [p["id"] for p in planos] == [p2["id"], p3["id"], p1["id"]]  # vigente primeiro
    assert [p["vigente"] for p in planos] == [True, False, False]

    # GET /bases sem plano_id usa o vigente; com plano_id, o escolhido
    assert _bases(client, gerente)["plano"]["id"] == p2["id"]
    assert _bases(client, gerente, plano_id=p1["id"])["plano"]["id"] == p1["id"]
    assert client.get(f"{API}/bases", headers=gerente,
                      params={"plano_id": 9999}).status_code == 404

    r = client.put(f"{API}/planos/{p1['id']}/vigente", headers=gerente)
    assert r.status_code == 200 and r.json()["vigente"] is True
    with SessionLocal() as db:
        assert db.scalars(select(PlanoPda.id).where(PlanoPda.vigente.is_(True))).all() == [
            p1["id"]]
    assert client.put(f"{API}/planos/9999/vigente", headers=gerente).status_code == 404

    assert client.delete(f"{API}/planos/{p1['id']}", headers=gerente).status_code == 409
    assert client.delete(f"{API}/planos/{p2['id']}", headers=gerente).status_code == 204
    assert client.delete(f"{API}/planos/{p2['id']}", headers=gerente).status_code == 404
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(BasePrevista)
                         .where(BasePrevista.plano_id == p2["id"])) == 0
        assert db.scalar(select(func.count()).select_from(BasePrevista)) == 8


def test_sem_nenhum_pda(client, gerente):
    corpo = _bases(client, gerente)
    assert corpo["plano"] is None and corpo["bases"] == [] and corpo["total_previstas"] == 0
    assert corpo["opcoes"] == {"orgaos": [], "periodicidades": [], "anos": []}
    assert corpo["hoje"] == "2026-10-07" and corpo["janela_alerta_dias"] == 30


# ---------------------------------------------------------- lista, filtros e detalhe
def test_lista_situacoes_opcoes_e_filtros(client, gerente, inventario):
    _importar(client, gerente, "PDA 2025-2027")
    corpo = _bases(client, gerente)
    assert corpo["total_previstas"] == 4
    assert [b["orgao_sigla"] for b in corpo["bases"]] == ["AGEHAB", "SEDUC", "SEDUC", "SES"]
    bases = _por_nome(corpo)
    assert bases["Escolas estaduais"]["situacao"] == "Publicado"
    assert bases["Matrículas"]["situacao"] == "Em dia"
    assert bases["Leitos hospitalares"]["situacao"] == "Próximo do prazo"
    assert bases["Leitos hospitalares"]["flag_prazo"] == "proximo"
    assert bases["Programas habitacionais"]["situacao"] == "Em atraso"
    assert bases["Programas habitacionais"]["flag_prazo"] == "vencido"
    assert bases["Programas habitacionais"]["orgao_chave"] == "sigla:AGEHAB"
    assert bases["Programas habitacionais"]["orgao_nome"] is None
    assert bases["Programas habitacionais"]["periodicidade"] == "Bienal"
    assert bases["Escolas estaduais"]["orgao_nome"] == "Secretaria da Educação"
    assert corpo["opcoes"]["orgaos"] == [
        {"valor": "sigla:AGEHAB", "rotulo": "AGEHAB"},
        {"valor": "org-seduc", "rotulo": "SEDUC — Secretaria da Educação"},
        {"valor": "org-ses", "rotulo": "SES — Secretaria da Saúde"},
    ]
    assert corpo["opcoes"]["periodicidades"] == ["Mensal", "Semestral", "Bienal"]
    assert corpo["opcoes"]["anos"] == [2026]

    def nomes(**params):
        c = _bases(client, gerente, **params)
        assert c["total_previstas"] == 4  # contador "de M previstas" ignora filtros
        return sorted(b["nome_previsto"] for b in c["bases"])

    assert nomes(situacao="Publicado") == ["Escolas estaduais"]
    assert nomes(orgao="org-seduc") == ["Escolas estaduais", "Matrículas"]
    assert nomes(orgao="sigla:AGEHAB") == ["Programas habitacionais"]
    assert nomes(periodicidade="Mensal") == ["Escolas estaduais", "Matrículas"]
    assert nomes(prazo="vencido") == ["Programas habitacionais"]
    assert nomes(prazo="proximo") == ["Leitos hospitalares"]
    assert nomes(ano=2026, orgao="org-seduc") == ["Matrículas"]
    assert nomes(orgao="", situacao="") == sorted(bases)  # vazio = sem filtro
    assert client.get(f"{API}/bases", headers=gerente,
                      params={"prazo": "amanha"}).status_code == 422


def test_detalhe_da_base(client, gerente, inventario):
    _importar(client, gerente, "PDA 2025-2027")
    escolas = _por_nome(_bases(client, gerente))["Escolas estaduais"]
    r = client.get(f"{API}/bases/{escolas['id']}", headers=gerente)
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["vinculo"] == "resolvido" and b["dataset_id"] == "7f3e9a10-escolas"
    assert (b["dataset_name"], b["dataset_titulo"]) == ("escolas-estaduais", "Escolas Estaduais")
    assert b["dataset_ativo"] is True and b["recursos_validos"] == 1  # dicionário não conta
    assert b["ultima_atualizacao"].startswith("2026-09-01T08:00:00")  # não a do dicionário
    assert b["ultima_atualizacao_estimada"] is False
    assert b["plano_nome"] == "PDA 2025-2027" and b["prazo_abertura"] is None
    assert b["situacao"] == "Publicado" and b["classificacao"] == "pda"
    assert client.get(f"{API}/bases/9999", headers=gerente).status_code == 404


def test_vincular_resolve_pendente_sem_recalcular_resolvido(client, gerente, inventario):
    plano = _importar(client, gerente, "PDA 2025-2027").json()["plano"]
    with SessionLocal() as db:
        # o dataset vinculado muda de name e outro dataset passa a usar o name antigo:
        # o vínculo resolvido continua no ID original
        db.get(Dataset, "7f3e9a10-escolas").name = "escolas-renomeado"
        db.add(Dataset(ckan_id="aaaa-impostor", name="escolas-estaduais", titulo="Outro"))
        # o dataset pendente foi publicado depois da importação
        db.add(Dataset(ckan_id="c0ffee-matriculas", name="matriculas-2026",
                       titulo="Matrículas 2026", organizacao_id="org-seduc"))
        db.add(Recurso(ckan_id="r-mat", dataset_id="c0ffee-matriculas", nome="mat.csv",
                       created=datetime(2026, 9, 20, tzinfo=UTC)))
        db.commit()
    r = client.post(f"{API}/planos/{plano['id']}/vincular", headers=gerente)
    assert r.status_code == 200, r.text
    assert r.json() == {"vinculos_resolvidos": 1, "vinculos_pendentes": 0}
    assert client.post(f"{API}/planos/9999/vincular", headers=gerente).status_code == 404

    bases = _por_nome(_bases(client, gerente))
    assert bases["Escolas estaduais"]["dataset_id"] == "7f3e9a10-escolas"
    assert bases["Escolas estaduais"]["dataset_name"] == "escolas-renomeado"  # name atual
    mat = bases["Matrículas"]
    assert mat["vinculo"] == "resolvido" and mat["dataset_id"] == "c0ffee-matriculas"
    assert mat["situacao"] == "Publicado"
    assert mat["ultima_atualizacao_estimada"] is True  # sem last_modified → created
    planos = client.get(f"{API}/planos", headers=gerente).json()
    assert (planos[0]["vinculos_resolvidos"], planos[0]["vinculos_pendentes"]) == (2, 0)


# ---------------------------------------------------------- permissões e escopo de órgão
def test_permissoes(client, gerente, analista, orgao):
    assert _importar(client, analista, "PDA analista").status_code == 403
    plano = _importar(client, gerente, "PDA 2025-2027").json()["plano"]
    assert client.put(f"{API}/planos/{plano['id']}/vigente", headers=analista).status_code == 403
    assert client.delete(f"{API}/planos/{plano['id']}", headers=analista).status_code == 403
    assert client.post(f"{API}/planos/{plano['id']}/vincular",
                       headers=analista).status_code == 403
    assert client.get(f"{API}/bases", headers=analista).status_code == 200  # analista vê
    assert client.get(f"{API}/planos", headers=analista).status_code == 200
    assert client.get(f"{API}/bases", headers=orgao).status_code == 403
    assert client.get(f"{API}/planos", headers=orgao).status_code == 403


def test_usuario_restrito_ve_so_o_proprio_orgao(client, admin, gerente):
    _importar(client, gerente, "PDA 2025-2027")
    papel = client.post("/api/v1/acesso/papeis", headers=admin, json={
        "codigo": "pda_orgao", "nome": "PDA do órgão", "permissoes": ["pda.acessar"]}).json()
    r = client.post("/api/v1/acesso/usuarios", headers=admin, json={
        "email": "pda@seduc.go.gov.br", "nome": "PDA SEDUC", "senha": SENHA,
        "papel_ids": [papel["id"]], "orgao_id": "org-seduc"})
    assert r.status_code == 201, r.text
    h = login(client, "pda@seduc.go.gov.br")
    corpo = _bases(client, h)
    assert {b["orgao_chave"] for b in corpo["bases"]} == {"org-seduc"}  # nem AGEHAB (sem órgão)
    assert corpo["total_previstas"] == 2
    leitos = _por_nome(_bases(client, gerente))["Leitos hospitalares"]
    assert client.get(f"{API}/bases/{leitos['id']}", headers=h).status_code == 404
