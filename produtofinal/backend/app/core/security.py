"""Hash de senha e emissão/validação de JWT. Regras de acesso ficam em permissoes.py/deps.py."""
import hashlib
from datetime import timedelta

import bcrypt
import jwt

from app.core.config import get_settings
from app.core.db import utcnow

# O bcrypt só considera os primeiros 72 bytes da senha (e as versões novas recusam mais que isso)
SENHA_MAX_BYTES = 72
# Hash de uma senha qualquer: o login de e-mail inexistente gasta o mesmo tempo de um existente
_HASH_DE_COMPARACAO = bcrypt.hashpw(b"sem-usuario", bcrypt.gensalt())


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    """Senha longa demais ou hash ilegível → False (nunca erro: o login responde 401)."""
    senha = password.encode()
    if len(senha) > SENHA_MAX_BYTES:
        return False
    try:
        return bcrypt.checkpw(senha, hashed.encode())
    except ValueError:
        return False


def gastar_tempo_de_verificacao(password: str) -> None:
    """Para o login de usuário inexistente ou inativo: faz a mesma conta de uma verificação real,
    para o tempo de resposta não revelar quais e-mails têm conta (ADR-0036)."""
    bcrypt.checkpw(password.encode()[:SENHA_MAX_BYTES], _HASH_DE_COMPARACAO)


def marca_da_senha(senha_hash: str) -> str:
    """Marca que muda quando a senha muda. Vai no token (`pwd`): trocada a senha, os tokens
    emitidos antes deixam de valer (ADR-0036). Não revela o hash."""
    return hashlib.sha256(senha_hash.encode()).hexdigest()[:16]


def create_access_token(user_id: int, senha_hash: str) -> str:
    """O token carrega a identidade e a marca da senha. Permissões são lidas do banco a cada
    requisição, para que revogar um papel tenha efeito imediato."""
    s = get_settings()
    payload = {"sub": str(user_id), "pwd": marca_da_senha(senha_hash),
               "exp": utcnow() + timedelta(minutes=s.jwt_expire_minutes)}
    return jwt.encode(payload, s.secret_key.get_secret_value(), algorithm="HS256")


def decode_access_token(token: str) -> dict:
    s = get_settings()
    return jwt.decode(token, s.secret_key.get_secret_value(), algorithms=["HS256"])
