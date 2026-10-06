"""Rotas do módulo lgpd. Endpoints são adicionados à medida que os PBIs forem implementados.

Permissões (app/core/permissoes.py): lgpd.acessar para ler, lgpd.triar para decidir achados,
lgpd.aprovar_correcao para publicar a anonimização no CKAN (US24/US26).
"""
from fastapi import APIRouter

router = APIRouter()
