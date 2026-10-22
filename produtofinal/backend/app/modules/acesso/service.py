"""Regras do módulo acesso: autenticação, permissões, administração de papéis e log de acesso.
O banco só é acessado pelo `AcessoDao` (ADR-0019)."""
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.db import SessionLocal, utcnow
from app.core.deps import UsuarioAtual
from app.core.permissoes import PAPEIS_PADRAO, P
from app.core.security import hash_password, verify_password
from app.modules.acesso.dao import AcessoDao
from app.modules.acesso.models import LogAcesso, Papel, Usuario
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
    """Usuário excluído (lógico) ou inativo → None (o token deixa de valer)."""
    u = AcessoDao(db).usuario(user_id)
    if u is None or not u.ativo:
        return None
    return UsuarioAtual(id=u.id, email=u.email, nome=u.nome, orgao_id=u.orgao_id,
                        papeis=[p.codigo for p in u.papeis], permissoes=permissoes_de(u))


def autenticar(db: Session, email: str, senha: str) -> Usuario | None:
    u = AcessoDao(db).usuario_por_email(email)
    if u and u.ativo and verify_password(senha, u.senha_hash):
        dao = AcessoDao(db, u.id)  # o próprio usuário registra o último acesso
        u.ultimo_acesso = utcnow()
        dao.save_generic(u)
        dao.commit()
        return u
    return None


# ------------------------------------------------------------------ saída
def usuario_por_id(db: Session, usuario_id: int) -> Usuario | None:
    return AcessoDao(db).usuario(usuario_id)


def usuario_out(db: Session, u: Usuario) -> UsuarioOut:
    org = AcessoDao(db).orgao(u.orgao_id) if u.orgao_id else None
    return UsuarioOut(
        id=u.id, email=u.email, nome=u.nome, ativo=u.ativo, ultimo_acesso=u.ultimo_acesso,
        orgao=OrgaoResumo(id=org.id, id_ckan=org.id_ckan, titulo=org.titulo) if org else None,
        papeis=[PapelResumo(id=p.id, codigo=p.codigo, nome=p.nome) for p in u.papeis],
    )


def listar_usuarios(db: Session) -> list[UsuarioOut]:
    return [usuario_out(db, u) for u in AcessoDao(db).usuarios()]


def sessao_out(db: Session, u: Usuario) -> SessaoOut:
    return SessaoOut(usuario=usuario_out(db, u), permissoes=sorted(permissoes_de(u)))


def listar_orgaos(db: Session) -> list[OrgaoResumo]:
    return [OrgaoResumo(id=o.id, id_ckan=o.id_ckan, titulo=o.titulo)
            for o in AcessoDao(db).orgaos()]


def orgao_por_referencia(db: Session, referencia: str) -> int | None:
    """`id` da organização pelo `id_ckan` ou `name` (CLI `criar-usuario --orgao`)."""
    org = AcessoDao(db).orgao_por_referencia(referencia)
    return org.id if org else None


def papel_out(db: Session, p: Papel) -> PapelOut:
    total = AcessoDao(db).total_usuarios_do_papel(p.id)
    perms = sorted(CODIGOS_VALIDOS) if p.todas else sorted(x.permissao for x in p.permissoes)
    return PapelOut(id=p.id, codigo=p.codigo, nome=p.nome, descricao=p.descricao,
                    sistema=p.sistema, exige_orgao=p.exige_orgao, todas=p.todas,
                    permissoes=perms, total_usuarios=total)


# ------------------------------------------------------------------ papéis
def sincronizar_papeis_padrao(db: Session) -> None:
    """Cria os papéis do catálogo que ainda não existem. Não sobrescreve ajustes feitos na tela,
    e exclui (logicamente) as permissões que saíram do catálogo. Ação do sistema."""
    dao = AcessoDao(db)
    for pp in PAPEIS_PADRAO:
        if dao.papel_por_codigo(pp.codigo) is None:
            papel = dao.save_generic(Papel(
                codigo=pp.codigo, nome=pp.nome, descricao=pp.descricao, sistema=True,
                exige_orgao=pp.exige_orgao, todas=pp.todas))
            dao.definir_permissoes(papel, [str(x) for x in pp.permissoes])
    dao.excluir_permissoes_fora_do_catalogo(CODIGOS_VALIDOS)
    dao.commit()


def _validar_permissoes(codigos: list[str]) -> list[str]:
    invalidas = sorted(set(codigos) - CODIGOS_VALIDOS)
    if invalidas:
        raise ErroAcesso(f"Permissões inexistentes no catálogo: {', '.join(invalidas)}.")
    return sorted(set(codigos))


def papel_por_id(db: Session, papel_id: int) -> Papel | None:
    return AcessoDao(db).papel(papel_id)


def listar_papeis(db: Session) -> list[PapelOut]:
    return [papel_out(db, p) for p in AcessoDao(db).papeis()]


def salvar_papel(db: Session, dados: PapelIn, papel: Papel | None = None,
                 editor: UsuarioAtual | None = None) -> Papel:
    dao = AcessoDao.de(db, editor)
    if papel is not None and papel.todas:
        raise ErroAcesso("O papel Administrador sempre tem todas as permissões.")
    if papel is None:
        if dao.papel_por_codigo(dados.codigo):
            raise ErroAcesso("Já existe um papel com este código.")
        papel = Papel(codigo=dados.codigo, sistema=False)
    elif papel.codigo != dados.codigo and papel.sistema:
        raise ErroAcesso("O código de um papel do sistema não pode ser alterado.")
    permissoes = _validar_permissoes(dados.permissoes)
    papel.codigo, papel.nome, papel.descricao = dados.codigo, dados.nome, dados.descricao
    papel.exige_orgao = dados.exige_orgao
    dao.save_generic(papel)
    dao.definir_permissoes(papel, permissoes)
    dao.commit()
    dao.recarregar(papel)
    return papel


def excluir_papel(db: Session, papel: Papel, editor: UsuarioAtual | None = None) -> None:
    """Exclusão lógica do papel e dos vínculos (usuários e permissões)."""
    if papel.sistema:
        raise ErroAcesso("Papéis do sistema não podem ser excluídos.")
    if papel_out(db, papel).total_usuarios:
        raise ErroAcesso("Há usuários com este papel. Remova-o dos usuários antes de excluir.")
    dao = AcessoDao.de(db, editor)
    dao.excluir_papel(papel)
    dao.commit()


# ------------------------------------------------------------------ usuários
def salvar_usuario(db: Session, dados: UsuarioIn, usuario: Usuario | None = None,
                   editor: UsuarioAtual | None = None) -> Usuario:
    dao = AcessoDao.de(db, editor)
    papeis = dao.papeis_por_ids(list(dados.papel_ids))
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
        if dao.usuario_por_email(dados.email):
            raise ErroAcesso("Já existe um usuário com este e-mail.")
        usuario = Usuario(email=dados.email.lower(), senha_hash=hash_password(dados.senha))
    elif dados.senha:
        usuario.senha_hash = hash_password(dados.senha)

    usuario.nome, usuario.ativo = dados.nome, dados.ativo
    usuario.orgao_id = dados.orgao_id or None
    dao.save_generic(usuario)
    dao.definir_papeis(usuario, papeis)
    if era_admin_ativo and dao.admins_ativos() == 0:
        dao.rollback()
        raise ErroAcesso("Operação bloqueada: o sistema ficaria sem nenhum administrador ativo.")
    dao.commit()
    dao.recarregar(usuario)
    return usuario


def excluir_usuario(db: Session, usuario: Usuario, editor: UsuarioAtual | None = None) -> None:
    """Exclusão lógica do usuário e dos vínculos com papéis; bloqueada se ele for o último
    administrador ativo."""
    dao = AcessoDao.de(db, editor)
    era_admin_ativo = usuario.ativo and any(p.todas for p in usuario.papeis)
    dao.definir_papeis(usuario, [])
    dao.delete_generic(usuario)
    if era_admin_ativo and dao.admins_ativos() == 0:
        dao.rollback()
        raise ErroAcesso("Operação bloqueada: o sistema ficaria sem nenhum administrador ativo.")
    dao.commit()


def criar_usuario(db: Session, email: str, nome: str, senha: str, papel_codigos: list[str],
                  orgao_id: int | None = None) -> Usuario:
    """Atalho usado pela CLI e pelos testes (ação do sistema)."""
    sincronizar_papeis_padrao(db)
    ids = AcessoDao(db).ids_de_papeis(papel_codigos)
    return salvar_usuario(db, UsuarioIn(email=email, nome=nome, senha=senha, papel_ids=ids,
                                        orgao_id=orgao_id))


# ------------------------------------------------------------------ log de acesso (ADR-0016)
def registrar_acesso(**campos) -> None:
    """Grava uma linha em `acesso_log` numa sessão própria. Chamado pelo middleware de main.py
    depois da resposta; falha no log é registrada, mas não derruba a requisição."""
    try:
        with SessionLocal() as db:
            AcessoDao(db).registrar_log(**campos)
    except Exception:  # noqa: BLE001
        logging.getLogger(__name__).exception("Falha ao gravar o log de acesso.")


def listar_logs(db: Session, usuario: str | None, desde: datetime | None, ate: datetime | None,
                limite: int) -> list[LogAcesso]:
    return AcessoDao(db).logs(usuario, desde, ate, limite)
