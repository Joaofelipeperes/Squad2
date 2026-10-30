"""Perfis de conexão do CKAN e resolução do CKAN em uso (ADR-0024).

O perfil `selecionado` rege todo o sistema e sobrepõe o `.env`. A resolução (`config_ativa`) é lida
do banco a cada construção de cliente, então a troca vale na hora e para todos os processos (API e
worker). Sem nenhum perfil, cai para o `.env` (compatível com quem ainda não usa a tela).
"""
from typing import NamedTuple

from sqlalchemy.orm import Session

from app.core import crypto
from app.core.config import CKAN_LOCAL_DOCKER, get_settings
from app.core.db import SessionLocal
from app.integrations.ckan.client import CkanClient
from app.modules.ckan_config.dao import CkanConfigDao
from app.modules.ckan_config.models import CkanPerfil
from app.modules.ckan_config.schemas import PerfilCkanIn, PerfilCkanOut

NOME_PERFIL_DOCKER = "CKAN Docker"


class PerfilNaoEncontrado(Exception):
    pass


class NomeEmUso(Exception):
    pass


# ------------------------------------------------------------------ resolução do CKAN em uso
class ConfigCkan(NamedTuple):
    base_url: str              # leitura pública (inventário, LGPD)
    auditoria_base_url: str    # auditoria/diff (dsaudit); já resolvido (nunca vazio)
    auditoria_token: str | None


def config_ativa() -> ConfigCkan:
    """CKAN em uso: o perfil selecionado (sobrepõe o `.env`) ou, sem perfil, o `.env`."""
    with SessionLocal() as db:
        perfil = CkanConfigDao(db).selecionado()
    if perfil is not None:
        token = (crypto.decrypt(perfil.auditoria_api_token_cifrada)
                 if perfil.auditoria_api_token_cifrada else None)
        return ConfigCkan(perfil.base_url, perfil.auditoria_base_url or perfil.base_url, token)
    s = get_settings()
    env_token = s.ckan_auditoria_api_token
    token = env_token.get_secret_value().strip() if env_token and env_token.get_secret_value().strip() else None
    return ConfigCkan(s.ckan_base_url, s.ckan_auditoria_base_url or s.ckan_base_url, token)


def cliente_leitura() -> CkanClient:
    """Cliente para a leitura pública (coleta do inventário, download da LGPD)."""
    return CkanClient(base_url=config_ativa().base_url)


def cliente_auditoria() -> CkanClient:
    """Cliente para a auditoria/diff (com a URL e o token do CKAN em uso)."""
    cfg = config_ativa()
    return CkanClient(base_url=cfg.auditoria_base_url, api_token=cfg.auditoria_token)


# ------------------------------------------------------------------ CRUD da tela
def _out(p: CkanPerfil) -> PerfilCkanOut:
    return PerfilCkanOut(
        id=p.id, nome=p.nome, base_url=p.base_url, auditoria_base_url=p.auditoria_base_url,
        tem_token=bool(p.auditoria_api_token_cifrada),
        auditoria_api_token_dica=p.auditoria_api_token_dica,
        selecionado=p.selecionado, atualizado_em=p.changed)


def listar(db: Session) -> list[PerfilCkanOut]:
    return [_out(p) for p in CkanConfigDao(db).listar()]


def _aplicar(perfil: CkanPerfil, dados: PerfilCkanIn) -> None:
    perfil.nome = dados.nome.strip()
    perfil.base_url = dados.base_url.strip().rstrip("/")
    aud = (dados.auditoria_base_url or "").strip().rstrip("/")
    perfil.auditoria_base_url = aud or None
    if dados.auditoria_api_token is not None:  # None = mantém; "" = remove; texto = substitui
        token = dados.auditoria_api_token.strip()
        perfil.auditoria_api_token_cifrada = crypto.encrypt(token) if token else None
        perfil.auditoria_api_token_dica = crypto.hint(token) if token else None


def criar(db: Session, dados: PerfilCkanIn, user) -> PerfilCkanOut:
    dao = CkanConfigDao.de(db, user)
    if dao.por_nome(dados.nome.strip()):
        raise NomeEmUso(f"Já existe um perfil chamado {dados.nome.strip()!r}.")
    perfil = CkanPerfil(selecionado=not dao.existe_algum())  # o 1º criado já entra em uso
    _aplicar(perfil, dados)
    dao.salvar(perfil)
    dao.commit()
    return _out(perfil)


def atualizar(db: Session, perfil_id: int, dados: PerfilCkanIn, user) -> PerfilCkanOut:
    dao = CkanConfigDao.de(db, user)
    perfil = dao.por_id(perfil_id)
    if perfil is None:
        raise PerfilNaoEncontrado("Perfil não encontrado.")
    outro = dao.por_nome(dados.nome.strip())
    if outro is not None and outro.id != perfil.id:
        raise NomeEmUso(f"Já existe um perfil chamado {dados.nome.strip()!r}.")
    _aplicar(perfil, dados)
    dao.salvar(perfil)
    dao.commit()
    return _out(perfil)


def excluir(db: Session, perfil_id: int, user) -> None:
    dao = CkanConfigDao.de(db, user)
    perfil = dao.por_id(perfil_id)
    if perfil is None:
        raise PerfilNaoEncontrado("Perfil não encontrado.")
    if perfil.selecionado:
        raise NomeEmUso("Não é possível excluir o perfil em uso; selecione outro antes.")
    dao.excluir(perfil)
    dao.commit()


def selecionar(db: Session, perfil_id: int, user) -> PerfilCkanOut:
    """Troca o CKAN em uso. Vale na hora para todo o sistema; não apaga dados já coletados."""
    dao = CkanConfigDao.de(db, user)
    perfil = dao.por_id(perfil_id)
    if perfil is None:
        raise PerfilNaoEncontrado("Perfil não encontrado.")
    dao.limpar_selecao()
    perfil.selecionado = True
    dao.salvar(perfil)
    dao.commit()
    return _out(perfil)


# ------------------------------------------------------------------ seed inicial
def semear_perfil_docker(db: Session) -> None:
    """Na primeira subida, grava as configurações do CKAN local do Docker como o perfil em uso."""
    dao = CkanConfigDao(db)
    if dao.existe_algum():
        return
    s = get_settings()
    env_token = s.ckan_auditoria_api_token
    token = env_token.get_secret_value().strip() if env_token else ""
    perfil = CkanPerfil(
        nome=NOME_PERFIL_DOCKER, base_url=CKAN_LOCAL_DOCKER, auditoria_base_url=CKAN_LOCAL_DOCKER,
        auditoria_api_token_cifrada=crypto.encrypt(token) if token else None,
        auditoria_api_token_dica=crypto.hint(token) if token else None, selecionado=True)
    dao.salvar(perfil)
    dao.commit()
