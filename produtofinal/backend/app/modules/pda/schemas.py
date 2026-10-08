"""Contrato JSON do módulo pda (o frontend segue exatamente estes nomes).
Datas em "aaaa-mm-dd"; datetimes em ISO 8601."""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

Vinculo = Literal["resolvido", "pendente", "sem_vinculo"]
FlagPrazo = Literal["vencido", "proximo", ""]


class PlanoOut(BaseModel):
    id: int
    nome: str
    vigencia_inicio: date | None
    vigencia_fim: date | None
    vigente: bool
    arquivo_nome: str | None
    importado_por: str | None
    importado_em: datetime
    total_bases: int
    vinculos_resolvidos: int
    vinculos_pendentes: int


class LinhaIgnoradaOut(BaseModel):
    linha: int
    motivo: str


class ImportacaoResumoOut(BaseModel):
    plano: PlanoOut
    bases_importadas: int
    linhas_ignoradas: list[LinhaIgnoradaOut]
    vinculos_resolvidos: int
    vinculos_pendentes: int
    sem_vinculo: int
    orgaos_sem_correspondencia: list[str]
    tem_coluna_prazo: bool  # sem a coluna "Prazo", as bases não publicadas ficam "Não publicado"
    tem_coluna_portal: bool  # sem "Disponível no Portal", nenhuma base é vinculada na importação
    colunas_opcionais_ausentes: list[str]  # rótulos das colunas opcionais não encontradas


class VinculosOut(BaseModel):
    vinculos_resolvidos: int  # resolvidos NESTA execução
    vinculos_pendentes: int   # que continuam pendentes após a execução


class OpcaoOut(BaseModel):
    valor: str
    rotulo: str


class OpcoesOut(BaseModel):
    orgaos: list[OpcaoOut]
    periodicidades: list[str]
    anos: list[int]


class BaseOut(BaseModel):
    id: int
    plano_id: int
    plano_nome: str
    orgao_sigla: str
    orgao_chave: str
    orgao_nome: str | None
    nome_previsto: str
    descricao: str | None
    unidade_responsavel: str | None
    periodicidade: str
    periodicidade_original: str | None
    politicas_publicas: str | None
    possui_conteudo_sigiloso: bool | None
    prazo_abertura: date | None
    vinculo: Vinculo
    dataset_id: str | None
    dataset_name: str | None
    dataset_titulo: str | None
    dataset_name_planilha: str | None
    dataset_ativo: bool | None
    data_publicacao: datetime | None  # metadata_created do dataset vinculado e ativo
    recursos_validos: int
    formatos: list[str]  # formatos dos recursos válidos (sem dicionário), sem repetição
    ultima_atualizacao: datetime | None
    ultima_atualizacao_estimada: bool
    situacao: str
    flag_prazo: FlagPrazo
    classificacao: str

    model_config = {"from_attributes": True}


class BasesOut(BaseModel):
    plano: PlanoOut | None
    hoje: date
    janela_alerta_dias: int
    total_previstas: int  # bases do plano visíveis ao usuário, SEM filtros
    opcoes: OpcoesOut
    bases: list[BaseOut]
