"""Configuração central, lida de variáveis de ambiente com prefixo GDA_ (ver .env.example).

Fora de dev, a aplicação NÃO inicia com chave JWT padrão, de exemplo ou curta, nem sem
GDA_ENCRYPTION_KEY: com a chave padrão (pública no repositório) qualquer um forjaria um token
de administrador.
"""
import logging
from functools import lru_cache

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger(__name__)

SECRET_KEY_MIN_BYTES = 32

AMBIENTES = ("dev", "homologacao", "producao")
# CKAN lido quando GDA_CKAN_BASE_URL não é informado (ADR-0024): o portal oficial só em produção;
# fora dela, o CKAN local do Docker da raiz (container_name fixo no docker-compose.yml da raiz).
CKAN_PORTAL_OFICIAL = "https://dadosabertos.go.gov.br"
CKAN_LOCAL_DOCKER = "http://ckansquad2-ckan-1:5000"


def ckan_padrao(ambiente: str) -> str:
    return CKAN_PORTAL_OFICIAL if ambiente == "producao" else CKAN_LOCAL_DOCKER


def chave_fraca(chave: str) -> bool:
    """Chave padrão ou de exemplo (ambas começam com "troque") ou com menos de 32 bytes."""
    return "troque" in chave.lower() or len(chave.encode()) < SECRET_KEY_MIN_BYTES


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GDA_", env_file=".env", extra="ignore")

    app_name: str = "Monitor Dados Abertos GO"
    environment: str = "dev"  # dev | homologacao | producao
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:5173"]

    # Banco — SQLite só para desenvolvimento local; PostgreSQL em homologação/produção
    database_url: str = "sqlite:///./dev.db"

    # Segurança
    secret_key: SecretStr = SecretStr("troque-esta-chave-em-producao-dev-0000")  # só vale em dev
    encryption_key: SecretStr | None = None  # chave Fernet para cifrar segredos (chaves de IA)
    jwt_expire_minutes: int = 480

    # CKAN — leitura pela API pública. Vazio = padrão do ambiente (ckan_padrao): portal oficial
    # em produção, CKAN local do Docker em homologação e dev.
    ckan_base_url: str | None = None
    ckan_timeout_s: float = 30.0
    ckan_page_size: int = 500
    ckan_max_retries: int = 3
    # CKAN — leitura da auditoria (extensão ckanext-dsaudit, ADR-0009). A API
    # dsaudit_activity_list exige permissão de EDITOR no dataset: use o token de um usuário
    # editor das organizações monitoradas (nunca de sysadmin em produção). Vazio = a
    # rastreabilidade não sincroniza.
    ckan_auditoria_api_token: SecretStr | None = None

    # CKAN — escrita (somente publicação de recurso anonimizado, US26 / PBI-95)
    # Permanece desligada até a autorização formal CGE-GO/SECTI. Credencial é da GEDA.
    ckan_write_enabled: bool = False
    ckan_write_base_url: str | None = None  # por padrão, o mesmo de ckan_base_url
    ckan_write_api_token: SecretStr | None = None

    # Agendamento (US23)
    coleta_cron: str = "0 3 * * *"  # todo dia às 03:00
    # Varredura LGPD incremental (PBI-34): recursos novos ou alterados, depois da coleta
    lgpd_varredura_cron: str = "0 5 * * *"
    lgpd_varredura_max_recursos: int = 200  # por execução (o modelo local é lento em CPU)
    # Anonimização (US26): cópia do original e prévia ficam FORA do banco, nesta pasta (no Docker,
    # um volume). Contém dado pessoal: nunca versionar; retenção definida pela GEDA.
    lgpd_arquivos_dir: str = "dados_lgpd"
    lgpd_sal_hash: SecretStr | None = None  # sal do operador "hash"; vazio = deriva da secret_key
    timezone: str = "America/Sao_Paulo"

    # IA — política de dados sensíveis
    # False (padrão): tarefas que tocam dado pessoal só podem usar provedor marcado como LOCAL.
    ia_permitir_externo_para_sensivel: bool = False

    @model_validator(mode="after")
    def _ckan_do_ambiente(self) -> "Settings":
        if self.environment not in AMBIENTES:
            raise ValueError(f"GDA_ENVIRONMENT={self.environment!r} inválido; "
                             f"use {' | '.join(AMBIENTES)}.")
        if not self.ckan_base_url:
            self.ckan_base_url = ckan_padrao(self.environment)
        return self

    @model_validator(mode="after")
    def _exigir_segredos_fora_de_dev(self) -> "Settings":
        fraca = chave_fraca(self.secret_key.get_secret_value())
        if self.environment == "dev":
            if fraca:
                log.warning("GDA_SECRET_KEY padrão ou fraca: aceita só porque GDA_ENVIRONMENT=dev.")
            return self
        if fraca:
            raise ValueError(
                f"GDA_SECRET_KEY padrão, de exemplo ou com menos de {SECRET_KEY_MIN_BYTES} bytes "
                f"(GDA_ENVIRONMENT={self.environment}). Gere uma com: "
                "python -c \"import secrets; print(secrets.token_urlsafe(48))\"")
        if not self.encryption_key or not self.encryption_key.get_secret_value():
            raise ValueError(
                f"GDA_ENCRYPTION_KEY é obrigatória fora de dev (GDA_ENVIRONMENT={self.environment})."
                " Gere com: python -m app.cli gerar-chave")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
