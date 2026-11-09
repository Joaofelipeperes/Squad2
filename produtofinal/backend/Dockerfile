FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    # IP (ou CIDR) de quem o uvicorn aceita X-Forwarded-For (IP real do usuário no log, ADR-0016).
    # Padrão: ninguém além do próprio container. O compose informa o IP do nginx (container web).
    FORWARDED_ALLOW_IPS=127.0.0.1
COPY . .
RUN pip install --no-cache-dir . \
    # Usuário sem privilégio (ADR-0032): a API e o worker não rodam como root
    && useradd --system --uid 10001 --home-dir /app --shell /usr/sbin/nologin gda \
    && mkdir -p /app/dados_lgpd && chown gda:gda /app/dados_lgpd \
    && chmod +x /app/docker-entrypoint.sh
EXPOSE 8000
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
