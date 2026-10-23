"""Rastreabilidade: eventos de alteração e o registro de cada sincronização (ADR-0009).

Três origens de evento:
- `auditoria_ckan`: atividades da extensão ckanext-dsaudit (datasets, recursos, DataStore), com
  autor e data exatos;
- `comparacao_coletas`: diferenças no cadastro dos órgãos entre duas coletas (a extensão não
  audita órgãos); autor e data das atividades nativas do órgão, quando legíveis;
- `atividade_nativa`: atividade nativa do CKAN em dataset sem registro correspondente da
  extensão (ações em lote na organização, package_patch), com autor e data; o conteúdo só é
  deduzido para a visibilidade.

Tabelas de histórico, somente inserção. `dataset_id` e `organizacao_id` não têm FK: o evento
sobrevive mesmo que o dataset deixe de existir no inventário (ver REFERENCIAS_LOGICAS).
Valores de linhas de arquivos e do DataStore NÃO são gravados (podem conter dado pessoal):
só contagens e nomes de colunas.
"""
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, utcnow


class EventoRastreabilidade(Base):
    """Item da linha do tempo: alteração em dataset, recurso ou cadastro de órgão."""

    __tablename__ = "rastreabilidade_evento"
    # Uma atividade pode gerar mais de um evento (ex.: privação + alteração de título na mesma
    # gravação viram Privação e Alteração); `sequencia` distingue as partes.
    __table_args__ = (UniqueConstraint("ckan_activity_id", "sequencia"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    # auditoria_ckan | comparacao_coletas | atividade_nativa
    origem: Mapped[str] = mapped_column(String(30), default="auditoria_ckan")
    # origens auditoria_ckan e atividade_nativa: atividade no CKAN e parte dela
    ckan_activity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sequencia: Mapped[int] = mapped_column(Integer, default=0)  # 0, 1... dentro da atividade
    # origem comparacao_coletas: fotografia do órgão em que a diferença foi detectada
    orgao_snapshot_id: Mapped[int | None] = mapped_column(
        ForeignKey("rastreabilidade_orgao_snapshot.id"), nullable=True, unique=True)
    ocorrido_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    # inclusao | alteracao | exclusao | privacao | recurso_atualizado
    tipo: Mapped[str] = mapped_column(String(30), index=True)
    activity_type: Mapped[str] = mapped_column(String(40))  # tipo da atividade no CKAN
    # vazios em eventos do cadastro do órgão
    dataset_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    dataset_titulo: Mapped[str | None] = mapped_column(String(500), nullable=True)  # na data do evento
    organizacao_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    recurso_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    recurso_nome: Mapped[str | None] = mapped_column(String(500), nullable=True)
    usuario: Mapped[str | None] = mapped_column(String(200), nullable=True)  # usuário do CKAN
    resumo: Mapped[str] = mapped_column(Text)  # frase em linguagem humana (PBI-85)
    detalhes: Mapped[list] = mapped_column(JSON, default=list)  # itens exibíveis do evento
    # há diff linha a linha no CKAN; a tela o busca sob demanda (valores não são gravados aqui)
    tem_diff: Mapped[bool] = mapped_column(Boolean, default=False)
    sincronizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SincronizacaoRastreabilidade(Base):
    """Execução da leitura da auditoria do CKAN, com totais e eventual erro."""

    __tablename__ = "rastreabilidade_sincronizacao"

    id: Mapped[int] = mapped_column(primary_key=True)
    iniciada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finalizada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="executando")  # executando|ok|erro|ignorada
    datasets_consultados: Mapped[int] = mapped_column(Integer, default=0)
    datasets_sem_permissao: Mapped[int] = mapped_column(Integer, default=0)
    datasets_nao_encontrados: Mapped[int] = mapped_column(Integer, default=0)
    orgaos_consultados: Mapped[int] = mapped_column(Integer, default=0)
    # atividades nativas de dataset lidas até este instante (próxima leitura parte daqui)
    atividades_nativas_ate: Mapped[datetime | None] = mapped_column(DateTime(timezone=True),
                                                                   nullable=True)
    eventos_novos: Mapped[int] = mapped_column(Integer, default=0)
    erro: Mapped[str | None] = mapped_column(Text, nullable=True)


class OrgaoSnapshot(Base):
    """Fotografia do cadastro de um órgão (título, descrição, imagem, campos extras), gravada só
    quando muda — insumo da comparação entre coletas."""

    __tablename__ = "rastreabilidade_orgao_snapshot"

    id: Mapped[int] = mapped_column(primary_key=True)
    organizacao_id: Mapped[str] = mapped_column(String(64), index=True)  # ID no CKAN
    capturado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)  # False = sumiu da listagem
    hash_conteudo: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON)  # campos achatados: {"title": ..., "extras.x": ...}
