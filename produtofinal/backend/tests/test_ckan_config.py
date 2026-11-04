"""Configurações CKAN (ADR-0024): perfis de conexão e troca do CKAN em uso."""
import pytest

from app.core.config import CKAN_LOCAL_DOCKER
from app.core.db import SessionLocal
from app.modules.ckan_config import service
from app.modules.ckan_config.schemas import PerfilCkanIn

URL = "/api/v1/ckan-config/perfis"


def _novo(nome, base="http://ckan-a:5000", aud=None, token=None):
    return PerfilCkanIn(nome=nome, base_url=base, auditoria_base_url=aud, auditoria_api_token=token)


def test_seed_cria_perfil_docker_selecionado():
    with SessionLocal() as db:
        service.semear_perfil_docker(db)
        service.semear_perfil_docker(db)  # idempotente
        perfis = service.listar(db)
    assert [p.nome for p in perfis] == [service.NOME_PERFIL_DOCKER]
    docker = perfis[0]
    assert docker.selecionado is True
    assert docker.base_url == CKAN_LOCAL_DOCKER and docker.auditoria_base_url == CKAN_LOCAL_DOCKER


def test_primeiro_perfil_entra_em_uso_e_troca_atualiza_tudo():
    with SessionLocal() as db:
        a = service.criar(db, _novo("CKAN A", base="http://ckan-a:5000", aud="http://aud-a:5000",
                                     token="tok-a"), None)
        b = service.criar(db, _novo("CKAN B", base="http://ckan-b:5000"), None)
    assert a.selecionado is True and b.selecionado is False  # o 1º criado já fica em uso
    # A troca vale na hora e sobrepõe o .env: config_ativa reflete o perfil selecionado.
    assert service.config_ativa().base_url == "http://ckan-a:5000"
    assert service.config_ativa().auditoria_base_url == "http://aud-a:5000"
    assert service.config_ativa().auditoria_token == "tok-a"
    assert service.cliente_auditoria().base_url == "http://aud-a:5000"
    assert service.cliente_leitura().base_url == "http://ckan-a:5000"
    with SessionLocal() as db:
        service.selecionar(db, b.id, None)
    assert service.config_ativa().base_url == "http://ckan-b:5000"
    # auditoria sem URL própria cai para a base_url do perfil
    assert service.config_ativa().auditoria_base_url == "http://ckan-b:5000"
    assert service.config_ativa().auditoria_token is None


def test_token_e_cifrado_e_nunca_exposto():
    with SessionLocal() as db:
        p = service.criar(db, _novo("Com token", token="super-secreto-123"), None)
    assert p.tem_token is True and p.auditoria_api_token_dica == "••••-123"
    assert "super-secreto-123" not in p.model_dump_json()  # token em claro não sai no schema
    # Mantém o token quando api_token vem None; remove quando vem "".
    with SessionLocal() as db:
        mantido = service.atualizar(db, p.id, _novo("Com token", token=None), None)
        assert mantido.tem_token is True
        removido = service.atualizar(db, p.id, _novo("Com token", token=""), None)
        assert removido.tem_token is False


def test_nome_em_uso_e_regras_de_exclusao():
    with SessionLocal() as db:
        a = service.criar(db, _novo("CKAN A"), None)
        with pytest.raises(service.NomeEmUso):
            service.criar(db, _novo("CKAN A", base="http://outro:5000"), None)
        with pytest.raises(service.NomeEmUso):  # não dá para excluir o perfil em uso
            service.excluir(db, a.id, None)
        b = service.criar(db, _novo("CKAN B"), None)
        service.excluir(db, b.id, None)  # não selecionado: pode excluir
        assert [p.nome for p in service.listar(db)] == ["CKAN A"]


def test_config_ativa_sem_perfil_cai_para_o_env():
    cfg = service.config_ativa()  # nenhum perfil criado neste teste
    assert cfg.base_url == CKAN_LOCAL_DOCKER  # ambiente dev → Docker local
    assert cfg.auditoria_base_url == CKAN_LOCAL_DOCKER  # auditoria vazia → base_url


def test_api_exige_permissao_de_gestao(client, admin, gerente):
    assert client.get(URL, headers=gerente).status_code == 403  # gerente não gerencia CKAN
    r = client.get(URL, headers=admin)
    assert r.status_code == 200
