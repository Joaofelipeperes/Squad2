"""Consultas e gravações do módulo parametros (ADR-0019)."""
from sqlalchemy import select

from app.core.dao import Dao
from app.modules.parametros.models import Parametro


class ParametrosDao(Dao):
    def parametro(self, chave: str) -> Parametro | None:
        """Valor gravado (ativo) da chave; None = vale o padrão do catálogo."""
        return self.buscar_um(select(Parametro).where(Parametro.chave == chave))

    def gravar(self, chave: str, valor, alterado_por: str | None) -> Parametro:
        p = self.parametro(chave) or Parametro(chave=chave)
        p.valor, p.alterado_por = valor, alterado_por
        self.save_generic(p)
        self.commit()
        return p
