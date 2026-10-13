# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# CKAN 2.9.5 + auditoria de alteracoes (ckanext-dsaudit, versao enxuta)
# ---------------------------------------------------------------------------
#
# A extensao fica INTEIRA neste repositorio, em ckanext-dsaudit/ (codigo
# vendorizado). Origem: ckan/ckanext-dsaudit @ c3988427821c43e5dac5078c6adc42f7f16d3fa4,
# ja com as correcoes para o CKAN 2.9 (plugins.py, actions.py, versions.py) e
# sem o que so servia para telas (views, helpers, templates). O build nao
# baixa mais nada do GitHub. Detalhes em ckanext-dsaudit/README-CKAN29.md.
#
# Versao enxuta: so CAPTURA e ARMAZENA (tabela `activity` do banco do CKAN e
# versoes dos arquivos em /var/lib/ckan/dsaudit_versions). Sem telas: a
# leitura e pela API `dsaudit_activity_list`.
#
# Por que NAO ckanext-event-audit: exige CKAN >= 2.10 (ckan.types,
# ckan.config.declaration, ISignal, IConfigDeclaration, toolkit.blanket).
# ---------------------------------------------------------------------------

FROM ckan/ckan-base:2.9.5

# A imagem base roda como root: o start_ckan.sh dela usa `sudo -u ckan` para o
# prerun e para o uwsgi. NAO troque o usuario final (USER ckan).
USER root

# leitura de planilhas .xlsx para o diff linha a linha de arquivos enviados
RUN pip3 install --no-cache-dir "openpyxl==3.0.10"

# --- extensao dsaudit (codigo local) ---------------------------------------
# Mesmo caminho que o `pip install -e git+...` usava antes.
COPY ckanext-dsaudit/ /srv/app/src/ckanext-dsaudit/
RUN set -eu; \
    DST=/srv/app/src/ckanext-dsaudit; \
    find "$DST" -type f \( -name '*.py' -o -name '*.cfg' \) -exec sed -i 's/\r$//' {} +; \
    pip3 install --no-cache-dir -e "$DST"; \
    python3 -m py_compile "$DST"/ckanext/dsaudit/*.py; \
    echo "ckanext-dsaudit: instalada a partir de ckanext-dsaudit/"

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
