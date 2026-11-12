#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Verifica, sem alterar nada, se a extensao ckanext-dsaudit esta ativa no CKAN.
#
# Uso:
#   CKAN_URL=https://dados.exemplo.gov.br \
#   CKAN_API_KEY=<token de um usuario que edita o dataset> \
#   ./verificar_instalacao.sh [nome-ou-id-de-um-dataset]
#
# Variaveis (todas opcionais):
#   CKAN_INI   ckan.ini do servidor        (padrao: /etc/ckan/default/ckan.ini)
#   CKAN_VENV  ambiente virtual do CKAN    (padrao: /usr/lib/ckan/default)
#   CKAN_URL   endereco do CKAN            (padrao: ckan.site_url do CKAN_INI)
#
# Requer: curl e python3. So faz leituras (status_show e dsaudit_activity_list).
# ---------------------------------------------------------------------------
set -u

CKAN_INI="${CKAN_INI:-/etc/ckan/default/ckan.ini}"
CKAN_VENV="${CKAN_VENV:-/usr/lib/ckan/default}"
if [ -z "${CKAN_URL:-}" ] && [ -r "$CKAN_INI" ]; then
    CKAN_URL="$(sed -n 's/^[[:space:]]*ckan\.site_url[[:space:]]*=[[:space:]]*//p' "$CKAN_INI" | tail -1 | tr -d '\r')"
fi
CKAN_URL="${CKAN_URL:-http://localhost:5000}"
CKAN_URL="${CKAN_URL%/}"
DATASET="${1:-}"
FALHAS=0

ok()    { echo "[ OK ] $*"; }
falha() { echo "[FALHA] $*"; FALHAS=$((FALHAS + 1)); }
info()  { echo "[ -- ] $*"; }

campo() {  # campo <expressao python sobre d> ; le JSON da entrada padrao
    python3 -c "import json,sys
try:
    d=json.load(sys.stdin)
    print($1)
except Exception as e:
    print('ERRO: %s' % e)"
}

echo "CKAN: $CKAN_URL"

# 1) verificacoes locais no ambiente virtual (nao dependem do CKAN estar no ar)
PY="$CKAN_VENV/bin/python"
if [ -x "$PY" ]; then
    # .pth orfao de uma instalacao `pip install -e` antiga cuja pasta foi apagada
    for PTH in "$CKAN_VENV"/lib*/python3*/site-packages/*dsaudit*nspkg.pth; do
        [ -e "$PTH" ] || continue
        ORIGEM="$(sed -n "s/.*os\.path\.join('\([^']*\)'.*/\1/p" "$PTH" | head -1)"
        if [ -n "$ORIGEM" ] && [ ! -d "$ORIGEM/ckanext" ]; then
            falha "arquivo orfao $PTH (aponta para $ORIGEM, que nao existe mais): remova-o"
        fi
    done
    if MSG="$("$PY" -c 'import ckanext.dsaudit.plugins' 2>&1)"; then
        ok "ckanext.dsaudit importa no ambiente $CKAN_VENV"
    else
        falha "ckanext.dsaudit NAO importa em $CKAN_VENV: $(printf '%s' "$MSG" | tail -1)"
    fi
else
    info "ambiente virtual nao encontrado em $CKAN_VENV (defina CKAN_VENV para as verificacoes locais)"
fi

# 2) o CKAN responde e a extensao aparece entre os plugins carregados?
if ! STATUS="$(curl -sS --max-time 30 "$CKAN_URL/api/3/action/status_show" 2>&1)"; then
    falha "o CKAN nao respondeu em $CKAN_URL: $STATUS"
    echo "       Confira se o CKAN esta no ar (supervisorctl status; log do uWSGI) e se o"
    echo "       endereco esta certo: a porta 5000 so existe no 'ckan run'; com uWSGI vale a"
    echo "       porta de 'http =' no ckan-uwsgi.ini ou o endereco publico (CKAN_URL=...)."
    echo "Resultado: $FALHAS verificacao(oes) falharam."
    exit "$FALHAS"
fi
VERSAO="$(printf '%s' "$STATUS" | campo "d['result']['ckan_version']")"
PLUGINS="$(printf '%s' "$STATUS" | campo "' '.join(d['result']['extensions'])")"
case "$VERSAO" in
    2.9.*) ok "versao do CKAN: $VERSAO" ;;
    ERRO:*) falha "$CKAN_URL respondeu, mas nao com a API do CKAN ($VERSAO)" ;;
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

# 3) a API da extensao responde para um dataset?
if [ -z "$DATASET" ]; then
    info "informe um dataset para testar a API dsaudit_activity_list"
elif [ -z "${CKAN_API_KEY:-}" ]; then
    info "defina CKAN_API_KEY para testar a API dsaudit_activity_list"
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
