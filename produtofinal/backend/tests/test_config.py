"""Guarda de segredos na subida: fora de dev, chave JWT fraca ou falta de chave de cifragem impede a API."""
import pytest
from pydantic import ValidationError

from app.core.config import CKAN_LOCAL_DOCKER, CKAN_PORTAL_OFICIAL, Settings

CHAVE_FORTE = "x" * 48
CHAVE_FERNET = "a" * 43 + "="


def _settings(**kw):
    return Settings(_env_file=None, **kw)


@pytest.mark.parametrize("chave", [
    "troque-esta-chave-em-producao-dev-0000",  # padrão do config.py
    "troque-por-um-valor-longo-e-aleatorio",   # placeholder do .env.example
    "curta-demais",
])
@pytest.mark.parametrize("ambiente", ["homologacao", "producao"])
def test_fora_de_dev_recusa_chave_jwt_fraca(ambiente, chave):
    with pytest.raises(ValidationError, match="GDA_SECRET_KEY"):
        _settings(environment=ambiente, secret_key=chave, encryption_key=CHAVE_FERNET)


def test_fora_de_dev_recusa_chave_padrao_quando_nada_e_configurado():
    with pytest.raises(ValidationError, match="GDA_SECRET_KEY"):
        _settings(environment="producao", encryption_key=CHAVE_FERNET)


@pytest.mark.parametrize("encryption_key", [None, ""])
def test_fora_de_dev_exige_chave_de_cifragem(encryption_key):
    with pytest.raises(ValidationError, match="GDA_ENCRYPTION_KEY"):
        _settings(environment="producao", secret_key=CHAVE_FORTE, encryption_key=encryption_key)


def test_fora_de_dev_aceita_segredos_fortes():
    s = _settings(environment="producao", secret_key=CHAVE_FORTE, encryption_key=CHAVE_FERNET)
    assert s.secret_key.get_secret_value() == CHAVE_FORTE


def test_ambiente_desconhecido_e_tratado_como_fora_de_dev():
    with pytest.raises(ValidationError):
        _settings(environment="production")


def test_dev_aceita_chave_padrao():
    assert _settings(environment="dev").encryption_key is None


@pytest.mark.parametrize(("ambiente", "esperado"), [
    ("producao", CKAN_PORTAL_OFICIAL),
    ("homologacao", CKAN_LOCAL_DOCKER),
    ("dev", CKAN_LOCAL_DOCKER),
])
def test_ckan_padrao_pelo_ambiente(ambiente, esperado):
    s = _settings(environment=ambiente, secret_key=CHAVE_FORTE, encryption_key=CHAVE_FERNET)
    assert s.ckan_base_url == esperado


@pytest.mark.parametrize("ambiente", ["dev", "producao"])
def test_ckan_informado_prevalece_sobre_o_ambiente(ambiente):
    s = _settings(environment=ambiente, secret_key=CHAVE_FORTE, encryption_key=CHAVE_FERNET,
                  ckan_base_url="http://localhost:5000")
    assert s.ckan_base_url == "http://localhost:5000"


def test_ambiente_desconhecido_e_recusado_mesmo_com_segredos_fortes():
    with pytest.raises(ValidationError, match="GDA_ENVIRONMENT"):
        _settings(environment="production", secret_key=CHAVE_FORTE, encryption_key=CHAVE_FERNET)
