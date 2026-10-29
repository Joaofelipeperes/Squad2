from datetime import datetime

from pydantic import BaseModel


class OpcaoOut(BaseModel):
    valor: str
    rotulo: str


class DetalheOut(BaseModel):
    """Item exibível do evento: campo com valor anterior → novo, ou uma contagem."""

    escopo: str | None = None
    recurso: str | None = None
    situacao: str | None = None
    campo: str
    anterior: str | None = None
    novo: str | None = None


class EventoOut(BaseModel):
    id: int
    ocorrido_em: datetime
    tipo: str          # código (inclusao, alteracao, ...)
    tipo_rotulo: str   # rótulo da tela (Inclusão, Alteração, ...)
    origem: str        # auditoria_ckan | comparacao_coletas (cadastro do órgão)
    dataset_id_ckan: str | None      # vazio em evento do cadastro do órgão
    dataset_titulo: str | None
    organizacao_id: int | None       # `id` do órgão no inventário (vazio se não estiver lá)
    organizacao_id_ckan: str | None
    orgao_nome: str | None
    recurso_id_ckan: str | None
    recurso_nome: str | None
    usuario: str | None
    resumo: str
    detalhes: list[DetalheOut]
    tem_diff: bool  # há diff linha a linha no CKAN (GET /eventos/{id}/diff)


class SincronizacaoOut(BaseModel):
    id: int
    iniciada_em: datetime
    finalizada_em: datetime | None
    status: str
    datasets_consultados: int
    datasets_sem_permissao: int
    datasets_nao_encontrados: int
    orgaos_consultados: int
    eventos_novos: int
    erro: str | None

    model_config = {"from_attributes": True}


class EventosOpcoesOut(BaseModel):
    tipos: list[OpcaoOut]
    orgaos: list[OpcaoOut]


class EventosOut(BaseModel):
    total: int            # eventos que atendem aos filtros (antes do limite)
    exibidos: int
    opcoes: EventosOpcoesOut
    sincronizacao: SincronizacaoOut | None  # última leitura da auditoria do CKAN
    eventos: list[EventoOut]


class DiffCampoOut(BaseModel):
    campo: str
    anterior: str | None
    novo: str | None


class DiffLinhaOut(BaseModel):
    chave: str      # ex.: "id=12" (coluna de valores únicos) ou "linha=5"
    situacao: str   # incluída | alterada | removida
    campos: list[DiffCampoOut]


class DiffOut(BaseModel):
    """Diff linha a linha lido do CKAN na hora da consulta (não é gravado na solução)."""

    evento_id: int
    recurso_nome: str | None
    arquivo_anterior: str | None
    arquivo_novo: str | None
    versao_anterior: int | None
    versao_nova: int | None
    colunas_chave: list[str]
    total_linhas: int          # linhas diferentes na auditoria
    linhas: list[DiffLinhaOut]  # até 500
