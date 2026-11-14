"""Contrato JSON da tela Monitoramento de Atualizações (/api/v1/atualizacoes/datasets)."""
from datetime import date, datetime

from pydantic import BaseModel


class OpcaoOut(BaseModel):
    valor: str
    rotulo: str


class AtualizacaoLinhaOut(BaseModel):
    """Um dataset publicado no portal (previsto no PDA ou espontâneo) com a situação de
    atualização pela periodicidade declarada no CKAN (ADR-0037)."""

    dataset_id: int
    dataset_titulo: str
    dataset_name: str | None
    orgao_chave: str  # id da organização (texto) ou "sem_orgao"
    orgao_sigla: str
    orgao_nome: str | None
    tipo_base: str  # "Prevista no PDA" | "Espontânea" (ADR-0026)
    periodicidade_declarada: str | None  # campo "Atualização" do CKAN, como o órgão preencheu
    periodicidade: str  # valor do domínio, "Sem atualização periódica" ou "Periodicidade não informada"
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
    sem_atualizacao_periodica: int  # declarado "Não possui atualização periódica" (válido)
    periodicidade_nao_informada: int  # campo "Atualização" vazio ou inválido (não conforme)
    sem_data: int  # periodicidade válida, sem recurso válido com data
    previstas_no_pda: int
    espontaneas: int


class OpcoesAtualizacoesOut(BaseModel):
    orgaos: list[OpcaoOut]
    periodicidades: list[str]
    situacoes: list[str]
    tipos_base: list[str]


class AtualizacoesOut(BaseModel):
    plano_nome: str | None  # PDA vigente que define o tipo de base; None = nenhum
    hoje: date
    total: int  # linhas do escopo, antes dos filtros
    resumo: ResumoAtualizacoesOut
    opcoes: OpcoesAtualizacoesOut
    datasets: list[AtualizacaoLinhaOut]
