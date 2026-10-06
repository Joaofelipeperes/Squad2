from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class LoginIn(BaseModel):
    email: EmailStr
    senha: str


class PapelResumo(BaseModel):
    id: int
    codigo: str
    nome: str


class OrgaoResumo(BaseModel):
    ckan_id: str
    titulo: str


class UsuarioOut(BaseModel):
    id: int
    email: str
    nome: str
    ativo: bool
    orgao: OrgaoResumo | None
    papeis: list[PapelResumo]
    ultimo_acesso: datetime | None


class SessaoOut(BaseModel):
    """Resposta de /acesso/me: o frontend monta menu e botões a partir de `permissoes`."""

    usuario: UsuarioOut
    permissoes: list[str]


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    sessao: SessaoOut


class UsuarioIn(BaseModel):
    email: EmailStr
    nome: str = Field(min_length=2, max_length=200)
    senha: str | None = Field(None, min_length=8)  # obrigatória na criação; opcional na edição
    ativo: bool = True
    orgao_id: str | None = None
    papel_ids: list[int] = Field(default_factory=list)


class PermissaoOut(BaseModel):
    codigo: str
    rotulo: str
    descricao: str
    sensivel: bool


class GrupoPermissoesOut(BaseModel):
    modulo: str
    permissoes: list[PermissaoOut]


class PapelOut(BaseModel):
    id: int
    codigo: str
    nome: str
    descricao: str | None
    sistema: bool
    exige_orgao: bool
    todas: bool
    permissoes: list[str]
    total_usuarios: int


class PapelIn(BaseModel):
    codigo: str = Field(pattern=r"^[a-z][a-z0-9_]{2,59}$")
    nome: str = Field(min_length=2, max_length=120)
    descricao: str | None = None
    exige_orgao: bool = False
    permissoes: list[str] = Field(default_factory=list)
