"""Tela Organizações (US19) e formato fechado (PBI-53). Dados fictícios."""
from datetime import UTC, date, datetime

import pytest

from app.core.db import SessionLocal
from app.modules.inventario.models import Coleta, Dataset, Recurso
from app.modules.metadados import regras
from app.modules.pda import service as pda_service
from tests.conftest import SEDUC, SES

API = "/api/v1/painel/organizacoes"
URL = "https://dadosabertos.go.gov.br/dataset/"
DS_A, DS_B, DS_C = 1, 2, 3


@pytest.fixture(autouse=True)
def _hoje(monkeypatch):
    monkeypatch.setattr(pda_service, "hoje_local", lambda: date(2026, 10, 18))


@pytest.fixture
def inventario():
    """org-ses: 2 datasets ativos (CSV, ZIP, PDF, sem formato, dicionário PDF, recurso apagado
    XLS) e 1 fora do portal (PDF); org-seduc: nenhum dataset."""
    lm = datetime(2026, 9, 1, tzinfo=UTC)
    with SessionLocal() as db:
        db.add_all([Coleta(id=1, status="ok"), Coleta(id=2, status="ok")])
        db.add_all([
            Dataset(id=DS_A, id_ckan="ds-a", name="indicadores-saude", titulo="Indicadores",
                    organizacao_id=SES, ultima_coleta_id=2),
            Dataset(id=DS_B, id_ckan="ds-b", name="leitos", titulo="Leitos", organizacao_id=SES,
                    ultima_coleta_id=2),
            Dataset(id=DS_C, id_ckan="ds-c", name="antigo", titulo="Antigo", organizacao_id=SES,
                    ativo_no_portal=False, ultima_coleta_id=1),
        ])
        db.add_all([
            Recurso(id=1, id_ckan="r1", dataset_id=DS_A, formato="CSV", ultima_coleta_id=2,
                    last_modified=lm),
            Recurso(id=2, id_ckan="r2", dataset_id=DS_A, formato="ZIP", ultima_coleta_id=2),
            Recurso(id=3, id_ckan="r3", dataset_id=DS_A, nome="Dicionário de dados", formato="PDF",
                    eh_dicionario_dados=True, ultima_coleta_id=2),
            Recurso(id=4, id_ckan="r4", dataset_id=DS_A, formato="XLS", ultima_coleta_id=1),
            Recurso(id=5, id_ckan="r5", dataset_id=DS_B, formato="PDF", ultima_coleta_id=2),
            Recurso(id=6, id_ckan="r6", dataset_id=DS_B, formato=None, ultima_coleta_id=2),
            Recurso(id=7, id_ckan="r7", dataset_id=DS_C, formato="PDF", ultima_coleta_id=1),
        ])
        db.commit()


@pytest.mark.parametrize("formato,esperado", [
    ("CSV", True), (" csv ", True), (".json", True), ("ZIP", False), ("PDF", False),
    ("", False), (None, False),
])
def test_eh_formato_aberto(formato, esperado):
    assert regras.eh_formato_aberto(formato, ["CSV", "JSON"]) is esperado


def _org(corpo, chave):
    return next(o for o in corpo["organizacoes"] if o["chave"] == chave)


def test_sem_pda(client, gerente, inventario):
    corpo = client.get(API, headers=gerente).json()
    assert corpo["plano"] is None
    assert corpo["formatos_abertos"] == ["CSV", "JSON", "XML", "ODS", "GEOJSON", "TXT"]
    assert [o["nome"] for o in corpo["organizacoes"]] == [
        "Secretaria da Educação", "Secretaria da Saúde"]
    ses = _org(corpo, str(SES))
    # Só datasets ativos; recursos atuais sem dicionário; formatos fechados: ZIP, PDF e sem formato
    assert ses["datasets_no_portal"] == 2 and ses["recursos_validos"] == 4
    assert ses["recursos_formato_fechado"] == 3
    assert ses["formatos_fechados"] == {"ZIP": 1, "PDF": 1, "": 1}
    assert ses["bases_previstas"] == 0
    assert ses["atualizacao_pct"] is None and ses["indice_atencao"] is None
    assert ses["riscos_lgpd"] is None
    seduc = _org(corpo, str(SEDUC))
    assert seduc["datasets_no_portal"] == 0 and seduc["recursos_formato_fechado"] == 0


def test_bases_do_pda_vigente_por_orgao(client, gerente, inventario):
    texto = ("Orgão;Base de Dados;Meta/Prazo para abertura;Disponível no Portal\n"
             f"SES;Indicadores;Março/2025;{URL}indicadores-saude\n"
             "SES;Vacinas;Março/2025;Não\n"
             f"SES;Antiga;Março/2025;{URL}antigo\n"
             "SES;Leitos;Outubro/2026;Não\n"
             "SEDUC;Matrículas;Dezembro/2027;Não\n"
             "XYZ;Base sem órgão;Março/2025;Não\n")
    r = client.post("/api/v1/pda/planos", headers=gerente, data={"nome": "PDA teste"},
                    files={"arquivo": ("pda.csv", texto.encode(), "text/csv")})
    assert r.status_code == 201, r.text
    corpo = client.get(API, headers=gerente).json()
    assert corpo["plano"]["nome"] == "PDA teste"
    ses = _org(corpo, str(SES))
    assert ses["siglas"] == ["SES"] and ses["bases_previstas"] == 4
    assert ses["bases_vinculadas"] == 2 and ses["bases_publicadas"] == 1
    # Só a vinculada a dataset fora do portal conta; Vacinas (sem vínculo, prazo vencido) não
    assert ses["bases_em_atraso"] == 1
    assert ses["bases_proximas_do_prazo"] == 1  # Leitos vence em 31/10/2026 (janela de 30 dias)
    seduc = _org(corpo, str(SEDUC))
    assert seduc["bases_previstas"] == 1 and seduc["bases_em_atraso"] is None  # sem vínculo
    # Sigla do PDA sem organização no portal vira linha própria
    xyz = _org(corpo, "sigla:XYZ")
    assert xyz["organizacao_id"] is None and xyz["nome"] == "XYZ"
    assert xyz["bases_previstas"] == 1 and xyz["datasets_no_portal"] == 0


def test_parametro_formatos_abertos_editavel(client, admin, gerente, inventario):
    r = client.put("/api/v1/parametros/formatos_abertos", headers=admin,
                   json={"valor": ["CSV", "ZIP"]})
    assert r.status_code == 200, r.text
    ses = _org(client.get(API, headers=gerente).json(), str(SES))
    assert ses["formatos_fechados"] == {"PDF": 1, "": 1}


def test_permissao(client, orgao):
    assert client.get(API, headers=orgao).status_code == 403  # papel de órgão não tem painel


def test_excluidos_nao_contam_no_painel(client, gerente, inventario):
    """Exclusão lógica (ADR-0019): dataset e recurso excluídos saem das contagens."""
    with SessionLocal() as db:
        db.get(Dataset, DS_B).deleted = True  # leva PDF e sem formato
        db.get(Recurso, 2).deleted = True     # ZIP do DS_A
        db.commit()
    ses = _org(client.get(API, headers=gerente).json(), str(SES))
    assert ses["datasets_no_portal"] == 1 and ses["recursos_validos"] == 1
    assert ses["recursos_formato_fechado"] == 0 and ses["formatos_fechados"] == {}


def _atualizacao_no_ckan(**por_dataset):
    """Campo "Atualização" do CKAN nos extras de cada dataset (None = campo ausente)."""
    with SessionLocal() as db:
        for ds_id, valor in por_dataset.items():
            db.get(Dataset, int(ds_id.removeprefix("ds"))).extras = (
                {} if valor is None else {"Atualização": valor})
        db.commit()


@pytest.mark.parametrize("periodicidade,pct,atrasadas", [
    ("Mensal", 0, 1),     # última atualização em 01/09/2026: 47 dias > 30
    ("Anual", 100, 0),    # 47 dias, bem dentro de 365
    ("Não possui atualização periódica", None, None),  # declaração válida, sem prazo: fora do %
])
def test_atualizacao_pela_periodicidade_do_ckan(client, gerente, inventario, periodicidade, pct,
                                                atrasadas):
    """ADR-0037: todas as bases publicadas do órgão entram, sem PDA nem vínculo; leitos sem o
    campo "Atualização" é "Periodicidade não informada" (fora do %, contada à parte)."""
    _atualizacao_no_ckan(ds1=periodicidade, ds2=None)
    corpo = client.get(API, headers=gerente).json()
    assert corpo["plano"] is None
    ses = _org(corpo, str(SES))
    assert ses["atualizacao_pct"] == pct and ses["atualizacoes_atrasadas"] == atrasadas
    assert ses["atualizacoes_avaliadas"] == (0 if pct is None else 1)
    assert ses["periodicidade_nao_informada"] == 1
    seduc = _org(corpo, str(SEDUC))
    assert seduc["atualizacao_pct"] is None and seduc["atualizacoes_avaliadas"] == 0
    assert seduc["periodicidade_nao_informada"] == 0


def test_atualizacao_ignora_periodicidade_do_pda(client, gerente, inventario):
    texto = ("Orgão;Base de Dados;Atualização;Disponível no Portal\n"
             f"SES;Indicadores;Mensal;{URL}indicadores-saude\n")
    r = client.post("/api/v1/pda/planos", headers=gerente, data={"nome": "PDA teste"},
                    files={"arquivo": ("pda.csv", texto.encode(), "text/csv")})
    assert r.status_code == 201, r.text
    _atualizacao_no_ckan(ds1="Anual")  # no CKAN é Anual: 47 dias, em dia
    ses = _org(client.get(API, headers=gerente).json(), str(SES))
    assert (ses["atualizacao_pct"], ses["atualizacoes_atrasadas"]) == (100, 0)


# ---------------------------------------------------------- riscos LGPD e índice de atenção
@pytest.fixture
def achados(inventario):
    """SES: 4 recursos varridos (1, 2, 5, 6). Em aberto: recurso 1 (um achado a revisar e um
    confirmado) e recurso 5 (a revisar); recurso 2 só com falso positivo; recurso 6 tratado."""
    from app.modules.lgpd.models import Achado, Varredura
    with SessionLocal() as db:
        db.add_all([Varredura(recurso_id=r, status="ok") for r in (1, 2, 5, 6)]
                   + [Varredura(recurso_id=7, status="erro")])
        for i, (rec, status) in enumerate([(1, "revisar"), (1, "confirmado"),
                                           (2, "falso_positivo"), (5, "revisar"), (6, "tratado")]):
            db.add(Achado(recurso_id=rec, coluna=f"c{i}", tipo="cpf", metodo="regra",
                          confianca=95, prioridade="Alta", status=status,
                          impressao_digital=f"h{i}"))
        db.commit()


def _mensal_no_ckan(client, gerente):
    """Indicadores (SES) "Mensal" no campo Atualização do CKAN, atualizada em 01/09/2026: atrasada
    em 18/10/2026. Leitos sem o campo não entra no % (ADR-0037)."""
    _atualizacao_no_ckan(ds1="Mensal", ds2=None)


def test_riscos_lgpd_por_orgao(client, gerente, achados):
    corpo = client.get(API, headers=gerente).json()
    assert corpo["lgpd_visivel"] is True
    assert corpo["criterio_atencao"] == {"peso_lgpd": 70, "peso_atualizacao": 30,
                                         "limite_medio": 25, "limite_alto": 50}
    ses = _org(corpo, str(SES))
    # Falso positivo e tratado não contam; o recurso com dois achados conta uma vez
    assert ses["riscos_lgpd"] == 2 and ses["lgpd_recursos_analisados"] == 4
    assert ses["lgpd_aguardando_revisao"] == 2 and ses["lgpd_confirmados"] == 1
    assert ses["risco_lgpd_pct"] == 50
    # Sem o campo "Atualização" no CKAN não há atualização avaliada: o índice usa só o risco LGPD
    # (50 = início do Alto)
    assert (ses["indice_atencao"], ses["indice_atencao_valor"]) == ("Alto", 50)
    assert ses["indice_atencao_componentes"] == ["Risco LGPD"]
    seduc = _org(corpo, str(SEDUC))  # nenhum recurso varrido, nenhuma base: sem índice
    assert seduc["riscos_lgpd"] is None and seduc["indice_atencao"] is None
    assert seduc["indice_atencao_componentes"] == []


def test_indice_de_atencao_com_pesos_dos_parametros(client, admin, gerente, achados):
    _mensal_no_ckan(client, gerente)
    ses = _org(client.get(API, headers=gerente).json(), str(SES))
    # 0,7 × 50 (risco LGPD) + 0,3 × 100 (a única base avaliada está atrasada) = 65
    assert (ses["indice_atencao"], ses["indice_atencao_valor"]) == ("Alto", 65)
    assert ses["indice_atencao_componentes"] == ["Risco LGPD", "Atraso de atualização"]
    assert ses["atraso_atualizacao_pct"] == 100

    def alterar(chave, valor):
        r = client.put(f"/api/v1/parametros/{chave}", headers=admin, json={"valor": valor})
        assert r.status_code == 200, r.text

    alterar("indice_atencao_limite_alto", 70)
    assert _org(client.get(API, headers=gerente).json(), str(SES))["indice_atencao"] == "Médio"
    alterar("peso_lgpd_indice_atencao", 0)  # peso 0: o componente sai da média
    ses = _org(client.get(API, headers=gerente).json(), str(SES))
    assert ses["indice_atencao_valor"] == 100
    assert ses["indice_atencao_componentes"] == ["Atraso de atualização"]


def test_sem_lgpd_acessar_indice_so_com_atualizacao(client, gerente, achados):
    from app.modules.acesso.service import criar_usuario
    from tests.conftest import SENHA, login
    _mensal_no_ckan(client, gerente)
    with SessionLocal() as db:
        criar_usuario(db, "junior@cge.go.gov.br", "Júnior", SENHA, ["superintendencia"])
    corpo = client.get(API, headers=login(client, "junior@cge.go.gov.br")).json()
    assert corpo["lgpd_visivel"] is False
    ses = _org(corpo, str(SES))
    # O painel não amplia o acesso: nada do LGPD, nem dentro do índice
    assert ses["riscos_lgpd"] is None and ses["lgpd_recursos_analisados"] == 0
    assert ses["indice_atencao_valor"] == 100
    assert ses["indice_atencao_componentes"] == ["Atraso de atualização"]


def test_parametros_do_indice_validam_a_faixa(client, admin):
    for valor in (-1, 101):
        r = client.put("/api/v1/parametros/peso_lgpd_indice_atencao", headers=admin,
                       json={"valor": valor})
        assert r.status_code == 422, r.text
    r = client.put("/api/v1/parametros/peso_lgpd_indice_atencao", headers=admin,
                   json={"valor": 0.5})
    assert r.status_code == 422  # tipo do padrão: inteiro


def test_regra_do_indice_de_atencao():
    from app.modules.painel import regras as r
    c = r.CriterioAtencao(peso_lgpd=70, peso_atualizacao=30, limite_medio=25, limite_alto=50)
    assert r.indice_atencao(None, None, c) is None
    i = r.indice_atencao(20, 10, c)  # 0,7 × 20 + 0,3 × 10 = 17
    assert (i.valor, i.faixa, i.componentes) == (17, r.BAIXO, [r.LGPD, r.ATUALIZACAO])
    assert r.indice_atencao(None, 40, c).valor == 40  # pesos redistribuídos
    assert r.indice_atencao(25, None, c).faixa == r.MEDIO  # limite é inclusivo
    zero = r.CriterioAtencao(peso_lgpd=0, peso_atualizacao=0, limite_medio=25, limite_alto=50)
    assert r.indice_atencao(80, 80, zero) is None
    assert r.pct(1, 3) == 33 and r.pct(0, 0) is None
