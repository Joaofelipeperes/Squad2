"""Acesso ao banco do módulo relatorios (ADR-0019). Só leitura: os dados dos relatórios vêm dos
services dos módulos de origem; aqui só o que eles não devolvem (nome dos órgãos)."""
from sqlalchemy import select

from app.core.dao import Dao
from app.core.deps import UsuarioAtual, filtrar_por_orgao
from app.modules.inventario.models import Organizacao


class RelatoriosDao(Dao):
    def organizacoes_visiveis(self, user: UsuarioAtual) -> dict[int, Organizacao]:
        stmt = filtrar_por_orgao(select(Organizacao), Organizacao.id, user)
        return {o.id: o for o in self.buscar_lista(stmt)}
