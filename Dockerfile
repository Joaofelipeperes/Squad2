# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# CKAN 2.9.5 + auditoria de alteracoes (ckanext-dsaudit, versao enxuta)
# ---------------------------------------------------------------------------
#
# Base: extensao oficial ckan/ckanext-dsaudit, fixada em um commit. Ela e
# escrita para CKAN 2.10/2.11 e quebra no 2.9.5; por isso o plugins.py e o
# actions.py dela sao substituidos pelos da pasta ckanext-dsaudit-ckan29/
# (correcoes para o 2.9 + captura completa), e o versions.py e acrescentado.
#
# Versao enxuta: so CAPTURA e ARMAZENA (tabela `activity` do banco do CKAN e
# versoes dos arquivos em /var/lib/ckan/dsaudit_versions). Sem telas: a
# leitura e pela API `dsaudit_activity_list`. Detalhes em
# ckanext-dsaudit-ckan29/README.md.
#
# Por que NAO ckanext-event-audit: exige CKAN >= 2.10 (ckan.types,
# ckan.config.declaration, ISignal, IConfigDeclaration, toolkit.blanket).
# ---------------------------------------------------------------------------

FROM ckan/ckan-base:2.9.5

# A imagem base roda como root: o start_ckan.sh dela usa `sudo -u ckan` para o
# prerun e para o uwsgi. NAO troque o usuario final (USER ckan).
USER root

# Commit fixado para builds reprodutiveis.
ARG DSAUDIT_REF=c3988427821c43e5dac5078c6adc42f7f16d3fa4
RUN pip3 install --no-cache-dir -e \
    "git+https://github.com/ckan/ckanext-dsaudit.git@${DSAUDIT_REF}#egg=ckanext-dsaudit"

# leitura de planilhas .xlsx para o diff linha a linha de arquivos enviados
RUN pip3 install --no-cache-dir "openpyxl==3.0.10"

# --- camada CKAN 2.9 (captura) sobre a extensao instalada ------------------
# Substitui plugins.py/actions.py, acrescenta versions.py e remove o que o
# upstream traz so para telas (views, helpers, templates).
COPY ckanext-dsaudit-ckan29/ /tmp/dsaudit-ckan29/
RUN set -eu; \
    SRC=/tmp/dsaudit-ckan29; \
    DST=/srv/app/src/ckanext-dsaudit/ckanext/dsaudit; \
    test -f "$DST/plugins.py"; \
    for f in plugins.py actions.py versions.py; do \
        sed 's/\r$//' "$SRC/$f" > "$DST/$f"; \
    done; \
    rm -rf "$DST/views.py" "$DST/helpers.py" "$DST/templates" "$DST/2.9_templates"; \
    if grep -rnE "in h\.datastore_rw_resource_url_types|from ckanext.dsaudit import .*(views|helpers)" "$DST"/*.py; then \
        echo "camada incompleta" >&2; exit 1; \
    fi; \
    python3 -m py_compile "$DST/plugins.py" "$DST/actions.py" "$DST/versions.py"; \
    rm -rf "$SRC"; \
    echo "ckanext-dsaudit: camada CKAN 2.9 (enxuta) aplicada"

# Timeout do uwsgi (harakiri) configuravel por UWSGI_HARAKIRI (segundos).
# Cargas grandes com auditoria completa levam mais tempo; se o worker for
# morto no meio da requisicao, a alteracao e desfeita e nao e registrada.
RUN set -eu; \
    F=/srv/app/start_ckan.sh; \
    if grep -qE -- '--harakiri' "$F"; then \
        sed -i -E 's/--harakiri[= ]+[^ "\\]+/--harakiri ${UWSGI_HARAKIRI:-300}/' "$F"; \
    else \
        echo "aviso: --harakiri nao encontrado em $F (nada alterado)"; \
    fi; \
    grep -nE -- '--harakiri' "$F" || true

# prerun corrigido (substitui /srv/app/prerun.py da imagem base) -- ver o
# cabecalho de docker/prerun.py para as correcoes.
COPY docker/prerun.py /srv/app/prerun.py
RUN sed -i 's/\r$//' /srv/app/prerun.py \
    && chown -R ckan:ckan /srv/app /var/lib/ckan
