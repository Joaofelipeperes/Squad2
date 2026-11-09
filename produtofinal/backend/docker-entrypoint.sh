#!/bin/sh
# Entrada da API e do worker (ADR-0032).
#
# 1. Segredos: no servidor, o serviço `segredos` do docker-compose.prod.yml os gera na primeira
#    subida num volume montado em /segredos. Aqui viram as variáveis GDA_* (a que já vier definida
#    no ambiente, por exemplo pelo .env, prevalece). Em dev não há /segredos e nada muda.
# 2. Volumes criados por versões anteriores (que rodavam como root) podem pertencer ao root: acerta
#    o dono da pasta da anonimização e segue sem privilégio (usuário gda).
set -e

SEGREDOS=/segredos
# carregar VARIAVEL arquivo [prefixo] [sufixo]: exporta VARIAVEL com o conteúdo do arquivo, se ela
# ainda estiver vazia e o arquivo existir
carregar() {
    eval "atual=\${$1:-}"
    [ -z "$atual" ] && [ -r "$SEGREDOS/$2" ] || return 0
    valor="$(tr -d '\r\n' < "$SEGREDOS/$2")"
    export "$1=${3:-}${valor}${4:-}"
}
if [ -d "$SEGREDOS" ]; then
    carregar GDA_SECRET_KEY secret_key
    carregar GDA_ENCRYPTION_KEY encryption_key
    carregar GDA_LGPD_SAL_HASH lgpd_sal_hash
    carregar GDA_DATABASE_URL db_senha "postgresql+psycopg://gda:" "@${GDA_DB_HOST:-db}:5432/gda"
fi

if [ "$(id -u)" = "0" ]; then
    mkdir -p /app/dados_lgpd
    chown -R gda:gda /app/dados_lgpd
    exec setpriv --reuid=gda --regid=gda --init-groups "$@"
fi
exec "$@"
