"""Inventário espelhado do CKAN (base comum a todos os eixos).

Tabelas de "estado atual" (organizacao, dataset, recurso) + histórico de coletas (coleta) e
fotografia por coleta (dataset_snapshot), que alimenta o diff da rastreabilidade (US14/US29).
Chave primária = ID do CKAN, nunca o `name` (editável pelos órgãos).
"""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, utcnow


class Coleta(Base):
    """Execução da coleta do CKAN (agendada ou manual), com totais e eventual erro."""

    __tablename__ = "coleta"

    id: Mapped[int] = mapped_column(primary_key=True)
    iniciada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finalizada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="executando")  # executando|ok|erro
    origem: Mapped[str] = mapped_column(String(20), default="agendada")    # agendada|manual
    solicitada_por: Mapped[str | None] = mapped_column(String(200), nullable=True)
    total_organizacoes: Mapped[int] = mapped_column(Integer, default=0)
    total_datasets: Mapped[int] = mapped_column(Integer, default=0)
    total_recursos: Mapped[int] = mapped_column(Integer, default=0)
    erro: Mapped[str | None] = mapped_column(Text, nullable=True)


class Organizacao(Base):
    """Órgão publicador espelhado do CKAN (organization)."""

    __tablename__ = "organizacao"

    ckan_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    titulo: Mapped[str] = mapped_column(String(300))
    sigla: Mapped[str | None] = mapped_column(String(40), nullable=True)
    ultima_coleta_id: Mapped[int | None] = mapped_column(ForeignKey("coleta.id"), nullable=True)


class Dataset(Base):
    """Conjunto de dados espelhado do CKAN (package), no estado da última coleta."""

    __tablename__ = "dataset"

    ckan_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    titulo: Mapped[str] = mapped_column(String(500))
    organizacao_id: Mapped[str | None] = mapped_column(ForeignKey("organizacao.ckan_id"),
                                                       nullable=True, index=True)
    autor: Mapped[str | None] = mapped_column(String(300), nullable=True)
    autor_email: Mapped[str | None] = mapped_column(String(300), nullable=True)
    licenca: Mapped[str | None] = mapped_column(String(100), nullable=True)
    periodicidade_declarada: Mapped[str | None] = mapped_column(String(100), nullable=True)
    metadata_created: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # metadata_modified é guardado apenas como informação — NÃO é indicador de atualização
    metadata_modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    extras: Mapped[dict] = mapped_column(JSON, default=dict)  # metadados customizados (PBI-08)
    ativo_no_portal: Mapped[bool] = mapped_column(Boolean, default=True)
    ultima_coleta_id: Mapped[int | None] = mapped_column(ForeignKey("coleta.id"), nullable=True)

    recursos: Mapped[list["Recurso"]] = relationship(back_populates="dataset",
                                                     cascade="all, delete-orphan")


class Recurso(Base):
    """Arquivo ou link de um dataset (resource); last_modified é o indicador de atualização."""

    __tablename__ = "recurso"

    ckan_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("dataset.ckan_id"), index=True)
    nome: Mapped[str | None] = mapped_column(String(500), nullable=True)
    formato: Mapped[str | None] = mapped_column(String(40), nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    url_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # upload | link(None)
    created: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    datastore_active: Mapped[bool] = mapped_column(Boolean, default=False)
    eh_dicionario_dados: Mapped[bool] = mapped_column(Boolean, default=False)  # PBI-11
    ultima_coleta_id: Mapped[int | None] = mapped_column(ForeignKey("coleta.id"), nullable=True)

    dataset: Mapped[Dataset] = relationship(back_populates="recursos")


class DatasetSnapshot(Base):
    """Fotografia compacta de um dataset em uma coleta — insumo do diff entre coletas."""

    __tablename__ = "dataset_snapshot"

    id: Mapped[int] = mapped_column(primary_key=True)
    coleta_id: Mapped[int] = mapped_column(ForeignKey("coleta.id"), index=True)
    dataset_id: Mapped[str] = mapped_column(String(64), index=True)
    hash_conteudo: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON)
