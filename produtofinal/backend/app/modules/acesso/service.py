"""Regras do módulo acesso: autenticação, resolução de permissões e administração de papéis."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.core.deps import UsuarioAtual
from app.core.permissoes import PAPEIS_PADRAO, P
from app.core.security import hash_password, verify_password
from app.modules.acesso.models import Papel, PapelPermissao, Usuario, usuario_papel
from app.modules.acesso.schemas import (
    OrgaoResumo, PapelIn, PapelOut, PapelResumo, SessaoOut, UsuarioIn, UsuarioOut,
)

CODIGOS_VALIDOS = {str(p) for p in P}


class ErroAcesso(ValueError):
    pass


# ------------------------------------------------------------------ resolução de permissões
def permissoes_de(usuario: Usuario) -> frozenset[str]:
    if any(p.todas for p in usuario.papeis):
        return frozenset(CODIGOS_VALIDOS)
    # Filtra pelo catálogo: permissão removida do código deixa de valer mesmo se sobrar no banco
    return frozenset(pp.permissao for papel in usuario.papeis for pp in papel.permissoes
                     if pp.permissao in CODIGOS_VALIDOS)


def carregar_usuario_atual(db: Session, user_id: int) -> UsuarioAtual | None:
    u = db.get(Usuario, user_id)
    if u is None or not u.ativo:
        return None
    return UsuarioAtual(id=u.id, email=u.email, nome=u.nome, orgao_id=u.orgao_id,
                        papeis=[p.codigo for p in u.papeis], permissoes=permissoes_de(u))


def autenticar(db: Session, email: str, senha: str) -> Usuario | None:
    u = db.scalar(select(Usuario).where(Usuario.email == email.lower()))
    if u and u.ativo and verify_password(senha, u.senha_hash):
        u.ultimo_acesso = utcnow()
        db.commit()
        return u
    return None


# ------------------------------------------------------------------ saída
def usuario_out(db: Session, u: Usuario) -> UsuarioOut:
    from app.modules.inventario.models import Organizacao  # leitura cruzada (ver MODULO.md)

    org = db.get(Organizacao, u.orgao_id) if u.orgao_id else None
    return UsuarioOut(
        id=u.id, email=u.email, nome=u.nome, ativo=u.ativo, ultimo_acesso=u.ultimo_acesso,
        orgao=OrgaoResumo(ckan_id=org.ckan_id, titulo=org.titulo) if org else None,
        papeis=[PapelResumo(id=p.id, codigo=p.codigo, nome=p.nome) for p in u.papeis],
    )


def sessao_out(db: Session, u: Usuario) -> SessaoOut:
    return SessaoOut(usuario=usuario_out(db, u), permissoes=sorted(permissoes_de(u)))


def papel_out(db: Session, p: Papel) -> PapelOut:
    total = db.scalar(select(func.count()).select_from(usuario_papel)
                      .where(usuario_papel.c.papel_id == p.id))
    perms = sorted(CODIGOS_VALIDOS) if p.todas else sorted(x.permissao for x in p.permissoes)
    return PapelOut(id=p.id, codigo=p.codigo, nome=p.nome, descricao=p.descricao,
                    sistema=p.sistema, exige_orgao=p.exige_orgao, todas=p.todas,
                    permissoes=perms, total_usuarios=total or 0)


# ------------------------------------------------------------------ papéis
def sincronizar_papeis_padrao(db: Session) -> None:
    """Cria os papéis do catálogo que ainda não existem. Não sobrescreve ajustes feitos na tela,
    e remove do banco permissões que saíram do catálogo."""
    for pp in PAPEIS_PADRAO:
        papel = db.scalar(select(Papel).where(Papel.codigo == pp.codigo))
        if papel is None:
            papel = Papel(codigo=pp.codigo, nome=pp.nome, descricao=pp.descricao, sistema=True,
                          exige_orgao=pp.exige_orgao, todas=pp.todas)
            papel.permissoes = [PapelPermissao(permissao=str(x)) for x in sorted(pp.permissoes)]
            db.add(papel)
    db.flush()
    for orfa in db.scalars(select(PapelPermissao)
                           .where(PapelPermissao.permissao.not_in(CODIGOS_VALIDOS))).all():
        db.delete(orfa)
    db.commit()


def _validar_permissoes(codigos: list[str]) -> list[str]:
    invalidas = sorted(set(codigos) - CODIGOS_VALIDOS)
    if invalidas:
        raise ErroAcesso(f"Permissões inexistentes no catálogo: {', '.join(invalidas)}.")
    return sorted(set(codigos))


def salvar_papel(db: Session, dados: PapelIn, papel: Papel | None = None) -> Papel:
    if papel is not None and papel.todas:
        raise ErroAcesso("O papel Administrador sempre tem todas as permissões.")
    if papel is None:
        if db.scalar(select(Papel).where(Papel.codigo == dados.codigo)):
            raise ErroAcesso("Já existe um papel com este código.")
        papel = Papel(codigo=dados.codigo, sistema=False)
    elif papel.codigo != dados.codigo and papel.sistema:
        raise ErroAcesso("O código de um papel do sistema não pode ser alterado.")
    papel.codigo, papel.nome, papel.descricao = dados.codigo, dados.nome, dados.descricao
    papel.exige_orgao = dados.exige_orgao
    papel.permissoes = [PapelPermissao(permissao=c) for c in _validar_permissoes(dados.permissoes)]
    db.add(papel)
    db.commit()
    db.refresh(papel)
    return papel


def excluir_papel(db: Session, papel: Papel) -> None:
    if papel.sistema:
        raise ErroAcesso("Papéis do sistema não podem ser excluídos.")
    if papel_out(db, papel).total_usuarios:
        raise ErroAcesso("Há usuários com este papel. Remova-o dos usuários antes de excluir.")
    db.delete(papel)
    db.commit()


# ------------------------------------------------------------------ usuários
def _admins_ativos(db: Session) -> int:
    return db.scalar(select(func.count(func.distinct(Usuario.id))).select_from(Usuario)
                     .join(usuario_papel).join(Papel)
                     .where(Usuario.ativo, Papel.todas)) or 0


def salvar_usuario(db: Session, dados: UsuarioIn, usuario: Usuario | None = None,
                   editor: UsuarioAtual | None = None) -> Usuario:
    papeis = list(db.scalars(select(Papel).where(Papel.id.in_(dados.papel_ids))).all())
    if len(papeis) != len(set(dados.papel_ids)):
        raise ErroAcesso("Um ou mais papéis informados não existem.")
    if any(p.exige_orgao for p in papeis) and not dados.orgao_id:
        nomes = ", ".join(p.nome for p in papeis if p.exige_orgao)
        raise ErroAcesso(f"O papel {nomes} exige vincular o usuário a um órgão.")
    # Só quem gerencia papéis pode conceder o papel Administrador
    if editor and any(p.todas for p in papeis) and not editor.pode(P.ACESSO_GERENCIAR_PAPEIS):
        if usuario is None or not any(p.todas for p in usuario.papeis):
            raise ErroAcesso("Apenas administradores podem conceder o papel Administrador.")

    era_admin_ativo = bool(usuario and usuario.ativo and any(p.todas for p in usuario.papeis))
    if usuario is None:
        if not dados.senha:
            raise ErroAcesso("Informe uma senha inicial (mínimo 8 caracteres).")
        if db.scalar(select(Usuario).where(Usuario.email == dados.email.lower())):
            raise ErroAcesso("Já existe um usuário com este e-mail.")
        usuario = Usuario(email=dados.email.lower(), senha_hash=hash_password(dados.senha))
    elif dados.senha:
        usuario.senha_hash = hash_password(dados.senha)

    usuario.nome, usuario.ativo = dados.nome, dados.ativo
    usuario.orgao_id = dados.orgao_id or None
    usuario.papeis = papeis
    db.add(usuario)
    db.flush()
    if era_admin_ativo and _admins_ativos(db) == 0:
        db.rollback()
        raise ErroAcesso("Operação bloqueada: o sistema ficaria sem nenhum administrador ativo.")
    db.commit()
    db.refresh(usuario)
    return usuario


def criar_usuario(db: Session, email: str, nome: str, senha: str, papel_codigos: list[str],
                  orgao_id: str | None = None) -> Usuario:
    """Atalho usado pela CLI e pelos testes."""
    sincronizar_papeis_padrao(db)
    ids = list(db.scalars(select(Papel.id).where(Papel.codigo.in_(papel_codigos))).all())
    return salvar_usuario(db, UsuarioIn(email=email, nome=nome, senha=senha, papel_ids=ids,
                                        orgao_id=orgao_id))
