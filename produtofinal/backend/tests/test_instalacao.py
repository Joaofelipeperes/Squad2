"""Primeira subida no servidor sem comandos à mão (ADR-0032): segredos, papéis iniciais,
administrador inicial, CKAN, IA local e primeira coleta."""
import logging

import pytest

from app import instalacao, segredos
from app.core.config import get_settings
from app.core.db import Base, SessionLocal, engine
from app.integrations.ai.policy import TarefaIA
from app.modules.acesso import service as acesso
from app.modules.ckan_config import service as ckan_config
from app.modules.ia import service as ia
from app.modules.inventario import service as inventario
from app.modules.inventario.dao import InventarioDao

SERVIDOR = {
    "GDA_PAPEIS_INICIAIS": '["administrador","gerente_geda"]',
    "GDA_ADMIN_INICIAL_EMAIL": "admin@cge.go.gov.br",
    "GDA_ADMIN_INICIAL_SENHA": "12345",
    "GDA_IA_LOCAL_URL": "http://ollama:11434",
}


@pytest.fixture
def config(monkeypatch):
    """Aplica variáveis GDA_* e recarrega a configuração (desfeito ao fim do teste)."""
    def aplicar(**env):
        for chave, valor in env.items():
            monkeypatch.setenv(chave, valor)
        get_settings.cache_clear()
    yield aplicar
    get_settings.cache_clear()


@pytest.fixture
def banco_vazio():
    """Banco recém-migrado do servidor: sem usuários, papéis, perfis nem coletas."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def test_preparar_servidor_do_zero(config, banco_vazio):
    config(**SERVIDOR)
    with SessionLocal() as db:
        instalacao.preparar(db)
        instalacao.preparar(db)  # idempotente: a API chama a cada subida

        assert sorted(p.codigo for p in acesso.listar_papeis(db)) == ["administrador",
                                                                      "gerente_geda"]
        usuarios = acesso.listar_usuarios(db)
        assert [u.email for u in usuarios] == ["admin@cge.go.gov.br"]
        assert [p.codigo for p in usuarios[0].papeis] == ["administrador"]
        assert acesso.autenticar(db, "admin@cge.go.gov.br", "12345") is not None

        perfis = sorted(p.modelo for p in ia.listar_perfis(db))
        assert perfis == ["bge-m3", "qwen2.5:7b-instruct"]
        vinculos = {t.tarefa: t.perfil_id for t in ia.listar_tarefas(db)}
        assert vinculos[TarefaIA.CLASSIFICACAO_DADO_PESSOAL] is not None
        assert vinculos[TarefaIA.EMBEDDINGS_DADO_PESSOAL] is not None
        assert vinculos[TarefaIA.ASSISTENTE] is None  # modelo pago: o administrador configura

        assert [p.nome for p in ckan_config.listar(db)] == [ckan_config.NOME_PERFIL_DOCKER]


def test_admin_inicial_nao_e_criado_se_ja_ha_usuarios(config):
    config(GDA_ADMIN_INICIAL_EMAIL="novo@cge.go.gov.br")
    with SessionLocal() as db:
        assert acesso.semear_admin_inicial(db) is None
        assert all(u.email != "novo@cge.go.gov.br" for u in acesso.listar_usuarios(db))


def test_aviso_enquanto_admin_usa_senha_inicial(config, banco_vazio, caplog):
    config(**SERVIDOR)
    with SessionLocal() as db:
        acesso.semear_admin_inicial(db)
        caplog.clear()
        with caplog.at_level(logging.WARNING):
            acesso.semear_admin_inicial(db)
        assert "ainda usa a senha inicial" in caplog.text


def test_sem_configuracao_de_servidor_nada_e_criado(config, banco_vazio):
    config()  # dev/testes: todos os papéis, sem admin nem IA automáticos
    with SessionLocal() as db:
        instalacao.preparar(db)
        assert len(acesso.listar_papeis(db)) == 5
        assert acesso.listar_usuarios(db) == []
        assert ia.listar_perfis(db) == []


def test_ia_local_nao_recria_se_ja_ha_perfil(config, banco_vazio):
    config(**SERVIDOR)
    with SessionLocal() as db:
        ia.salvar_perfil(db, ia.PerfilIn(nome="Escolhido na tela", tipo="mock", modelo="eco",
                                         execucao_local=True))
        instalacao.preparar(db)
        assert [p.nome for p in ia.listar_perfis(db)] == ["Escolhido na tela"]


def test_coleta_inicial_so_quando_nunca_houve_coleta(config, monkeypatch):
    chamadas = []
    monkeypatch.setattr(inventario, "job_coleta_diaria", lambda: chamadas.append(1))

    config()  # desligada por padrão
    inventario.job_coleta_inicial()
    assert chamadas == []

    config(GDA_COLETA_INICIAL="true")
    inventario.job_coleta_inicial()
    assert chamadas == [1]

    with SessionLocal() as db:
        InventarioDao(db).criar_coleta("agendada", None)
    inventario.job_coleta_inicial()
    assert chamadas == [1]


def test_segredos_gerados_uma_unica_vez(tmp_path):
    assert sorted(segredos.gerar(tmp_path)) == sorted(segredos.SEGREDOS)
    antes = {f.name: f.read_text() for f in tmp_path.iterdir()}
    assert segredos.gerar(tmp_path) == []
    assert {f.name: f.read_text() for f in tmp_path.iterdir()} == antes
    assert len(antes["secret_key"].encode()) >= 32
    assert (tmp_path / "db_senha").stat().st_mode & 0o004  # o Postgres (outro usuário) lê
    assert not (tmp_path / "secret_key").stat().st_mode & 0o044
