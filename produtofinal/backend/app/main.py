"""Aplicação FastAPI. Rotas montadas a partir do registro de módulos (app/modules/__init__.py).

Na subida, cada rota é inspecionada: se não declarar controle de acesso (publico, autenticado,
require ou require_qualquer — ver app/core/deps.py), a aplicação NÃO inicia.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

import app.integrations.ai  # noqa: F401  registra os adaptadores de IA
from app.core.config import get_settings
from app.core.deps import controle_de_acesso, publico
from app.core.module import BackendModule
from app.modules import load_modules

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

    try:
        with SessionLocal() as db:
            sincronizar_papeis_padrao(db)
    except Exception:  # noqa: BLE001 — banco ainda sem migração: não impede a subida
        logging.getLogger(__name__).warning("Papéis padrão não sincronizados (rode o alembic).")
    yield


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title=s.app_name, version="0.2.0", lifespan=lifespan,
                  docs_url=f"{s.api_prefix}/docs", openapi_url=f"{s.api_prefix}/openapi.json")
    app.add_middleware(CORSMiddleware, allow_origins=s.cors_origins, allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])

    modulos = load_modules()
    verificar_controle_de_acesso(modulos)
    for m in modulos:
        if m.router is not None:
            app.include_router(m.router, prefix=f"{s.api_prefix}{m.prefix}", tags=m.tags)

    @app.get(f"{s.api_prefix}/saude", tags=["Sistema"], dependencies=[Depends(publico)])
    def saude():
        return {"status": "ok", "ambiente": s.environment,
                "modulos": [{"nome": m.name, "user_stories": m.user_stories} for m in modulos]}

    return app


app = create_app()
