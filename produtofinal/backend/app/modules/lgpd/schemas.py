from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class OpcaoOut(BaseModel):
    valor: str
    rotulo: str


class KpisOut(BaseModel):
    """Os 4 indicadores do topo da tela (Protótipo V1), no escopo de órgão do usuário."""

    recursos_analisados: int      # recursos com varredura concluída
    recursos_com_achados: int     # recursos com achado que não foi descartado como falso positivo
    alertas_criticos: int         # achados de prioridade Alta aguardando revisão
    alertas_para_revisao: int     # achados com status "revisar"


class ContagemOut(BaseModel):
    rotulo: str
    total: int


class ResumoDadosPessoaisOut(BaseModel):
    """Resumo agregado dos achados para o Dashboard (só contagens, nunca valores — PBI-35), no
    escopo de órgão do usuário."""

    recursos_analisados: int  # recursos com varredura concluída
    recursos_com_achados: int  # recursos com achado que não foi descartado como falso positivo
    aguardando_revisao: int  # achados com status "revisar"
    criticos: int  # achados de prioridade Alta aguardando revisão
    por_tipo: list[ContagemOut]  # achados que não são falso positivo, por tipo (mais frequente 1º)
    por_status: list[ContagemOut]  # achados por status da triagem (ordem de regras.STATUS)


class AchadoOut(BaseModel):
    id: int
    prioridade: str
    orgao_id: int | None
    orgao_sigla: str | None
    orgao_nome: str | None
    dataset_id: int
    dataset_titulo: str
    recurso_id: int
    recurso_nome: str | None
    tipo: str          # código (cpf, email...)
    tipo_rotulo: str   # rótulo da tela (CPF, E-mail...)
    coluna: str
    linha: int | None
    ocorrencias: int
    confianca: int
    metodo: str        # regra | ia
    status: str        # revisar | confirmado | falso_positivo | tratado
    atualizado_em: datetime | None


class OpcoesAchadosOut(BaseModel):
    prioridades: list[str]
    tipos: list[OpcaoOut]
    orgaos: list[OpcaoOut]
    status: list[OpcaoOut]


class AchadosOut(BaseModel):
    kpis: KpisOut
    opcoes: OpcoesAchadosOut
    total: int  # achados visíveis ao usuário, sem filtros
    achados: list[AchadoOut]


class DecisaoOut(BaseModel):
    decisao: str
    justificativa: str | None
    usuario: str
    momento: datetime


class AchadoDetalheOut(AchadoOut):
    explicacao: str | None
    recurso_url: str | None
    recurso_formato: str | None
    decisoes: list[DecisaoOut]


class DecisaoIn(BaseModel):
    decisao: Literal["confirmado", "falso_positivo", "tratado", "revisar"]
    justificativa: str | None = Field(default=None, max_length=1000)


class PedidoVarreduraIn(BaseModel):
    """`pendentes` = recursos (CSV/XLSX) nunca varridos ou alterados desde a última varredura."""

    escopo: Literal["pendentes", "dataset", "recurso"]
    id: int | None = None  # `id` do dataset ou do recurso (chave própria, ADR-0018)


class VarreduraOut(BaseModel):
    id: int
    recurso_id: int
    recurso_nome: str | None
    dataset_titulo: str | None
    status: str  # pendente | executando | ok | erro | ignorado | cancelada
    origem: str
    solicitada_por: str | None
    solicitada_em: datetime
    iniciada_em: datetime | None
    finalizada_em: datetime | None
    linhas_analisadas: int
    chamadas_ia: int
    achados: int
    modelo: str | None
    aviso: str | None
    erro: str | None


class PedidoVarreduraOut(BaseModel):
    criadas: int
    ja_na_fila: int
    varreduras: list[VarreduraOut]


class VarredurasOut(BaseModel):
    em_andamento: int
    varreduras: list[VarreduraOut]


# ------------------------------------------------------------------ anonimização (US26)
class CorrecaoItemIn(BaseModel):
    achado_id: int
    operador: Literal["mascara_cpf", "substituir", "mascarar", "hash", "remover"]
    alcance: Literal["detectados", "coluna"] = "detectados"


class CorrecaoIn(BaseModel):
    """Prévia da anonimização de UM recurso, com os achados confirmados que entram nela."""

    recurso_id: int
    itens: list[CorrecaoItemIn] = Field(min_length=1, max_length=50)


class ExemploOut(BaseModel):
    linha: int
    valor: str  # valor JÁ anonimizado, lido do arquivo da prévia (não fica no banco)


class CorrecaoItemOut(BaseModel):
    achado_id: int
    tipo: str
    tipo_rotulo: str
    coluna: str
    operador: str
    operador_rotulo: str
    alcance: str
    ocorrencias: int       # células encontradas na varredura
    alteradas: int         # células que a prévia altera
    aviso: str | None = None
    exemplos: list[ExemploOut] = []


class CorrecaoOut(BaseModel):
    id: int
    recurso_id: int
    recurso_nome: str | None
    dataset_titulo: str | None
    recurso_url_type: str | None
    status: str  # gerando_previa|previa|publicando|publicada|revertendo|revertida|descartada|erro
    solicitada_por: str | None
    solicitada_em: datetime | None
    celulas_alteradas: int
    nome_arquivo: str | None
    aprovado_por: str | None
    aprovado_em: datetime | None
    justificativa: str | None
    publicada_em: datetime | None
    revertida_por: str | None
    revertida_em: datetime | None
    motivo_reversao: str | None
    erro: str | None
    itens: list[CorrecaoItemOut]


class CorrecoesOut(BaseModel):
    escrita_habilitada: bool   # GDA_CKAN_WRITE_ENABLED e token configurados
    operadores: list[OpcaoOut]
    alcances: list[OpcaoOut]
    correcoes: list[CorrecaoOut]


class AprovarCorrecaoIn(BaseModel):
    justificativa: str | None = Field(default=None, max_length=1000)


class ReverterCorrecaoIn(BaseModel):
    motivo: str = Field(min_length=5, max_length=1000)
