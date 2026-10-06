"""Configuração central, lida de variáveis de ambiente com prefixo GDA_ (ver .env.example)."""
from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GDA_", env_file=".env", extra="ignore")

    app_name: str = "Monitor Dados Abertos GO"
    environment: str = "dev"  # dev | homologacao | producao
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:5173"]

    # Banco — SQLite só para desenvolvimento local; PostgreSQL em homologação/produção
    database_url: str = "sqlite:///./dev.db"

    # Segurança
    secret_key: SecretStr = SecretStr("troque-esta-chave-em-producao-dev-0000")
    encryption_key: SecretStr | None = None  # chave Fernet para cifrar segredos (chaves de IA)
    jwt_expire_minutes: int = 480

    # CKAN — leitura pela API pública
    ckan_base_url: str = "https://dadosabertos.go.gov.br"
    ckan_timeout_s: float = 30.0
    ckan_page_size: int = 500
    ckan_max_retries: int = 3

    # CKAN — escrita (somente publicação de recurso anonimizado, US26 / PBI-95)
    # Permanece desligada até a autorização formal CGE-GO/SECTI. Credencial é da GEDA.
    ckan_write_enabled: bool = False
    ckan_write_base_url: str | None = None  # por padrão, o mesmo de ckan_base_url
    ckan_write_api_token: SecretStr | None = None

    # Agendamento (US23)
    coleta_cron: str = "0 3 * * *"  # todo dia às 03:00
    timezone: str = "America/Sao_Paulo"

    # IA — política de dados sensíveis
    # False (padrão): tarefas que tocam dado pessoal só podem usar provedor marcado como LOCAL.
    ia_permitir_externo_para_sensivel: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
