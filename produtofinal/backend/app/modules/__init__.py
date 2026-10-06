"""Registro dos módulos do backend. A ordem aqui é a ordem das rotas na documentação da API."""
import importlib

from app.core.module import BackendModule

INSTALLED_MODULES: list[str] = [
    "acesso",          # US24 — login, usuários, papéis e permissões
    "inventario",      # US5, US23 — coleta diária CKAN (base comum)
    "pda",             # US6, US7, US8 — vínculo PDA×CKAN e prazos de abertura (Eixo 1)
    "atualizacoes",    # US9, US10 — atualização real e periodicidade (Eixo 1)
    "lgpd",            # US11–US13, US26, US27 — dados pessoais e anonimização (Eixo 2)
    "metadados",       # US16, US17 — metadados obrigatórios e formatos (Eixo 2 / Eixo 3)
    "rastreabilidade", # US14, US29 — linha do tempo de mudanças (Eixo 1)
    "painel",          # US19 — visão geral e organizações
    "relatorios",      # US20 — exportações XLSX/CSV
    "assistente",      # US28 — Assistente GEDA
    "envio",           # área do órgão publicador (NÃO comprometido — ver docs/modulos/envio.md)
    "ia",              # configuração de provedores e modelos de IA
    "parametros",      # parâmetros de negócio editáveis pela GEDA
]


def load_modules() -> list[BackendModule]:
    return [importlib.import_module(f"app.modules.{name}").module for name in INSTALLED_MODULES]


def import_all_models() -> None:
    """Importa models.py de cada módulo (necessário para o Alembic enxergar as tabelas)."""
    for name in INSTALLED_MODULES:
        try:
            importlib.import_module(f"app.modules.{name}.models")
        except ModuleNotFoundError as exc:
            if exc.name != f"app.modules.{name}.models":
                raise
