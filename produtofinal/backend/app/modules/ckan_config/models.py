"""Perfis de conexão com o CKAN (ADR-0024). Um perfil fica `selecionado` e rege TODO o sistema
(leitura do inventário/LGPD e auditoria/diff da rastreabilidade), sobrepondo o que está no `.env`
(`GDA_CKAN_*` / `GDA_ENVIRONMENT`). Trocar o perfil NÃO apaga nada já coletado (inventário,
eventos, achados): só muda de qual CKAN o sistema lê a partir dali.
"""
from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, unico_entre_ativos


class CkanPerfil(Base):
    """Perfil de conexão com um CKAN. Um fica `selecionado` e rege todo o sistema (sobrepõe o
    `.env`); trocar de perfil não apaga os dados já coletados (ADR-0024)."""

    __tablename__ = "ckan_perfil"
    __table_args__ = (unico_entre_ativos("ckan_perfil", "nome"),)

    nome: Mapped[str] = mapped_column(String(120))
    # Leitura pública (coleta do inventário e download de recursos pela LGPD).
    base_url: Mapped[str] = mapped_column(String(500))
    # Leitura da auditoria/diff (dsaudit). Vazio = usa a `base_url`.
    auditoria_base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Token de editor para a auditoria (cifrado em repouso; `dica` é só para exibição).
    auditoria_api_token_cifrada: Mapped[str | None] = mapped_column(Text, nullable=True)
    auditoria_api_token_dica: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # O CKAN em uso agora. No máximo um perfil com `selecionado=True`.
    selecionado: Mapped[bool] = mapped_column(Boolean, default=False)
