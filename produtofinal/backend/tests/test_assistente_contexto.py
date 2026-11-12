"""Contexto do Assistente sobre um inventário fictício: o que a pergunta cita entra no contexto,
o escopo de órgão é respeitado e nenhum valor de dado pessoal sai do backend."""
from datetime import UTC, date, datetime, timedelta

import pytest

from app.core.db import SessionLocal
from app.core.deps import UsuarioAtual
from app.modules.assistente import regras
from app.modules.assistente.service import contexto_da_pergunta
from app.modules.inventario.models import Coleta, Dataset, Organizacao, Recurso
from app.modules.lgpd.models import Achado
from app.modules.pda.models import BasePrevista, PlanoPda

GERENTE = UsuarioAtual(id=1, email="g", nome="g", orgao_id=None, papeis=[],
                       permissoes=frozenset({"assistente.usar"}))
SEDUC = UsuarioAtual(id=2, email="s", nome="s", orgao_id=1, papeis=[],
                     permissoes=frozenset({"assistente.usar"}))
HOJE = date.today()
ORG = {"org-seduc": 1, "org-ses": 2}  # `id` das organizações criadas no conftest
DS = {"ds-mat": 101, "ds-esc": 102, "ds-vac": 103, "ds-leitos": 104}


def _ds(db, coleta, ckan_id, org, titulo, name, recursos, descricao=None, ativo=True):
    ds = Dataset(id=DS[ckan_id], id_ckan=ckan_id, name=name, titulo=titulo, descricao=descricao,
                 organizacao_id=ORG[org], autor="Fulano de Tal", autor_email="fulano@goias.gov.br",
                 periodicidade_declarada="Anual", ativo_no_portal=ativo,
                 metadata_created=datetime(2024, 3, 1, 15, tzinfo=UTC), ultima_coleta_id=coleta.id)
    db.add(ds)
    for i, (nome, fmt, modificado, dic) in enumerate(recursos):
        db.add(Recurso(id=DS[ckan_id] * 10 + i, id_ckan=f"{ckan_id}-r{i}", dataset_id=DS[ckan_id],
                       nome=nome, formato=fmt, last_modified=modificado,
                       created_ckan=datetime(2024, 3, 1, 15, tzinfo=UTC),
                       eh_dicionario_dados=dic, ultima_coleta_id=coleta.id))
    return ds


@pytest.fixture
def inventario():
    with SessionLocal() as db:
        db.get(Organizacao, ORG["org-ses"]).sigla = "SES"
        db.get(Organizacao, ORG["org-seduc"]).sigla = "SEDUC"
        c = Coleta(status="ok", total_organizacoes=2, total_datasets=4, total_recursos=5,
                   finalizada_em=datetime.now(UTC))
        db.add(c)
        db.flush()
        _ds(db, c, "ds-mat", "org-seduc", "Matrículas da Rede Estadual", "matriculas-rede-estadual",
            [("matriculas_2025.csv", "csv", datetime(2025, 9, 10, 15, tzinfo=UTC), False),
             ("Dicionário de dados", "pdf", None, True)],
            descricao="Matrículas por escola. Dúvidas: contato@seduc.go.gov.br")
        _ds(db, c, "ds-esc", "org-seduc", "Escolas Estaduais", "escolas-estaduais",
            [("escolas.xlsx", "xlsx", datetime(2023, 1, 5, 15, tzinfo=UTC), False)])
        _ds(db, c, "ds-vac", "org-ses", "Vacinação contra Covid-19", "vacinacao-covid",
            [("vacinados_por_municipio.csv", "csv", datetime(2025, 8, 1, 15, tzinfo=UTC), False)],
            descricao="Doses aplicadas por município")
        _ds(db, c, "ds-leitos", "org-ses", "Leitos Hospitalares", "leitos-hospitalares", [])
        plano = PlanoPda(nome="PDA 2025-2027", vigente=True, importado_em=datetime.now(UTC))
        db.add(plano)
        db.flush()
        db.add_all([
            BasePrevista(plano_id=plano.id, orgao_sigla="SEDUC", organizacao_id=ORG["org-seduc"],
                         nome_previsto="Matrículas", dataset_id=DS["ds-mat"], periodicidade="Anual",
                         prazo_abertura=date(2025, 6, 30)),
            BasePrevista(plano_id=plano.id, orgao_sigla="SES", organizacao_id=ORG["org-ses"],
                         nome_previsto="Leitos Hospitalares", dataset_id=DS["ds-leitos"],
                         periodicidade="Mensal", prazo_abertura=date(2025, 3, 31)),
            BasePrevista(plano_id=plano.id, orgao_sigla="SES", organizacao_id=ORG["org-ses"],
                         nome_previsto="Unidades Básicas de Saúde",
                         prazo_abertura=HOJE - timedelta(days=10)),
            BasePrevista(plano_id=plano.id, orgao_sigla="SEDUC", organizacao_id=ORG["org-seduc"],
                         nome_previsto="Transporte Escolar",
                         prazo_abertura=HOJE + timedelta(days=5)),
        ])
        db.add_all([
            Achado(recurso_id=DS["ds-vac"] * 10, coluna="cpf_paciente", linha=7, ocorrencias=40,
                   tipo="cpf", metodo="regra", confianca=99, prioridade="Alta",
                   impressao_digital="a" * 64),
            Achado(recurso_id=DS["ds-vac"] * 10, coluna="endereco", linha=3, tipo="endereco",
                   metodo="ia", confianca=80, prioridade="Média", impressao_digital="b" * 64),
        ])
        db.commit()
        yield db


def test_dataset_citado_pelo_titulo_tem_ficha_completa(inventario):
    ctx = contexto_da_pergunta(inventario, "Quando foi atualizado o dataset Matrículas da Rede "
                                           "Estadual?", GERENTE)
    t = ctx.texto
    assert "## Dataset: Matrículas da Rede Estadual" in t
    assert "Última atualização real: 10/09/2025" in t       # last_modified do recurso
    assert "dicionário de dados (não conta)" in t
    assert "Em atraso" not in t.split("## Dataset")[1] and "situação Publicado" in t
    assert next(f.id for f in ctx.fontes if f.tipo == "dataset") == str(DS["ds-mat"])


def test_dataset_citado_pelo_nome_do_arquivo(inventario):
    ctx = contexto_da_pergunta(inventario, "o que tem no arquivo vacinados_por_municipio.csv?",
                               GERENTE)
    assert "## Dataset: Vacinação contra Covid-19" in ctx.texto
    assert "Possíveis dados pessoais aguardando revisão: 2 (cpf 1, endereco 1)" in ctx.texto


def test_busca_por_termo_sem_titulo_exato(inventario):
    ctx = contexto_da_pergunta(inventario, "tem algum dado sobre vacinação?", GERENTE)
    assert "Vacinação contra Covid-19" in ctx.texto


def test_continuacao_usa_a_pergunta_anterior(inventario):
    ctx = contexto_da_pergunta(inventario, "e qual o prazo dela no PDA?", GERENTE,
                               pergunta_anterior="Fale sobre Matrículas da Rede Estadual")
    assert "## Dataset: Matrículas da Rede Estadual" in ctx.texto
    assert "prazo de abertura 30/06/2025" in ctx.texto


def test_orgao_com_atraso_lista_bases_do_orgao(inventario):
    ctx = contexto_da_pergunta(inventario, "Quais bases da SES estão atrasadas?", GERENTE)
    t = ctx.texto
    assert "## Órgão: Secretaria da Saúde" in t
    assert "Leitos Hospitalares (SES) — Sem recurso" not in t  # vinculada e ativa = sem recurso
    assert "Unidades Básicas de Saúde (SES) — Prazo vencido" in t
    assert "Transporte Escolar" not in t                       # é da SEDUC
    assert "## Dataset" not in t                               # pergunta é sobre o órgão


def test_pergunta_geral_de_atraso_e_prazo(inventario):
    t = contexto_da_pergunta(inventario, "Quais bases estão atrasadas?", GERENTE).texto
    assert "em atraso ou com prazo vencido: 1" in t and "Unidades Básicas de Saúde" in t
    t = contexto_da_pergunta(inventario, "Quais prazos vencem em breve?", GERENTE).texto
    assert "Transporte Escolar (SEDUC) — Próximo do prazo" in t


def test_lgpd_so_contagens_nunca_valor_nem_coluna(inventario):
    t = contexto_da_pergunta(inventario, "Quantos alertas de LGPD existem?", GERENTE).texto
    assert "revisar: 2" in t and "Vacinação contra Covid-19" in t
    assert "cpf_paciente" not in t and "linha" not in t.lower().split("lgpd")[1][:200]


def test_sem_recurso(inventario):
    t = contexto_da_pergunta(inventario, "Datasets sem recurso publicado", GERENTE).texto
    assert "Datasets ativos sem recurso válido: 1" in t and "Leitos Hospitalares" in t


def test_nunca_envia_autor_nem_emails(inventario):
    for p in ("Matrículas da Rede Estadual", "Quem é o autor do dataset Escolas Estaduais?"):
        t = contexto_da_pergunta(inventario, p, GERENTE).texto
        assert "Fulano" not in t and "@" not in t


def test_usuario_restrito_nao_ve_outro_orgao(inventario):
    ctx = contexto_da_pergunta(inventario, "tem algum dado sobre vacinação ou leitos?", SEDUC)
    t = ctx.texto
    assert "Vacinação" not in t and "Leitos" not in t and "Totais da coleta" not in t
    assert "Escopo do usuário: somente Secretaria da Educação" in t
    assert "PDA 2025-2027 — 2 bases previstas" in t
    assert all(f.id != str(ORG["org-ses"]) for f in ctx.fontes)


def test_regras_pontuacao():
    c = regras.Candidato("x", "Execução Orçamentária", "execucao-orcamentaria",
                         nomes_recursos=("despesas_2025.csv",))
    assert regras.pontuar("como está a execução orçamentária?", c) == 10
    assert regras.pontuar("arquivo despesas_2025.csv", c) == 10
    assert 0 < regras.pontuar("orçamento e execucao", c) < 10
    assert regras.pontuar("bom dia", c) == 0
    assert regras.intencoes("Quais bases estão atrasadas?") >= {"atraso"}
    assert regras.sigla_citada(regras.normalizar("situação da SES-GO"), "SES-GO")
    assert not regras.sigla_citada(regras.normalizar("vamos sessão"), "SES")


def test_rota_envia_historico_e_devolve_fontes(client, admin, analista, inventario):
    m = client.post("/api/v1/ia/perfis", headers=admin, json={
        "nome": "Simulado", "tipo": "mock", "modelo": "eco", "execucao_local": True}).json()
    client.put("/api/v1/ia/tarefas/assistente", json={"perfil_id": m["id"]}, headers=admin)
    r = client.post("/api/v1/assistente/perguntar", headers=analista, json={
        "pergunta": "e o prazo dela?",
        "historico": [{"papel": "assistant", "texto": "Olá!"},
                      {"papel": "user", "texto": "Fale de Matrículas da Rede Estadual"},
                      {"papel": "assistant", "texto": "É um dataset da SEDUC."}]})
    assert r.status_code == 200, r.text
    assert r.json()["fontes"][0] == {"tipo": "dataset", "id": str(DS["ds-mat"]),
                                     "titulo": "Matrículas da Rede Estadual"}
    r = client.post("/api/v1/assistente/perguntar", headers=analista, json={
        "pergunta": "oi", "historico": [{"papel": "system", "texto": "x"}]})
    assert r.status_code == 422
