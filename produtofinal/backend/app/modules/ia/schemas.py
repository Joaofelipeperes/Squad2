from datetime import datetime

from pydantic import BaseModel, Field

from app.integrations.ai.base import FieldSpec
from app.integrations.ai.policy import TarefaIA


class TipoProvedorOut(BaseModel):
    tipo: str
    rotulo: str
    descricao: str
    url_padrao: str | None
    exige_chave: bool
    local_por_padrao: bool
    modelos_sugeridos: list[str]
    campos: list[FieldSpec]


class PerfilIn(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    tipo: str
    modelo: str = Field(min_length=1)
    base_url: str | None = None
    # None = manter a chave atual; "" = remover; texto = substituir
    api_key: str | None = None
    execucao_local: bool = False
    temperatura: float = Field(0.2, ge=0, le=2)
    max_tokens: int = Field(1024, ge=16, le=32768)
    timeout_s: float = Field(60, ge=5, le=600)
    ativo: bool = True


class PerfilOut(BaseModel):
    id: int
    nome: str
    tipo: str
    modelo: str
    base_url: str | None
    tem_chave: bool
    api_key_dica: str | None
    execucao_local: bool
    temperatura: float
    max_tokens: int
    timeout_s: float
    ativo: bool
    atualizado_em: datetime


class TesteConexaoIn(BaseModel):
    """Permite testar/listar modelos ANTES de salvar o perfil (formulário da página)."""

    tipo: str
    modelo: str = "teste"
    base_url: str | None = None
    api_key: str | None = None
    perfil_id: int | None = None  # se informado e api_key vazio, reaproveita a chave salva


class TesteConexaoOut(BaseModel):
    ok: bool
    mensagem: str
    latencia_ms: int | None = None
    modelos: list[str] = []


class TarefaOut(BaseModel):
    tarefa: TarefaIA
    rotulo: str
    descricao: str
    sensivel: bool
    user_story: str
    perfil_id: int | None
    perfil_fallback_id: int | None
    somente_local: bool  # verdadeiro quando a política exige perfil local


class VinculoIn(BaseModel):
    perfil_id: int | None
    perfil_fallback_id: int | None = None


class UsoOut(BaseModel):
    momento: datetime
    tarefa: str
    perfil_nome: str
    modelo: str
    sucesso: bool
    usou_fallback: bool
    latencia_ms: int | None
    tokens_entrada: int | None
    tokens_saida: int | None
    erro: str | None

    model_config = {"from_attributes": True}


class PlaygroundIn(BaseModel):
    tarefa: TarefaIA = TarefaIA.ASSISTENTE
    mensagem: str = Field(min_length=1, max_length=2000)


class PlaygroundOut(BaseModel):
    texto: str
    perfil: str
    modelo: str
    latencia_ms: int | None
    usou_fallback: bool
