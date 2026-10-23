"""Contrato JSON do módulo pda (o frontend segue exatamente estes nomes).
Datas em "aaaa-mm-dd"; datetimes em ISO 8601."""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

Vinculo = Literal["resolvido", "pendente", "sem_vinculo"]
FlagPrazo = Literal["vencido", "proximo", ""]


class PlanoIn(BaseModel):
    """Criação manual (sem planilha) e edição de um PDA. O vigente é trocado por
    PUT /planos/{id}/vigente; `definir_vigente` só vale na criação."""

    nome: str = Field(max_length=200)
    vigencia_inicio: date | None = None
    vigencia_fim: date | None = None
    definir_vigente: bool = False


class BaseIn(BaseModel):
    """Inclusão e edição manual de uma base prevista (mesmos campos da planilha).

    `organizacao_id` (id da organização) vazio → órgão identificado pela sigla, como na
    importação. Vínculo com o dataset, em ordem de prioridade: `dataset_id` = id do dataset
    escolhido na busca do formulário; `dataset_id_ckan` = ID do dataset no CKAN, digitado
    (ADR-0006: serve para quando o nome no PDA difere do name no portal; precisa existir no
    inventário e não pode divergir do endereço); `dataset_link` = endereço do dataset no portal
    (ou só o name), que serve SÓ para achar o ID (PBI-13). Todos vazios → sem vínculo."""

    orgao_sigla: str = Field(max_length=100)
    organizacao_id: int | None = None
    nome_previsto: str = Field(max_length=500)
    descricao: str | None = None
    unidade_responsavel: str | None = Field(default=None, max_length=500)
    periodicidade: str | None = Field(default=None, max_length=100)
    prazo_abertura: date | None = None
    politicas_publicas: str | None = Field(default=None, max_length=500)
    possui_conteudo_sigiloso: bool | None = None
    dataset_id: int | None = None
    dataset_link: str | None = Field(default=None, max_length=500)
    dataset_id_ckan: str | None = Field(default=None, max_length=100)


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


class FormularioOut(BaseModel):
    """Opções do formulário de base: organizações do portal (valor = id) e o domínio de
    periodicidade."""

    organizacoes: list[OpcaoOut]
    periodicidades: list[str]


class DatasetOpcaoOut(BaseModel):
    """Dataset do inventário encontrado pela busca do formulário de base."""

    id: int
    id_ckan: str | None
    name: str
    titulo: str
    organizacao_id: int | None
    orgao_nome: str | None
    ativo_no_portal: bool


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
    dataset_id: int | None
    dataset_id_ckan: str | None  # para o link do portal
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
