"""Preparação automática do sistema a cada subida da API (ADR-0032).

No servidor, `docker compose up -d` precisa deixar o sistema pronto para uso, sem comandos à mão.
A API chama `preparar` ao iniciar, depois das migrações (o comando do container roda o alembic
antes do uvicorn). Tudo é idempotente e só cria o que falta, nunca sobrescreve o que foi ajustado
nas telas:

- papéis padrão (no servidor, só os de `GDA_PAPEIS_INICIAIS`: administrador e gerente_geda);
- administrador inicial, se o banco não tem nenhum usuário (`GDA_ADMIN_INICIAL_*`);
- perfil do CKAN lido (portal oficial em produção), se não há nenhum perfil;
- perfis de IA local do Ollama e vínculo da varredura LGPD, se não há nenhum perfil de IA
  (`GDA_IA_LOCAL_URL`).

Os Parâmetros não precisam de semente: sem valor gravado vale o padrão do catálogo
(`modules/parametros/catalogo.py`), e o que a GEDA altera na tela passa a valer.
A primeira coleta do CKAN é do worker (`inventario.service.job_coleta_inicial`).
"""
import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings

log = logging.getLogger(__name__)


def preparar(db: Session) -> None:
    from app.modules.acesso.service import semear_admin_inicial, sincronizar_papeis_padrao
    from app.modules.ckan_config.service import semear_perfil_inicial

    sincronizar_papeis_padrao(db)
    semear_admin_inicial(db)
    semear_perfil_inicial(db)
    _semear_ia_local(db)


def _semear_ia_local(db: Session) -> None:
    from app.modules.ia import service

    s = get_settings()
    if not s.ia_local_url or service.listar_perfis(db):
        return
    for linha in service.configurar_ia_local(db, s.ia_local_url, s.ia_local_modelo_chat,
                                             s.ia_local_modelo_embeddings, "instalacao"):
        log.info("IA local: %s", linha)
