"""Aplicação FastAPI. Rotas montadas a partir do registro de módulos (app/modules/__init__.py).

Na subida, cada rota é inspecionada: se não declarar controle de acesso (publico, autenticado,
require ou require_qualquer — ver app/core/deps.py), a aplicação NÃO inicia.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute
from starlette.concurrency import run_in_threadpool

import app.integrations.ai  # noqa: F401  registra os adaptadores de IA
from app.core.config import get_settings
from app.core.deps import controle_de_acesso, publico
from app.core.module import BackendModule
from app.modules import load_modules
from app.modules.acesso.service import registrar_acesso

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


class RotaSemControleDeAcesso(RuntimeError):
    pass


def verificar_controle_de_acesso(modulos: list[BackendModule]) -> None:
    sem_controle = [
        f"{','.join(sorted(r.methods))} {m.prefix}{r.path} (módulo {m.name})"
        for m in modulos if m.router
        for r in m.router.routes if isinstance(r, APIRoute) and controle_de_acesso(r) is None
    ]
    if sem_controle:
        raise RotaSemControleDeAcesso(
            "Rotas sem controle de acesso (use require(P.X), autenticado ou publico):\n  "
            + "\n  ".join(sem_controle))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from app.core.db import SessionLocal
    from app.modules.acesso.service import sincronizar_papeis_padrao
    from app.modules.ckan_config.service import semear_perfil_docker

    try:
        with SessionLocal() as db:
            sincronizar_papeis_padrao(db)
            semear_perfil_docker(db)  # 1ª subida: grava o CKAN do Docker como perfil em uso
    except Exception:  # noqa: BLE001 — banco ainda sem migração: não impede a subida
        logging.getLogger(__name__).warning("Papéis padrão não sincronizados (rode o alembic).")
    yield


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title=s.app_name, version="0.2.0", lifespan=lifespan,
                  docs_url=f"{s.api_prefix}/docs", openapi_url=f"{s.api_prefix}/openapi.json")
    app.add_middleware(CORSMiddleware, allow_origins=s.cors_origins, allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])

    rota_completa: dict = {}  # endpoint → /api/v1/<modulo>/...; scope["route"] vem sem o prefixo

    @app.middleware("http")
    async def log_de_acesso(request: Request, call_next):
        """Uma linha em `acesso_log` por requisição (ADR-0016). O e-mail vem de
        `get_current_user` ou do login, que gravam em `request.state.usuario`."""
        if request.method == "OPTIONS" or request.url.path == f"{s.api_prefix}/saude":
            return await call_next(request)
        request.state.usuario = None  # cria o state antes das rotas: elas escrevem no mesmo dict
        status_http = 500  # exceção não tratada
        try:
            resposta = await call_next(request)
            status_http = resposta.status_code
            return resposta
        finally:
            endpoint = request.scope.get("endpoint")
            consulta = f"?{request.url.query}" if request.url.query else ""
            await run_in_threadpool(
                registrar_acesso, usuario=request.state.usuario, metodo=request.method,
                caminho=(request.url.path + consulta)[:500], rota=rota_completa.get(endpoint),
                acao=getattr(endpoint, "__name__", None), status_http=status_http,
                ip=request.client.host if request.client else None,
                user_agent=(request.headers.get("user-agent") or "")[:500] or None)

    modulos = load_modules()
    verificar_controle_de_acesso(modulos)
    for m in modulos:
        if m.router is not None:
            app.include_router(m.router, prefix=f"{s.api_prefix}{m.prefix}", tags=m.tags)
    rota_completa.update({r.endpoint: f"{s.api_prefix}{m.prefix}{r.path}" for m in modulos
                          if m.router for r in m.router.routes if isinstance(r, APIRoute)})

    @app.get(f"{s.api_prefix}/saude", tags=["Sistema"], dependencies=[Depends(publico)])
    def saude():
        return {"status": "ok", "ambiente": s.environment, "ckan": s.ckan_base_url,
                "modulos": [{"nome": m.name, "user_stories": m.user_stories} for m in modulos]}

    return app


app = create_app()
