"""Regras do módulo acesso: autenticação, permissões, administração de papéis e log de acesso.
O banco só é acessado pelo `AcessoDao` (ADR-0019)."""
import logging
import secrets
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import SessionLocal, utcnow
from app.core.deps import UsuarioAtual
from app.core.permissoes import PAPEIS_PADRAO, P
from app.core.security import (
    SENHA_MAX_BYTES, marca_da_senha, gastar_tempo_de_verificacao, hash_password, verify_password,
)
from app.modules.acesso.dao import AcessoDao
from app.modules.acesso.models import Papel, Usuario
from app.modules.acesso.schemas import (
    LogAcessoOut, LogsAcessoOut, OrgaoResumo, PapelIn, PapelOut, PapelResumo, SessaoOut,
    UsuarioIn, UsuarioOut,
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


def carregar_usuario_atual(db: Session, user_id: int,
                           marca_senha: str | None = None) -> UsuarioAtual | None:
    """Usuário excluído (lógico) ou inativo → None (o token deixa de valer). O mesmo vale quando a
    marca da senha do token (`pwd`) não é a da senha atual: senha trocada encerra as sessões
    abertas (ADR-0036)."""
    u = AcessoDao(db).usuario(user_id)
    if u is None or not u.ativo or marca_senha != marca_da_senha(u.senha_hash):
        return None
    return UsuarioAtual(id=u.id, email=u.email, nome=u.nome, orgao_id=u.orgao_id,
                        papeis=[p.codigo for p in u.papeis], permissoes=permissoes_de(u),
                        administrador=_e_admin(u))


# ------------------------------------------------------------------ administradores ocultos
# O papel Administrador (`Papel.todas`) e os usuários que o têm só aparecem para quem também é
# administrador: nas listas, na edição por id e na escolha de papéis do usuário. `quem` = None é o
# sistema (CLI, instalação, testes), que enxerga tudo.
def _e_admin(u: Usuario) -> bool:
    return any(p.todas for p in u.papeis)


def ve_administradores(quem: UsuarioAtual | None) -> bool:
    return quem is None or quem.administrador


def login_bloqueado(db: Session, email: str) -> bool:
    """Muitas senhas erradas seguidas para este e-mail (exista ou não a conta) dentro da janela
    (`GDA_LOGIN_MAX_FALHAS` em `GDA_LOGIN_JANELA_MINUTOS`, ADR-0036). Conta as linhas do log de
    acesso depois do último login bem-sucedido; passada a janela, libera sozinho."""
    s = get_settings()
    if s.login_max_falhas <= 0:
        return False
    desde = utcnow() - timedelta(minutes=s.login_janela_minutos)
    return AcessoDao(db).falhas_de_login(email.lower(), desde) >= s.login_max_falhas


def autenticar(db: Session, email: str, senha: str) -> Usuario | None:
    u = AcessoDao(db).usuario_por_email(email)
    if u is None or not u.ativo:
        gastar_tempo_de_verificacao(senha)  # mesmo tempo de resposta de uma conta existente
        return None
    if verify_password(senha, u.senha_hash):
        dao = AcessoDao(db, u.id)  # o próprio usuário registra o último acesso
        u.ultimo_acesso = utcnow()
        dao.save_generic(u)
        dao.commit()
        return u
    return None


# ------------------------------------------------------------------ saída
def usuario_por_id(db: Session, usuario_id: int,
                   quem: UsuarioAtual | None = None) -> Usuario | None:
    """Usuário pelo id; administrador visto por quem não é administrador → None (404)."""
    u = AcessoDao(db).usuario(usuario_id)
    if u is not None and not ve_administradores(quem) and _e_admin(u):
        return None
    return u


def usuario_out(db: Session, u: Usuario) -> UsuarioOut:
    org = AcessoDao(db).orgao(u.orgao_id) if u.orgao_id else None
    return UsuarioOut(
        id=u.id, email=u.email, nome=u.nome, ativo=u.ativo, ultimo_acesso=u.ultimo_acesso,
        orgao=OrgaoResumo(id=org.id, id_ckan=org.id_ckan, titulo=org.titulo) if org else None,
        papeis=[PapelResumo(id=p.id, codigo=p.codigo, nome=p.nome) for p in u.papeis],
    )


def listar_usuarios(db: Session, quem: UsuarioAtual | None = None) -> list[UsuarioOut]:
    usuarios = AcessoDao(db).usuarios(incluir_admins=ve_administradores(quem))
    return [usuario_out(db, u) for u in usuarios]


def sessao_out(db: Session, u: Usuario) -> SessaoOut:
    return SessaoOut(usuario=usuario_out(db, u), permissoes=sorted(permissoes_de(u)))


def listar_orgaos(db: Session) -> list[OrgaoResumo]:
    return [OrgaoResumo(id=o.id, id_ckan=o.id_ckan, titulo=o.titulo)
            for o in AcessoDao(db).orgaos()]


def orgao_por_referencia(db: Session, referencia: str) -> int | None:
    """`id` da organização pelo `id_ckan` ou `name` (CLI `criar-usuario --orgao`)."""
    org = AcessoDao(db).orgao_por_referencia(referencia)
    return org.id if org else None


def papel_out(db: Session, p: Papel, quem: UsuarioAtual | None = None) -> PapelOut:
    """`total_usuarios` não conta os administradores para quem não os enxerga."""
    total = AcessoDao(db).total_usuarios_do_papel(p.id,
                                                  incluir_admins=ve_administradores(quem))
    perms = sorted(CODIGOS_VALIDOS) if p.todas else sorted(x.permissao for x in p.permissoes)
    return PapelOut(id=p.id, codigo=p.codigo, nome=p.nome, descricao=p.descricao,
                    sistema=p.sistema, exige_orgao=p.exige_orgao, todas=p.todas,
                    permissoes=perms, total_usuarios=total)


# ------------------------------------------------------------------ senha (ADR-0036)
SENHA_MIN = 8
# Senhas que cumprem "letra e número" mas estão em toda lista de ataque
SENHAS_COMUNS = frozenset({
    "senha123", "senha1234", "senha12345", "senha123456", "admin123", "admin1234", "admin12345",
    "abc12345", "abcd1234", "a1b2c3d4", "1q2w3e4r", "1q2w3e4r5t", "q1w2e3r4", "qwerty123",
    "qwert123", "password1", "password123", "mudar123", "mudar1234", "trocar123", "teste123",
    "teste1234", "goias123", "goias2025", "goias2026", "cge12345", "geda1234", "brasil123",
})


def problema_da_senha(senha: str, email: str | None = None) -> str | None:
    """Por que a senha não serve (None = serve): de 8 caracteres a 72 bytes, com letra e número,
    fora da lista de senhas comuns e sem repetir o e-mail."""
    if len(senha) < SENHA_MIN:
        return f"A senha precisa de pelo menos {SENHA_MIN} caracteres."
    if len(senha.encode()) > SENHA_MAX_BYTES:
        return f"A senha pode ter no máximo {SENHA_MAX_BYTES} bytes."
    if not (any(c.isalpha() for c in senha) and any(c.isdigit() for c in senha)):
        return "A senha precisa ter letras e números."
    minuscula = senha.lower()
    if minuscula in SENHAS_COMUNS or len(set(minuscula)) < 4:
        return "Senha muito comum ou repetitiva: escolha outra."
    nome_email = (email or "").split("@")[0].lower()
    if len(nome_email) >= 4 and nome_email in minuscula:
        return "A senha não pode conter o seu e-mail."
    return None


def _exigir_senha_valida(senha: str, email: str | None) -> None:
    problema = problema_da_senha(senha, email)
    if problema:
        raise ErroAcesso(problema)


def trocar_propria_senha(db: Session, user: UsuarioAtual, senha_atual: str,
                         senha_nova: str) -> Usuario:
    """O próprio usuário troca a senha (precisa informar a atual). As sessões abertas com a senha
    antiga deixam de valer; quem chama emite um token novo."""
    dao = AcessoDao.de(db, user)
    u = dao.usuario(user.id)
    if u is None or not verify_password(senha_atual, u.senha_hash):
        raise ErroAcesso("Senha atual incorreta.")
    if senha_nova == senha_atual:
        raise ErroAcesso("A nova senha deve ser diferente da atual.")
    _exigir_senha_valida(senha_nova, u.email)
    u.senha_hash = hash_password(senha_nova)
    dao.save_generic(u)
    dao.commit()
    dao.recarregar(u)
    return u


# ------------------------------------------------------------------ limites de quem não é admin
# Quem gerencia usuários ou papéis sem ser administrador não pode usar isso para ganhar acesso
# (ADR-0036): não mexe nos próprios papéis, não concede nem altera papel personalizado com
# permissão que não tem, não altera papel do sistema nem um papel que ele mesmo possui.
def _limitado(editor: UsuarioAtual | None) -> bool:
    return editor is not None and not editor.administrador


def _pode_conceder(editor: UsuarioAtual | None, papel: Papel) -> bool:
    """Papéis do sistema (definidos pelo catálogo e só alteráveis por administrador) qualquer
    gestor de usuários concede; um papel personalizado, só quem tem todas as permissões dele."""
    if not _limitado(editor):
        return True
    if papel.todas:
        return False
    return papel.sistema or {pp.permissao for pp in papel.permissoes} <= editor.permissoes


# ------------------------------------------------------------------ papéis
def sincronizar_papeis_padrao(db: Session) -> None:
    """Cria os papéis do catálogo que ainda não existem. Não sobrescreve ajustes feitos na tela,
    e exclui (logicamente) as permissões que saíram do catálogo. Ação do sistema.

    Com `GDA_PAPEIS_INICIAIS` preenchido (servidor, ADR-0032), cria só os papéis listados; os
    demais a GEDA cria na tela Usuários e papéis, conforme a necessidade."""
    dao = AcessoDao(db)
    iniciais = set(get_settings().papeis_iniciais)
    for pp in PAPEIS_PADRAO:
        if iniciais and pp.codigo not in iniciais:
            continue
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


def papel_por_id(db: Session, papel_id: int, quem: UsuarioAtual | None = None) -> Papel | None:
    """Papel pelo id; o Administrador, para quem não é administrador → None (404)."""
    p = AcessoDao(db).papel(papel_id)
    if p is not None and p.todas and not ve_administradores(quem):
        return None
    return p


def listar_papeis(db: Session, quem: UsuarioAtual | None = None) -> list[PapelOut]:
    papeis = AcessoDao(db).papeis(incluir_admin=ve_administradores(quem))
    return [papel_out(db, p, quem) for p in papeis]


def salvar_papel(db: Session, dados: PapelIn, papel: Papel | None = None,
                 editor: UsuarioAtual | None = None) -> Papel:
    dao = AcessoDao.de(db, editor)
    if papel is not None and papel.todas:
        raise ErroAcesso("O papel Administrador sempre tem todas as permissões.")
    if _limitado(editor):
        if papel is not None and papel.sistema:
            raise ErroAcesso("Papéis do sistema só podem ser alterados por um administrador.")
        if papel is not None and papel.codigo in editor.papeis:
            raise ErroAcesso("Você não pode alterar um papel que você mesmo possui.")
        alem = sorted(set(dados.permissoes) & CODIGOS_VALIDOS - editor.permissoes)
        if alem:
            raise ErroAcesso("Você não pode incluir permissões que não possui: "
                             + ", ".join(alem) + ".")
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
    if _limitado(editor) and not _pode_conceder(editor, papel):
        raise ErroAcesso("Este papel tem permissões que você não possui; só um administrador "
                         "pode excluí-lo.")
    if papel_out(db, papel).total_usuarios:
        raise ErroAcesso("Há usuários com este papel. Remova-o dos usuários antes de excluir.")
    dao = AcessoDao.de(db, editor)
    dao.excluir_papel(papel)
    dao.commit()


# ------------------------------------------------------------------ usuários
def salvar_usuario(db: Session, dados: UsuarioIn, usuario: Usuario | None = None,
                   editor: UsuarioAtual | None = None) -> Usuario:
    dao = AcessoDao.de(db, editor)
    # Só administrador concede o papel Administrador: para os demais ele nem existe
    papeis = dao.papeis_por_ids(list(dados.papel_ids),
                                incluir_admin=ve_administradores(editor))
    if len(papeis) != len(set(dados.papel_ids)):
        raise ErroAcesso("Um ou mais papéis informados não existem.")
    if any(p.exige_orgao for p in papeis) and not dados.orgao_id:
        nomes = ", ".join(p.nome for p in papeis if p.exige_orgao)
        raise ErroAcesso(f"O papel {nomes} exige vincular o usuário a um órgão.")
    if _limitado(editor):
        if usuario is not None and usuario.id == editor.id and (
                {p.id for p in papeis} != {p.id for p in usuario.papeis}
                or (dados.orgao_id or None) != usuario.orgao_id or not dados.ativo):
            raise ErroAcesso("Você não pode alterar os próprios papéis, órgão ou situação. "
                             "Peça a um administrador.")
        if usuario is not None and not all(_pode_conceder(editor, p) for p in usuario.papeis):
            raise ErroAcesso("Este usuário tem um papel com permissões que você não possui; "
                             "só um administrador pode alterá-lo.")
        negados = [p.nome for p in papeis if not _pode_conceder(editor, p)]
        if negados:
            raise ErroAcesso(f"Você não pode conceder o papel {', '.join(negados)}: ele tem "
                             "permissões que você não possui.")

    era_admin_ativo = bool(usuario and usuario.ativo and any(p.todas for p in usuario.papeis))
    email = dados.email.lower()
    dono_do_email = dao.usuario_por_email(email)
    if dono_do_email and (usuario is None or dono_do_email.id != usuario.id):
        raise ErroAcesso("Já existe um usuário com este e-mail.")
    if usuario is None:
        if not dados.senha:
            raise ErroAcesso("Informe uma senha inicial (mínimo 8 caracteres, com letras e "
                             "números).")
        _exigir_senha_valida(dados.senha, email)
        usuario = Usuario(email=email, senha_hash=hash_password(dados.senha))
    elif dados.senha:
        _exigir_senha_valida(dados.senha, email)
        usuario.senha_hash = hash_password(dados.senha)

    usuario.email = email
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


def semear_admin_inicial(db: Session) -> Usuario | None:
    """Primeira subida no servidor (ADR-0032): com `GDA_ADMIN_INICIAL_EMAIL` preenchido e o banco
    sem nenhum usuário, cria o administrador. A senha é a de `GDA_ADMIN_INICIAL_SENHA`, se ela
    cumprir a regra de senha; vazia ou fraca, é gerada uma senha aleatória, mostrada UMA vez no log
    da API (ADR-0036). O administrador a troca no primeiro acesso (menu do usuário › Trocar senha).
    Com senha configurada, cada subida avisa no log enquanto ela não for trocada.
    Ação do sistema. Devolve o usuário criado, ou None."""
    s = get_settings()
    if not s.admin_inicial_email:
        return None
    log = logging.getLogger(__name__)
    dao = AcessoDao(db)
    email = s.admin_inicial_email.strip().lower()
    configurada = s.admin_inicial_senha.get_secret_value() if s.admin_inicial_senha else ""
    if dao.existe_usuario():
        u = dao.usuario_por_email(email)
        if configurada and u and u.ativo and verify_password(configurada, u.senha_hash):
            log.warning("O administrador %s ainda usa a senha inicial: troque-a no menu do "
                        "usuário › Trocar senha.", u.email)
        return None
    gerada = not configurada or problema_da_senha(configurada, email) is not None
    senha = secrets.token_urlsafe(18) if gerada else configurada
    sincronizar_papeis_padrao(db)
    admin = dao.papel_por_codigo("administrador")
    usuario = dao.save_generic(Usuario(email=email, nome=s.admin_inicial_nome,
                                       senha_hash=hash_password(senha)))
    dao.definir_papeis(usuario, [admin])
    dao.commit()
    if gerada:
        if configurada:
            log.warning("GDA_ADMIN_INICIAL_SENHA ignorada: não cumpre a regra de senha.")
        log.warning("Administrador inicial %s criado. Senha gerada (aparece só agora; troque-a "
                    "no primeiro acesso): %s", usuario.email, senha)
    else:
        log.warning("Administrador inicial %s criado com a senha de GDA_ADMIN_INICIAL_SENHA: "
                    "troque-a no primeiro acesso.", usuario.email)
    return usuario


# ------------------------------------------------------------------ log de acesso (ADR-0016)
def registrar_acesso(**campos) -> None:
    """Grava uma linha em `acesso_log` numa sessão própria. Chamado pelo middleware de main.py
    depois da resposta; falha no log é registrada, mas não derruba a requisição."""
    try:
        with SessionLocal() as db:
            AcessoDao(db).registrar_log(**campos)
    except Exception:  # noqa: BLE001
        logging.getLogger(__name__).exception("Falha ao gravar o log de acesso.")


# Colunas do log que a tela ordena (ADR-0028) e limite por página (CSV pede até 5.000 de uma vez)
COLUNAS_LOG = ("ocorrido_em", "usuario", "metodo", "caminho", "acao", "status_http", "ip",
               "user_agent")
LOGS_POR_PAGINA_MAXIMO = 5000


def listar_logs(db: Session, usuario: str | None, desde: datetime | None, ate: datetime | None,
                *, pagina: int = 1, por_pagina: int = 50, ordenar: str = "ocorrido_em",
                direcao: str = "desc", ate_id: int | None = None) -> LogsAcessoOut:
    """Página do log de acesso com o total. Sem `ate_id`, fixa no maior `id` atual."""
    dao = AcessoDao(db)
    if ordenar not in COLUNAS_LOG:
        ordenar = "ocorrido_em"
    ate_id = ate_id if ate_id is not None else dao.maior_id_log()
    por_pagina = max(1, min(por_pagina, LOGS_POR_PAGINA_MAXIMO))
    total, registros = dao.logs(usuario, desde, ate, ate_id=ate_id, ordenar=ordenar,
                                desc=direcao == "desc", por_pagina=por_pagina,
                                deslocamento=(max(1, pagina) - 1) * por_pagina)
    return LogsAcessoOut(total=total, pagina=max(1, pagina), por_pagina=por_pagina, ate_id=ate_id,
                         registros=[LogAcessoOut.model_validate(r) for r in registros])
