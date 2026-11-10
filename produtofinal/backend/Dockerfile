FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    # IP (ou CIDR) de quem o uvicorn aceita X-Forwarded-For (IP real do usuário no log, ADR-0016).
    # Padrão: ninguém além do próprio container. O compose informa o IP do nginx (container web).
    FORWARDED_ALLOW_IPS=127.0.0.1
# Cliente do PostgreSQL 16 (pg_dump e pg_restore) para os backups internos do banco (ADR-0034).
# Vem do repositório oficial do PostgreSQL (PGDG): a versão tem de ser a do servidor (postgres:16).
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gnupg \
    && install -d /usr/share/keyrings \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /usr/share/keyrings/pgdg.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/pgdg.gpg] https://apt.postgresql.org/pub/repos/apt $(. /etc/os-release && echo $VERSION_CODENAME)-pgdg main" > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client-16 \
    && apt-get purge -y --auto-remove curl gnupg \
    && rm -rf /var/lib/apt/lists/*
COPY . .
RUN pip install --no-cache-dir . \
    # Usuário sem privilégio (ADR-0032): a API e o worker não rodam como root
    && useradd --system --uid 10001 --home-dir /app --shell /usr/sbin/nologin gda \
    && mkdir -p /app/dados_lgpd && chown gda:gda /app/dados_lgpd \
    && chmod +x /app/docker-entrypoint.sh
EXPOSE 8000
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
