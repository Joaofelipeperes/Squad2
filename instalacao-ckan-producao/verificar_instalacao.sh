#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Verifica, sem alterar nada, se a extensao ckanext-dsaudit esta ativa no CKAN.
#
# Uso:
#   CKAN_URL=https://dados.exemplo.gov.br \
#   CKAN_API_KEY=<token de um usuario que edita o dataset> \
#   ./verificar_instalacao.sh [nome-ou-id-de-um-dataset]
#
# Requer: curl e python3. So faz leituras (status_show e dsaudit_activity_list).
# ---------------------------------------------------------------------------
set -u

CKAN_URL="${CKAN_URL:-http://localhost:5000}"
CKAN_URL="${CKAN_URL%/}"
DATASET="${1:-}"
FALHAS=0

ok()    { echo "[ OK ] $*"; }
falha() { echo "[FALHA] $*"; FALHAS=$((FALHAS + 1)); }

campo() {  # campo <expressao python sobre d> ; le JSON da entrada padrao
    python3 -c "import json,sys
try:
    d=json.load(sys.stdin)
    print($1)
except Exception as e:
    print('ERRO: %s' % e)"
}

echo "CKAN: $CKAN_URL"

# 1) a extensao aparece entre os plugins carregados?
STATUS="$(curl -sS --max-time 30 "$CKAN_URL/api/3/action/status_show")" || STATUS=""
VERSAO="$(printf '%s' "$STATUS" | campo "d['result']['ckan_version']")"
PLUGINS="$(printf '%s' "$STATUS" | campo "' '.join(d['result']['extensions'])")"
case "$VERSAO" in
    2.9.*) ok "versao do CKAN: $VERSAO" ;;
    *)     falha "versao do CKAN: '$VERSAO' (a extensao e para CKAN 2.9.x)" ;;
esac
case " $PLUGINS " in
    *" dsaudit "*) ok "plugin dsaudit carregado" ;;
    *)             falha "plugin dsaudit NAO carregado (plugins: $PLUGINS)" ;;
esac
case " $PLUGINS " in
    *" datastore "*) ok "plugin datastore carregado" ;;
    *)               falha "plugin datastore NAO carregado" ;;
esac

# 2) a API da extensao responde para um dataset?
if [ -z "$DATASET" ]; then
    echo "[ -- ] informe um dataset para testar a API dsaudit_activity_list"
elif [ -z "${CKAN_API_KEY:-}" ]; then
    echo "[ -- ] defina CKAN_API_KEY para testar a API dsaudit_activity_list"
else
    RESP="$(curl -sS --max-time 60 -H "Authorization: $CKAN_API_KEY" \
        "$CKAN_URL/api/3/action/dsaudit_activity_list?id=$DATASET&limit=1")" || RESP=""
    SUCESSO="$(printf '%s' "$RESP" | campo "d.get('success')")"
    if [ "$SUCESSO" = "True" ]; then
        TOTAL="$(printf '%s' "$RESP" | campo "d['result']['count']")"
        ok "dsaudit_activity_list respondeu ($TOTAL registro(s) de auditoria em '$DATASET')"
    else
        ERRO="$(printf '%s' "$RESP" | campo "d.get('error')")"
        falha "dsaudit_activity_list nao respondeu como esperado: $ERRO"
    fi
fi

if [ "$FALHAS" -eq 0 ]; then
    echo "Resultado: tudo certo."
else
    echo "Resultado: $FALHAS verificacao(oes) falharam."
fi
exit "$FALHAS"
