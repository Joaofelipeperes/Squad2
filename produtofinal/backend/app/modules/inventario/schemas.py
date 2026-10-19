from datetime import datetime

from pydantic import BaseModel


class ColetaOut(BaseModel):
    id: int
    iniciada_em: datetime
    finalizada_em: datetime | None
    status: str
    origem: str
    solicitada_por: str | None
    total_organizacoes: int
    total_datasets: int
    total_recursos: int
    erro: str | None

    model_config = {"from_attributes": True}


# ------------------------------------------------------------------ tela Datasets (PBI-83)
class OpcaoOut(BaseModel):
    valor: str
    rotulo: str


class DatasetOut(BaseModel):
    """Linha da tela Datasets. Recursos válidos = ainda no pacote do dataset e sem dicionário
    de dados. Última atualização = maior `last_modified` dos recursos válidos (nunca o
    `metadata_modified`); `estimada` = sem last_modified, veio da criação do recurso."""

    ckan_id: str
    name: str
    titulo: str
    organizacao_id: str | None
    orgao_nome: str | None
    recursos_validos: int
    formatos: list[str]
    ultima_atualizacao: datetime | None
    ultima_atualizacao_estimada: bool
    metadata_modified: datetime | None  # só informativo: muda com qualquer edição de metadado
    situacao: str  # Publicado | Sem recurso | Fora do portal (situação no portal, não do PDA)


class DatasetsOpcoesOut(BaseModel):
    orgaos: list[OpcaoOut]
    formatos: list[str]
    situacoes: list[str]


class DatasetsOut(BaseModel):
    total: int  # datasets visíveis ao usuário, SEM filtros
    opcoes: DatasetsOpcoesOut
    datasets: list[DatasetOut]


class RecursoOut(BaseModel):
    ckan_id: str
    nome: str | None
    formato: str | None
    url: str | None
    created: datetime | None
    last_modified: datetime | None
    eh_dicionario_dados: bool


class DatasetDetalheOut(DatasetOut):
    descricao: str | None
    metadata_created: datetime | None  # data de publicação no portal
    periodicidade_declarada: str | None  # campo "Atualização" preenchido pelo órgão no CKAN
    licenca: str | None
    recursos: list[RecursoOut]  # recursos atuais (inclui dicionário, marcado)
    recursos_removidos: int  # recursos que já estiveram no dataset e saíram do portal
