"""Cifragem simétrica de segredos guardados no banco (ex.: chaves de API dos provedores de IA).

A chave mestra fica em GDA_ENCRYPTION_KEY (gere com `python -m app.cli gerar-chave`).
Sem ela, em dev, deriva-se uma chave da GDA_SECRET_KEY — nunca use isso fora de dev.
"""
import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

log = logging.getLogger(__name__)


def _fernet() -> Fernet:
    s = get_settings()
    if s.encryption_key:
        return Fernet(s.encryption_key.get_secret_value().encode())
    if s.environment != "dev":
        raise RuntimeError("GDA_ENCRYPTION_KEY é obrigatória fora do ambiente de desenvolvimento.")
    log.warning("GDA_ENCRYPTION_KEY ausente: usando chave derivada (apenas dev).")
    digest = hashlib.sha256(s.secret_key.get_secret_value().encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:  # chave mestra trocada ou dado corrompido
        raise RuntimeError("Não foi possível decifrar o segredo armazenado.") from exc


def hint(plain: str) -> str:
    """Dica exibível de um segredo, sem revelá-lo: ••••1a2b."""
    return "••••" + plain[-4:] if len(plain) >= 8 else "••••"


def generate_key() -> str:
    return Fernet.generate_key().decode()
