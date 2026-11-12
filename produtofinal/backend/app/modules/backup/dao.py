"""Consultas e gravações do módulo backup (ADR-0019)."""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import undefer

from app.core.dao import Dao
from app.modules.backup.models import BackupCopia


class BackupDao(Dao):
    def por_referencia(self, tipo: str, referencia: str) -> BackupCopia | None:
        return self.buscar_um(select(BackupCopia).where(BackupCopia.tipo == tipo,
                                                        BackupCopia.referencia == referencia))

    def listar(self, tipo: str | None = None, limite: int = 500) -> list[BackupCopia]:
        """Cópias ativas, da mais recente para a mais antiga (sem carregar o conteúdo)."""
        stmt = select(BackupCopia).order_by(BackupCopia.iniciado_em.desc(),
                                            BackupCopia.id.desc()).limit(limite)
        if tipo:
            stmt = stmt.where(BackupCopia.tipo == tipo)
        return self.buscar_lista(stmt)

    def com_conteudo(self, id_: int) -> BackupCopia | None:
        """Cópia ativa já com o conteúdo cifrado carregado."""
        return self.buscar_um(select(BackupCopia).options(undefer(BackupCopia.conteudo))
                              .where(BackupCopia.id == id_))

    def gravar(self, copia: BackupCopia) -> BackupCopia:
        self.save_generic(copia)
        self.commit()
        return copia

    def expirar_vencidos(self, agora: datetime) -> int:
        """Exclusão lógica dos vencidos, liberando o conteúdo (é o que ocupa espaço)."""
        n = self.update_generic(BackupCopia, BackupCopia.expira_em < agora,
                                deleted=True, conteudo=None)
        self.commit()
        return n
