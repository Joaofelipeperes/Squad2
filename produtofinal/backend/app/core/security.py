"""Hash de senha e emissão/validação de JWT. Regras de acesso ficam em permissoes.py/deps.py."""
from datetime import timedelta

import bcrypt
import jwt

from app.core.config import get_settings
from app.core.db import utcnow


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_access_token(user_id: int) -> str:
    """O token carrega só a identidade. Permissões são lidas do banco a cada requisição, para que
    revogar um papel tenha efeito imediato."""
    s = get_settings()
    payload = {"sub": str(user_id), "exp": utcnow() + timedelta(minutes=s.jwt_expire_minutes)}
    return jwt.encode(payload, s.secret_key.get_secret_value(), algorithm="HS256")


def decode_access_token(token: str) -> dict:
    s = get_settings()
    return jwt.decode(token, s.secret_key.get_secret_value(), algorithms=["HS256"])
