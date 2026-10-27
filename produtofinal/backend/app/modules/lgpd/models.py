"""Módulo LGPD (Eixo 2): achados, decisões, varreduras e anonimização.

Não retenção (PBI-35): o achado guarda LOCALIZAÇÃO (recurso, coluna, linha) e o tipo, nunca o
valor encontrado. A cópia do original para reversão (PBI-94) vive fora do banco, com prazo de
retenção definido pela GEDA. Identidade, exclusão lógica e auditoria vêm da `Base` (ADR-0019).
"""
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, utcnow


class Achado(Base):
    """Possível dado pessoal localizado num recurso (local e tipo, nunca o valor)."""

    __tablename__ = "lgpd_achado"

    recurso_id: Mapped[int] = mapped_column(ForeignKey("recurso.id"), index=True)
    coluna: Mapped[str] = mapped_column(String(300))
    linha: Mapped[int | None] = mapped_column(Integer, nullable=True)  # primeira ocorrência
    ocorrencias: Mapped[int] = mapped_column(Integer, default=1)
    tipo: Mapped[str] = mapped_column(String(40))                     # cpf, email, nome...
    metodo: Mapped[str] = mapped_column(String(20))                   # regra | ia
    confianca: Mapped[int] = mapped_column(Integer)                   # 0–100 (PBI-86)
    prioridade: Mapped[str] = mapped_column(String(10))               # Alta | Média | Baixa
    status: Mapped[str] = mapped_column(String(20), default="revisar")  # revisar|confirmado|falso_positivo|tratado
    impressao_digital: Mapped[str] = mapped_column(String(64), index=True)  # evita reapresentar (PBI-41)
    # Trilha do score (padrão, validação, contexto, entrada no modelo) — nunca o valor encontrado
    explicacao: Mapped[str | None] = mapped_column(Text, nullable=True)


class Varredura(Base):
    """Execução da varredura LGPD em um recurso (pedida na tela ou pelo job), com totais e erro."""

    __tablename__ = "lgpd_varredura"

    recurso_id: Mapped[int] = mapped_column(ForeignKey("recurso.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pendente")  # pendente|executando|ok|erro|ignorado|cancelada
    origem: Mapped[str] = mapped_column(String(20), default="manual")     # manual|agendada
    solicitada_por: Mapped[str | None] = mapped_column(String(200), nullable=True)
    solicitada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    iniciada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finalizada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    linhas_analisadas: Mapped[int] = mapped_column(Integer, default=0)
    chamadas_ia: Mapped[int] = mapped_column(Integer, default=0)
    achados: Mapped[int] = mapped_column(Integer, default=0)
    modelo: Mapped[str | None] = mapped_column(String(300), nullable=True)  # perfis usados
    aviso: Mapped[str | None] = mapped_column(Text, nullable=True)   # etapa pulada (ex.: sem filtro)
    erro: Mapped[str | None] = mapped_column(Text, nullable=True)


class DecisaoTriagem(Base):
    """Histórico imutável das decisões humanas (PBI-42)."""

    __tablename__ = "lgpd_decisao"

    achado_id: Mapped[int] = mapped_column(ForeignKey("lgpd_achado.id"), index=True)
    decisao: Mapped[str] = mapped_column(String(20))
    justificativa: Mapped[str | None] = mapped_column(Text, nullable=True)
    usuario: Mapped[str] = mapped_column(String(200))
    momento: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CorrecaoPublicada(Base):
    """Anonimização de um recurso (US26, PBI-91 a PBI-94): prévia, aprovação, publicação e reversão.

    Os arquivos (cópia do original e versão anonimizada) ficam FORA do banco, em
    `GDA_LGPD_ARQUIVOS_DIR`, pela política de retenção da GEDA; aqui só os caminhos e o hash."""

    __tablename__ = "lgpd_correcao"

    recurso_id: Mapped[int] = mapped_column(ForeignKey("recurso.id"), index=True)
    # gerando_previa|previa|publicando|publicada|revertendo|revertida|descartada|erro
    status: Mapped[str] = mapped_column(String(20), default="gerando_previa")
    solicitada_por: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # itens: [{achado_id, tipo, coluna, operador, alcance, ocorrencias, alteradas, linhas_exemplo}]
    # — como anonimizar cada achado confirmado; nunca contém valores (só posições)
    itens: Mapped[list] = mapped_column(JSON, default=list)
    celulas_alteradas: Mapped[int] = mapped_column(Integer, default=0)
    nome_arquivo: Mapped[str | None] = mapped_column(String(500), nullable=True)
    formato: Mapped[str | None] = mapped_column(String(20), nullable=True)
    hash_original: Mapped[str | None] = mapped_column(String(64), nullable=True)  # SHA-256
    caminho_backup: Mapped[str | None] = mapped_column(String(500), nullable=True)
    caminho_previa: Mapped[str | None] = mapped_column(String(500), nullable=True)
    aprovado_por: Mapped[str | None] = mapped_column(String(200), nullable=True)
    aprovado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    justificativa: Mapped[str | None] = mapped_column(Text, nullable=True)
    publicada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revertida_por: Mapped[str | None] = mapped_column(String(200), nullable=True)
    revertida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    motivo_reversao: Mapped[str | None] = mapped_column(Text, nullable=True)
    erro: Mapped[str | None] = mapped_column(Text, nullable=True)
