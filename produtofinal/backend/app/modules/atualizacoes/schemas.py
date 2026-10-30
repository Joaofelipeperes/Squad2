"""Contrato JSON da tela Monitoramento de Atualizações (/api/v1/atualizacoes/datasets)."""
from datetime import date, datetime

from pydantic import BaseModel


class OpcaoOut(BaseModel):
    valor: str
    rotulo: str


class AtualizacaoLinhaOut(BaseModel):
    """Um dataset vinculado a uma base do PDA vigente, com a situação de atualização."""

    base_id: int
    dataset_id: int
    dataset_titulo: str
    dataset_name: str | None
    orgao_chave: str
    orgao_sigla: str
    orgao_nome: str | None
    periodicidade: str
    ultima_atualizacao: datetime | None  # maior last_modified dos recursos (nunca metadata_modified)
    ultima_atualizacao_estimada: bool
    dias_desde_atualizacao: int | None
    prazo_esperado: date | None  # última atualização + prazo da periodicidade
    situacao: str


class ResumoAtualizacoesOut(BaseModel):
    """Cartões da tela: contagens sobre todas as linhas do escopo do usuário, sem os filtros."""

    atualizados: int
    atrasados: int
    proximos_do_vencimento: int
    sem_informacao: int  # "Sem informação" + "Sem periodicidade definida"


class OpcoesAtualizacoesOut(BaseModel):
    orgaos: list[OpcaoOut]
    periodicidades: list[str]
    situacoes: list[str]


class AtualizacoesOut(BaseModel):
    plano_nome: str | None  # None = nenhum PDA vigente
    hoje: date
    total: int  # linhas do escopo, antes dos filtros
    resumo: ResumoAtualizacoesOut
    opcoes: OpcoesAtualizacoesOut
    datasets: list[AtualizacaoLinhaOut]
