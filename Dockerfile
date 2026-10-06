# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# CKAN 2.9.5 + auditoria detalhada de alteracoes no DataStore (ckanext-dsaudit)
# ---------------------------------------------------------------------------
#
# ESTE DOCKERFILE E AUTOCONTIDO: todos os arquivos da camada de compatibilidade
# e o prerun corrigido estao embutidos abaixo (blocos COPY <<"..."). Para o
# build so sao necessarios Dockerfile, docker-compose.yml e init-db/.
#
# Por que NAO ckanext-event-audit: exige CKAN >= 2.10 (ckan.types,
# ckan.config.declaration, ISignal, IConfigDeclaration, toolkit.blanket).
#
# O que usamos: ckanext-dsaudit (repositorio oficial ckan/ckanext-dsaudit),
# fixado em um commit, + camada de compatibilidade CKAN 2.9 que substitui
# plugins/actions/helpers/views e os templates 2.9. O upstream sozinho quebra
# no 2.9.5 (datastore_info sem 'fields', helper do 2.11, template inexistente,
# activity.data descartado pelo package_activity_list do 2.9). Ver README.
#
# Alem do DataStore, a camada registra (aba Auditoria do dataset):
#   * metadados do dataset/recursos campo a campo, inclusive datasets privados
#     ('changed metadata': autor, e-mail do autor, titulo, tags, extras...);
#   * arquivos enviados pela interface/API: todas as versoes guardadas em
#     /var/lib/ckan/dsaudit_versions e diff linha a linha de CSV/TSV/XLSX
#     ('changed resource file').
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

# ===========================================================================
# Camada de compatibilidade CKAN 2.9 + auditoria linha a linha
# (gravada em /tmp/dsaudit-ckan29 e copiada sobre a extensao instalada)
# ===========================================================================

# --- 2.9_templates/dsaudit/audit.html ---
COPY <<"DSAUDIT_FILE_00" /tmp/dsaudit-ckan29/2.9_templates/dsaudit/audit.html
{% extends "package/read_base.html" %}

{% block subtitle %}Auditoria {{ g.template_title_delimiter }} {{ super() }}{% endblock %}

{% block primary_content_inner %}
  <h2>Auditoria de altera&ccedil;&otilde;es</h2>
  <p class="text-muted">
    Todas as altera&ccedil;&otilde;es deste dataset, com usu&aacute;rio, data/hora e valor anterior &rarr; novo:
    metadados do dataset e dos recursos (autor, e-mail do autor, t&iacute;tulo, descri&ccedil;&atilde;o, tags, extras...),
    arquivos enviados pela interface ou API (cada vers&atilde;o guardada, com diff linha a linha para CSV/XLSX)
    e linhas dos recursos DataStore.
  </p>

  <form method="get" class="form-inline" style="margin-bottom: 15px;">
    <select name="resource_id" class="form-control">
      <option value="">Todos os recursos</option>
      {% for r in pkg_dict.resources %}
        <option value="{{ r.id }}" {% if r.id == resource_id %}selected{% endif %}>{{ r.name or r.id }}</option>
      {% endfor %}
    </select>
    <select name="activity_type" class="form-control">
      <option value="">Todos os tipos</option>
      <option value="changed metadata" {% if activity_type == 'changed metadata' %}selected{% endif %}>Metadados do dataset / recursos</option>
      <option value="changed resource file" {% if activity_type == 'changed resource file' %}selected{% endif %}>Arquivos enviados (upload)</option>
      <option value="changed datastore" {% if activity_type == 'changed datastore' %}selected{% endif %}>DataStore: inser&ccedil;&otilde;es / altera&ccedil;&otilde;es</option>
      <option value="deleted datastore" {% if activity_type == 'deleted datastore' %}selected{% endif %}>DataStore: exclus&otilde;es</option>
      <option value="created datastore" {% if activity_type == 'created datastore' %}selected{% endif %}>DataStore: estrutura da tabela</option>
    </select>
    <button type="submit" class="btn btn-default">Filtrar</button>
    <a class="btn btn-primary" href="{{ h.url_for('dsaudit.audit_csv', id=pkg.name, resource_id=resource_id) }}">
      <i class="fa fa-download"></i> Exportar CSV
    </a>
  </form>

  <p><strong>{{ count }}</strong> evento(s)</p>

  {% if activity_stream %}
    {% snippet 'snippets/activity_stream.html', activity_stream=activity_stream, id=id, object_type='package' %}
  {% else %}
    <p class="empty">Nenhuma altera&ccedil;&atilde;o registrada.</p>
  {% endif %}

  {% set last_page = ((count - 1) // per_page) + 1 if count else 1 %}
  {% if last_page > 1 %}
    <ul class="pager">
      {% if page > 1 %}
        <li class="previous"><a href="{{ h.url_for('dsaudit.audit', id=pkg.name, resource_id=resource_id, activity_type=activity_type, page=page - 1) }}">&larr; Mais recentes</a></li>
      {% endif %}
      <li>P&aacute;gina {{ page }} de {{ last_page }}</li>
      {% if page < last_page %}
        <li class="next"><a href="{{ h.url_for('dsaudit.audit', id=pkg.name, resource_id=resource_id, activity_type=activity_type, page=page + 1) }}">Mais antigas &rarr;</a></li>
      {% endif %}
    </ul>
  {% endif %}
{% endblock %}
DSAUDIT_FILE_00

# --- 2.9_templates/package/read_base.html ---
COPY <<"DSAUDIT_FILE_01" /tmp/dsaudit-ckan29/2.9_templates/package/read_base.html
{% ckan_extends %}

{# ckanext-dsaudit: aba "Auditoria" para quem pode editar o dataset #}
{% block content_primary_nav %}
  {{ super() }}
  {% if not is_activity_archive and h.check_access('package_update', {'id': pkg.id}) %}
    <li class="{% if request.path.endswith('/auditoria') %}active{% endif %}">
      <a href="{{ h.url_for('dsaudit.audit', id=pkg.name) }}"><i class="fa fa-history"></i> Auditoria</a>
    </li>
  {% endif %}
{% endblock %}
DSAUDIT_FILE_01

# --- 2.9_templates/snippets/activities/changed_datastore.html ---
COPY <<"DSAUDIT_FILE_02" /tmp/dsaudit-ckan29/2.9_templates/snippets/activities/changed_datastore.html
{#
  ckanext-dsaudit (CKAN 2.9) -- alteracao de registros do DataStore.
  Mostra, quando disponivel, o diff linha a linha (valor anterior -> novo)
  capturado por actions.datastore_upsert; caso contrario, as linhas enviadas.
#}
{% macro resource(act) %}
  <a href="{{ h.dsaudit_resource_url(act.object_id, act.data.resource_id) }}">{{ h.dsaudit_resource_name(act.data.resource_id) }}</a>
{% endmacro %}

{% set data = activity.data %}
{% set preview = h.dsaudit_preview_records() %}
{% set total = data.total if 'total' in data else data.count if 'count' in data else (data.records or [])|count %}

{% if 'resource_id' not in activity.data %}
  {# sem permissao de edicao: o CKAN 2.9 remove activity.data #}
  <li class="item {{ activity.activity_type|replace(' ', '-')|lower }}">
    <i class="fa icon fa-database"></i>
    <p>
      {{ ah.actor(activity) }} alterou registros do DataStore
      <br />
      <span class="date" title="{{ h.render_datetime(activity.timestamp, with_hours=True) }}">
        {{ h.time_ago_from_timestamp(activity.timestamp) }}
      </span>
    </p>
  </li>
{% else %}
<li class="item {{ activity.activity_type|replace(' ', '-')|lower }}">
  <i class="fa icon fa-pencil"></i>
  <p>
    {% if data.method == 'insert' %}
      {% set verb = 'inseriu' %}
    {% elif data.method == 'update' %}
      {% set verb = 'atualizou' %}
    {% else %}
      {% set verb = 'inseriu/atualizou (upsert)' %}
    {% endif %}
    {{ ah.actor(activity) }} {{ verb }} {{ total }} registro(s) no recurso {{ resource(activity) }}
    {% if data.changes %}
      {% set upd = data.changes|selectattr('status', 'equalto', 'updated')|list|count %}
      {% set ins = data.changes|selectattr('status', 'equalto', 'inserted')|list|count %}
      {% set unc = data.changes|selectattr('status', 'equalto', 'unchanged')|list|count %}
      <small class="text-muted">&mdash; {{ upd }} alterada(s), {{ ins }} nova(s), {{ unc }} sem mudan&ccedil;a</small>
    {% endif %}
    <br />
    <span class="date" title="{{ h.render_datetime(activity.timestamp, with_hours=True) }}">
      {{ h.time_ago_from_timestamp(activity.timestamp) }}
      &middot; {{ h.render_datetime(activity.timestamp, with_hours=True) }}
    </span>
  </p>

  {% if data.changes %}
    <div class="dsaudit-diff" style="margin: 5px 0 10px 40px; overflow-x: auto;">
      <table class="table table-condensed table-bordered" style="font-size: 12px;">
        <thead>
          <tr>
            <th>Linha (chave)</th>
            <th>_id</th>
            <th>Status</th>
            <th>Campo</th>
            <th>Valor anterior</th>
            <th>Valor novo</th>
          </tr>
        </thead>
        <tbody>
          {% for c in data.changes[:preview] %}
            {% set keytxt = [] %}
            {% for k, v in c.key.items() %}{% do keytxt.append(k ~ '=' ~ v) %}{% endfor %}
            {% set nfields = c.fields|count if c.fields else 1 %}
            {% if c.fields %}
              {% for f in c.fields %}
                <tr>
                  {% if loop.first %}
                    <td rowspan="{{ nfields }}"><code>{{ keytxt|join(', ') }}</code></td>
                    <td rowspan="{{ nfields }}">{{ c.row_id if c.row_id is not none else '' }}</td>
                    <td rowspan="{{ nfields }}">
                      {% if c.status == 'updated' %}<span class="label label-warning">alterada</span>
                      {% elif c.status == 'inserted' %}<span class="label label-success">nova</span>
                      {% else %}<span class="label label-default">sem mudan&ccedil;a</span>{% endif %}
                    </td>
                  {% endif %}
                  <td><strong>{{ f.field }}</strong></td>
                  <td style="background:#fdecea;">{% if f.old is none %}<em class="text-muted">(vazio)</em>{% else %}{{ f.old }}{% endif %}</td>
                  <td style="background:#e8f5e9;">{% if f.new is none %}<em class="text-muted">(vazio)</em>{% else %}{{ f.new }}{% endif %}</td>
                </tr>
              {% endfor %}
            {% else %}
              <tr>
                <td><code>{{ keytxt|join(', ') }}</code></td>
                <td>{{ c.row_id if c.row_id is not none else '' }}</td>
                <td><span class="label label-default">sem mudan&ccedil;a</span></td>
                <td colspan="3" class="text-muted">nenhum campo alterado</td>
              </tr>
            {% endif %}
          {% endfor %}
          {% if data.changes|count > preview %}
            <tr><td colspan="6">... mais {{ data.changes|count - preview }} linha(s) &mdash; registro completo no CSV da p&aacute;gina Auditoria</td></tr>
          {% endif %}
        </tbody>
      </table>
    </div>
  {% elif data.records %}
    {% set cols = h.dsaudit_data_columns(data) %}
    <div style="margin: 5px 0 10px 40px; overflow-x: auto;">
      <table class="table table-condensed table-bordered" style="font-size: 12px;">
        <thead>
          <tr>{% for col in cols %}<th scope="col">{{ col }}</th>{% endfor %}</tr>
        </thead>
        <tbody>
          {% for r in data.records[:preview] %}
            <tr>{% for col in cols %}<td>{{ r.get(col, '') }}</td>{% endfor %}</tr>
          {% endfor %}
          {% if data.records|count > preview %}
            <tr><td colspan="{{ cols|count }}">... mais {{ data.records|count - preview }} linha(s)</td></tr>
          {% endif %}
        </tbody>
      </table>
    </div>
  {% endif %}
</li>
{% endif %}
DSAUDIT_FILE_02

# --- 2.9_templates/snippets/activities/created_datastore.html ---
COPY <<"DSAUDIT_FILE_03" /tmp/dsaudit-ckan29/2.9_templates/snippets/activities/created_datastore.html
{#
  ckanext-dsaudit (CKAN 2.9) -- (re)definicao da tabela do DataStore.
  O template upstream usa datastore/snippets/dictionary_view.html, que nao
  existe no CKAN 2.9 (TemplateNotFound -> erro 500 na aba Atividade).
#}
{% macro resource(act) %}
  <a href="{{ h.dsaudit_resource_url(act.object_id, act.data.resource_id) }}">{{ h.dsaudit_resource_name(act.data.resource_id) }}</a>
{% endmacro %}

{% if 'resource_id' not in activity.data %}
  {# sem permissao de edicao: o CKAN 2.9 remove activity.data #}
  <li class="item {{ activity.activity_type|replace(' ', '-')|lower }}">
    <i class="fa icon fa-database"></i>
    <p>
      {{ ah.actor(activity) }} alterou a estrutura de uma tabela do DataStore
      <br />
      <span class="date" title="{{ h.render_datetime(activity.timestamp, with_hours=True) }}">
        {{ h.time_ago_from_timestamp(activity.timestamp) }}
      </span>
    </p>
  </li>
{% else %}
<li class="item {{ activity.activity_type|replace(' ', '-')|lower }}">
  <i class="fa icon fa-code"></i>
  <p>
    {% if activity.data.get('existing') %}
      {{ ah.actor(activity) }} redefiniu a tabela do DataStore do recurso {{ resource(activity) }}
    {% else %}
      {{ ah.actor(activity) }} criou a tabela do DataStore do recurso {{ resource(activity) }}
    {% endif %}
    <br />
    <span class="date" title="{{ h.render_datetime(activity.timestamp, with_hours=True) }}">
      {{ h.time_ago_from_timestamp(activity.timestamp) }}
      &middot; {{ h.render_datetime(activity.timestamp, with_hours=True) }}
    </span>
  </p>
  {% if activity.data.fields %}
    <div style="margin: 5px 0 10px 40px; overflow-x: auto;">
      <table class="table table-condensed table-bordered" style="font-size: 12px;">
        <thead><tr><th>Coluna</th><th>Tipo</th><th>R&oacute;tulo</th></tr></thead>
        <tbody>
          {% for f in activity.data.fields %}
            <tr>
              <td>{{ f.id }}</td>
              <td>{{ f.type }}</td>
              <td>{{ (f.get('info') or {}).get('label', '') }}</td>
            </tr>
          {% endfor %}
        </tbody>
      </table>
      {% if activity.data.primary_key %}
        <small class="text-muted">Chave prim&aacute;ria: {{ activity.data.primary_key if activity.data.primary_key is string else activity.data.primary_key|join(', ') }}</small>
      {% endif %}
    </div>
  {% endif %}
</li>
{% endif %}
DSAUDIT_FILE_03

# --- 2.9_templates/snippets/activities/deleted_datastore.html ---
COPY <<"DSAUDIT_FILE_04" /tmp/dsaudit-ckan29/2.9_templates/snippets/activities/deleted_datastore.html
{#
  ckanext-dsaudit (CKAN 2.9) -- exclusao de registros / tabela do DataStore.
  Quando a exclusao usa filtros, as linhas removidas (conteudo completo) ficam
  gravadas em activity.data.records.
#}
{% macro resource(act) %}
  <a href="{{ h.dsaudit_resource_url(act.object_id, act.data.resource_id) }}">{{ h.dsaudit_resource_name(act.data.resource_id) }}</a>
{% endmacro %}

{% set data = activity.data %}
{% set preview = h.dsaudit_preview_records() %}

{% if 'resource_id' not in activity.data %}
  {# sem permissao de edicao: o CKAN 2.9 remove activity.data #}
  <li class="item {{ activity.activity_type|replace(' ', '-')|lower }}">
    <i class="fa icon fa-database"></i>
    <p>
      {{ ah.actor(activity) }} excluiu registros do DataStore
      <br />
      <span class="date" title="{{ h.render_datetime(activity.timestamp, with_hours=True) }}">
        {{ h.time_ago_from_timestamp(activity.timestamp) }}
      </span>
    </p>
  </li>
{% else %}
<li class="item {{ activity.activity_type|replace(' ', '-')|lower }}">
  <i class="fa icon fa-trash"></i>
  <p>
    {% if data.filters %}
      {{ ah.actor(activity) }} excluiu {{ data.total if data.total is not none else (data.records or [])|count }} registro(s) do recurso {{ resource(activity) }}
    {% else %}
      {{ ah.actor(activity) }} excluiu a tabela do DataStore do recurso {{ resource(activity) }}
      {% if data.records %}({{ data.records|count }} registro(s) guardado(s) na auditoria){% endif %}
    {% endif %}
    <br />
    <span class="date" title="{{ h.render_datetime(activity.timestamp, with_hours=True) }}">
      {{ h.time_ago_from_timestamp(activity.timestamp) }}
      &middot; {{ h.render_datetime(activity.timestamp, with_hours=True) }}
    </span>
  </p>
  {% if data.filters %}
    <div style="margin: 5px 0 0 40px;">
      <small class="text-muted">Filtros:
        {% for k, v in data.filters.items() %}<code>{{ k }}={{ v }}</code> {% endfor %}
      </small>
    </div>
  {% endif %}
  {% if data.records %}
    {% set cols = h.dsaudit_data_columns(data) %}
    <div style="margin: 5px 0 10px 40px; overflow-x: auto;">
      <table class="table table-condensed table-bordered" style="font-size: 12px;">
        <thead>
          <tr>{% for col in cols %}<th scope="col">{{ col }}</th>{% endfor %}</tr>
        </thead>
        <tbody>
          {% for r in data.records[:preview] %}
            <tr style="background:#fdecea;">{% for col in cols %}<td>{{ r.get(col, '') }}</td>{% endfor %}</tr>
          {% endfor %}
          {% if data.records|count > preview %}
            <tr><td colspan="{{ cols|count }}">... mais {{ data.records|count - preview }} linha(s)</td></tr>
          {% endif %}
        </tbody>
      </table>
    </div>
  {% endif %}
</li>
{% endif %}
DSAUDIT_FILE_04

# --- 2.9_templates/snippets/activities/changed_metadata.html ---
COPY <<"DSAUDIT_FILE_10" /tmp/dsaudit-ckan29/2.9_templates/snippets/activities/changed_metadata.html
{#
  ckanext-dsaudit (CKAN 2.9) -- metadados do dataset campo a campo
  (autor, e-mail do autor, titulo, descricao, tags, extras, recursos...).
  Eventos de datasets privados so aparecem para quem pode ve-los.
#}
{% if h.check_access('package_show', {'id': activity.object_id}) %}
{% set data = activity.data %}
{% set preview = h.dsaudit_preview_records() %}
<li class="item changed-metadata">
  <i class="fa icon fa-pencil-square-o"></i>
  <p>
    {% if data.method == 'created' %}{% set verb = 'criou o dataset' %}
    {% elif data.method == 'deleted' %}{% set verb = 'excluiu o dataset' %}
    {% else %}{% set verb = 'alterou os metadados do dataset' %}{% endif %}
    {{ ah.actor(activity) }} {{ verb }} {{ ah.dataset(activity) }}
    {% if data.changes %}<small class="text-muted">&mdash; {{ data.changes|count }} campo(s)</small>{% endif %}
    <br />
    <span class="date" title="{{ h.render_datetime(activity.timestamp, with_hours=True) }}">
      {{ h.time_ago_from_timestamp(activity.timestamp) }}
      &middot; {{ h.render_datetime(activity.timestamp, with_hours=True) }}
    </span>
  </p>
  {% if data.changes %}
    <div style="margin: 5px 0 10px 40px; overflow-x: auto;">
      <table class="table table-condensed table-bordered" style="font-size: 12px;">
        <thead>
          <tr><th>Onde</th><th>Campo</th><th>Valor anterior</th><th>Valor novo</th></tr>
        </thead>
        <tbody>
          {% for c in data.changes[:preview] %}
            <tr>
              <td>
                {% if c.scope == 'dataset' %}Dataset{% else %}Recurso <em>{{ c.resource_name }}</em>
                  {% if c.status == 'added' %}<span class="label label-success">novo</span>
                  {% elif c.status == 'removed' %}<span class="label label-danger">removido</span>{% endif %}
                {% endif %}
              </td>
              <td><strong>{{ c.field }}</strong></td>
              <td style="background:#fdecea;">{% if c.old is none or c.old == '' %}<em class="text-muted">(vazio)</em>{% else %}{{ c.old }}{% endif %}</td>
              <td style="background:#e8f5e9;">{% if c.new is none or c.new == '' %}<em class="text-muted">(vazio)</em>{% else %}{{ c.new }}{% endif %}</td>
            </tr>
          {% endfor %}
          {% if data.changes|count > preview %}
            <tr><td colspan="4">... mais {{ data.changes|count - preview }} campo(s) &mdash; registro completo no CSV da p&aacute;gina Auditoria</td></tr>
          {% endif %}
        </tbody>
      </table>
    </div>
  {% endif %}
</li>
{% endif %}
DSAUDIT_FILE_10

# --- 2.9_templates/snippets/activities/changed_resource_file.html ---
COPY <<"DSAUDIT_FILE_11" /tmp/dsaudit-ckan29/2.9_templates/snippets/activities/changed_resource_file.html
{#
  ckanext-dsaudit (CKAN 2.9) -- arquivo enviado (upload) criado ou
  substituido, com as versoes guardadas e o diff linha a linha.
#}
{% if h.check_access('package_show', {'id': activity.object_id}) %}
{% set data = activity.data %}
{% set preview = h.dsaudit_preview_records() %}
{% set editor = 'resource_id' in data and h.check_access('package_update', {'id': activity.object_id}) %}
{% macro vlink(v, editor, oid, rid) %}
  {%- if editor and v -%}
    <a href="{{ h.url_for('dsaudit.version', id=oid, resource_id=rid, version=v.version) }}"
       title="sha256 {{ v.sha256 }}"><i class="fa fa-download"></i> {{ v.filename }} (v{{ v.version }}, {{ h.localised_filesize(v.size or 0) }})</a>
  {%- elif v -%}{{ v.filename }} (v{{ v.version }}){%- endif -%}
{% endmacro %}
<li class="item changed-resource-file">
  <i class="fa icon fa-file-text-o"></i>
  <p>
    {% if 'resource_id' not in data %}
      {{ ah.actor(activity) }} enviou/substituiu um arquivo em {{ ah.dataset(activity) }}
    {% else %}
      {{ ah.actor(activity) }}
      {% if data.method == 'new' %}enviou o arquivo{% else %}substituiu o arquivo{% endif %}
      do recurso <a href="{{ h.dsaudit_resource_url(activity.object_id, data.resource_id) }}">{{ h.dsaudit_resource_name(data.resource_id) }}</a>
      {% if data.changes is defined and data.changes is not none %}
        {% set upd = data.changes|selectattr('status', 'equalto', 'updated')|list|count %}
        {% set ins = data.changes|selectattr('status', 'equalto', 'inserted')|list|count %}
        {% set dlt = data.changes|selectattr('status', 'equalto', 'deleted')|list|count %}
        <small class="text-muted">&mdash; {{ upd }} linha(s) alterada(s), {{ ins }} nova(s), {{ dlt }} removida(s), {{ data.unchanged }} sem mudan&ccedil;a
          ({{ data.rows_old }} &rarr; {{ data.rows_new }} linhas;
          compara&ccedil;&atilde;o por {% if data.mode == 'chave' %}chave <code>{{ data['keys']|join(', ') }}</code>{% else %}posi&ccedil;&atilde;o da linha{% endif %})</small>
      {% elif data.rows_new is defined %}
        <small class="text-muted">&mdash; {{ data.rows_new }} linha(s), {{ (data.columns or [])|count }} coluna(s)</small>
      {% endif %}
    {% endif %}
    <br />
    <span class="date" title="{{ h.render_datetime(activity.timestamp, with_hours=True) }}">
      {{ h.time_ago_from_timestamp(activity.timestamp) }}
      &middot; {{ h.render_datetime(activity.timestamp, with_hours=True) }}
    </span>
  </p>
  {% if 'resource_id' in data %}
    <div style="margin: 0 0 5px 40px;">
      <small>
        {% if data.previous_version %}Anterior: {{ vlink(data.previous_version, editor, activity.object_id, data.resource_id) }} &middot; {% endif %}
        Nova: {{ vlink(data.version, editor, activity.object_id, data.resource_id) }}
        {% if data.columns_added %}&middot; colunas novas: <code>{{ data.columns_added|join(', ') }}</code>{% endif %}
        {% if data.columns_removed %}&middot; colunas removidas: <code>{{ data.columns_removed|join(', ') }}</code>{% endif %}
      </small>
      {% if data.diff_error %}<br /><small class="text-warning">{{ data.diff_error }}</small>{% endif %}
    </div>
  {% endif %}
  {% if data.changes %}
    <div class="dsaudit-diff" style="margin: 5px 0 10px 40px; overflow-x: auto;">
      <table class="table table-condensed table-bordered" style="font-size: 12px;">
        <thead>
          <tr><th>Linha</th><th>Status</th><th>Campo</th><th>Valor anterior</th><th>Valor novo</th></tr>
        </thead>
        <tbody>
          {% for c in data.changes[:preview] %}
            {% set keytxt = [] %}
            {% for k, v in c.key.items() %}{% do keytxt.append(k ~ '=' ~ v) %}{% endfor %}
            {% set nfields = c.fields|count if c.fields else 1 %}
            {% for f in (c.fields or [{'field': '', 'old': none, 'new': none}]) %}
              <tr>
                {% if loop.first %}
                  <td rowspan="{{ nfields }}"><code>{{ keytxt|join(', ') }}</code></td>
                  <td rowspan="{{ nfields }}">
                    {% if c.status == 'updated' %}<span class="label label-warning">alterada</span>
                    {% elif c.status == 'inserted' %}<span class="label label-success">nova</span>
                    {% else %}<span class="label label-danger">removida</span>{% endif %}
                  </td>
                {% endif %}
                <td><strong>{{ f.field }}</strong></td>
                <td style="background:#fdecea;">{% if f.old is none %}<em class="text-muted">(vazio)</em>{% else %}{{ f.old }}{% endif %}</td>
                <td style="background:#e8f5e9;">{% if f.new is none %}<em class="text-muted">(vazio)</em>{% else %}{{ f.new }}{% endif %}</td>
              </tr>
            {% endfor %}
          {% endfor %}
          {% if data.changes|count > preview %}
            <tr><td colspan="5">... mais {{ data.changes|count - preview }} linha(s) &mdash; registro completo no CSV da p&aacute;gina Auditoria</td></tr>
          {% endif %}
        </tbody>
      </table>
    </div>
  {% endif %}
</li>
{% endif %}
DSAUDIT_FILE_11

# --- actions.py ---
COPY <<"DSAUDIT_FILE_05" /tmp/dsaudit-ckan29/actions.py
# -*- coding: utf-8 -*-
"""
ckanext-dsaudit -- actions adaptadas para CKAN 2.9.5
====================================================

Este arquivo SUBSTITUI ckanext/dsaudit/actions.py do commit fixado no
Dockerfile (ckan/ckanext-dsaudit@c398842). O upstream e escrito para CKAN
2.10/2.11 e quebra no 2.9 em quatro pontos:

1. h.datastore_rw_resource_url_types() -> helper so existe no CKAN 2.11.
   No 2.9 o unico url_type gravavel do DataStore e 'datastore'.
2. datastore_info()['fields'] -> no 2.9 datastore_info devolve apenas
   {'schema': ..., 'meta': ...}; 'fields' gera KeyError e o datastore_create
   responde "Internal Server Error". Usamos datastore_search(limit=0).
3. datastore_search()['records'] no 2.9 e um LazyJSONObject (simplejson
   RawJSON), que o json da stdlib usado pela tabela activity nao serializa.
   Convertido para lista pura antes de gravar.
4. rval['method'] nao existe no retorno do datastore_create do 2.9.

Alem das correcoes, adiciona o que faltava para auditoria "linha a linha":
para datastore_upsert com method 'update' ou 'upsert', os valores ANTERIORES
das linhas afetadas sao lidos antes da gravacao e a atividade guarda, para
cada linha, a chave, o status (alterada / inserida / sem mudanca) e a lista
de campos com valor antigo -> valor novo (activity.data.changes).

Garantia de "nada se perde" (padrao):
  * o "antes" e capturado para QUALQUER quantidade de linhas (em blocos);
  * a atividade e montada e validada ANTES da gravacao e confirmada logo
    depois dela (mesma requisicao); se a gravacao falhar, a atividade e
    descartada; se a captura do "antes" falhar, a alteracao e RECUSADA
    (modo estrito) em vez de ser aplicada sem auditoria;
  * datastore_delete guarda TODAS as linhas removidas, inclusive quando a
    tabela inteira e excluida (sem filters).

Configuracao (ckan.ini ou variavel de ambiente via envvars):
  ckanext.dsaudit.preview_records   (padrao 12) linhas exibidas por atividade
  ckanext.dsaudit.max_diff_records  (padrao 0 = sem limite) limite opcional de
                                    linhas por chamada para capturar o "antes"
  ckanext.dsaudit.strict            (padrao true) recusa a alteracao quando a
                                    auditoria completa nao pode ser garantida
                                    (falha na captura ou limite excedido)
  ckanext.dsaudit.capture_drop      (padrao true) guarda o conteudo da tabela
                                    quando ela e excluida por inteiro
"""
import copy
import json
import logging

import sqlalchemy

from ckan.plugins.toolkit import (
    chained_action, get_action, config, check_access, side_effect_free,
    NotAuthorized, ObjectNotFound, ValidationError, asbool,
)
from ckan.logic.schema import default_create_activity_schema

log = logging.getLogger(__name__)

RW_URL_TYPES = ('datastore',)
DATASTORE_TYPES = ('created datastore', 'changed datastore', 'deleted datastore')
FILE_TYPE = 'changed resource file'
META_TYPE = 'changed metadata'
DSAUDIT_TYPES = DATASTORE_TYPES + (FILE_TYPE, META_TYPE)


# ---------------------------------------------------------------------------
# utilitarios
# ---------------------------------------------------------------------------

def fresh_context(context):
    return {
        k: context[k] for k in (
            'model', 'session', 'user', 'auth_user_obj',
            'ignore_auth', 'defer_commit',
        ) if k in context
    }


def _plain(value):
    """LazyJSONObject / RawJSON -> estruturas python puras."""
    encoded = getattr(value, 'encoded_json', None)
    if encoded is not None:
        return json.loads(encoded)
    return value


def _jsonable(value):
    """Garante que o valor pode ser gravado na coluna activity.data."""
    return json.loads(json.dumps(_plain(value), default=str))


def _max_diff_records():
    """0 (padrao) = sem limite."""
    try:
        return max(int(config.get('ckanext.dsaudit.max_diff_records', 0)), 0)
    except (TypeError, ValueError):
        return 0


def _within_limit(n):
    limit = _max_diff_records()
    return limit == 0 or n <= limit


def _strict():
    return asbool(config.get('ckanext.dsaudit.strict', True))


def _capture_drop():
    return asbool(config.get('ckanext.dsaudit.capture_drop', True))


def _page_size():
    """Maior pagina aceita pelo datastore_search (rows_max do DataStore)."""
    try:
        return max(int(config.get('ckan.datastore.search.rows_max', 32000)), 1)
    except (TypeError, ValueError):
        return 32000


def _refuse(msg):
    """Modo estrito: aborta ANTES de gravar, nada e alterado no DataStore."""
    log.error('dsaudit: %s', msg)
    raise ValidationError({'dsaudit': [
        msg + ' Nenhuma alteracao foi aplicada (ckanext.dsaudit.strict).']})


def _is_system_user(context):
    site_user = get_action('get_site_user')({'ignore_auth': True}, {})
    return site_user['name'] == context.get('user') or not context.get('user')


def _user_id(context):
    user = context['model'].User.get(context.get('user'))
    if user:
        return user.id
    return get_action('get_site_user')({'ignore_auth': True}, {})['id']


def _search_context(context):
    return dict(fresh_context(context), ignore_auth=True)


def _ds_fields(context, resource_id):
    """Campos da tabela (sem _id), no formato de datastore_info()['fields']."""
    srval = get_action('datastore_search')(_search_context(context), {
        'resource_id': resource_id,
        'limit': 0,
        'include_total': False,
    })
    return [f for f in srval['fields'] if f['id'] != '_id']


def _unique_keys(resource_id):
    """Mesmo SQL de ckanext.datastore.backend.postgres._get_unique_key."""
    from ckanext.datastore.backend import DatastoreBackend
    backend = DatastoreBackend.get_active_backend()
    engine = backend._get_write_engine()
    sql = sqlalchemy.text(u'''
        SELECT a.attname
        FROM pg_class t, pg_index idx, pg_attribute a
        WHERE t.oid = idx.indrelid
          AND a.attrelid = t.oid
          AND a.attnum = ANY(idx.indkey)
          AND t.relkind = 'r'
          AND idx.indisunique = true
          AND idx.indisprimary = false
          AND t.relname = :rid
    ''')
    with engine.connect() as conn:
        return [row[0] for row in conn.execute(sql, rid=resource_id)]


def _key_of(record, keys):
    return tuple(u'%s' % (record.get(k),) for k in keys)


def _fetch_old_rows(context, resource_id, records, keys):
    """Le as linhas atuais (antes da alteracao) correspondentes a records."""
    wanted = [r for r in records if all(k in r for k in keys)]
    if not wanted:
        return {}
    old = {}
    search = get_action('datastore_search')
    scontext = _search_context(context)
    if len(keys) == 1:
        k = keys[0]
        values = list({u'%s' % r[k] for r in wanted})
        for i in range(0, len(values), 200):
            chunk = values[i:i + 200]
            srval = search(scontext, {
                'resource_id': resource_id,
                'filters': {k: chunk},
                'limit': len(chunk),
                'include_total': False,
            })
            for row in _plain(srval['records']):
                old[_key_of(row, keys)] = row
    else:
        # chave composta: busca por blocos com "k IN (...)" em cada coluna da
        # chave (devolve um superconjunto) e filtra pela tupla exata
        for i in range(0, len(wanted), 100):
            chunk = wanted[i:i + 100]
            tuples = {_key_of(r, keys) for r in chunk}
            filters = {
                k: list({u'%s' % r[k] for r in chunk}) for k in keys
            }
            for row in _search_all(context, resource_id, filters):
                kt = _key_of(row, keys)
                if kt in tuples:
                    old[kt] = row
    return old


def _search_all(context, resource_id, filters=None, fields_out=None):
    """Todas as linhas que atendem a filters, paginando pelo rows_max."""
    search = get_action('datastore_search')
    scontext = _search_context(context)
    page = _page_size()
    offset = 0
    rows = []
    while True:
        params = {
            'resource_id': resource_id,
            'limit': page,
            'offset': offset,
            'sort': '_id',
            'include_total': False,
        }
        if filters:
            params['filters'] = filters
        srval = search(scontext, params)
        if fields_out is not None and not fields_out:
            fields_out.extend(srval['fields'])
        batch = _plain(srval['records'])
        rows.extend(batch)
        if len(batch) < int(srval.get('limit') or page):
            return rows
        offset += len(batch)


def _same(a, b):
    if a is None or b is None:
        return a is None and b is None
    if a == b:
        return True
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return u'%s' % (a,) == u'%s' % (b,)


def _build_changes(records, old_rows, keys):
    changes = []
    for r in records:
        key = dict((k, r.get(k)) for k in keys)
        before = old_rows.get(_key_of(r, keys))
        if before is None:
            changes.append({
                'key': key,
                'status': 'inserted',
                'row_id': None,
                'fields': [
                    {'field': f, 'old': None, 'new': v}
                    for f, v in r.items() if f not in keys
                ],
            })
            continue
        diffs = [
            {'field': f, 'old': before.get(f), 'new': v}
            for f, v in r.items()
            if f not in keys and f != '_id' and not _same(before.get(f), v)
        ]
        changes.append({
            'key': key,
            'status': 'updated' if diffs else 'unchanged',
            'row_id': before.get('_id'),
            'fields': diffs,
        })
    return changes


def _create_activity(context, res, activity_type, data, defer=False):
    """defer=True: a atividade fica pendente na sessao ate _commit()."""
    acontext = dict(
        fresh_context(context),
        ignore_auth=True,
        schema=dsaudit_create_activity_schema(),
    )
    if defer:
        acontext['defer_commit'] = True
    get_action('activity_create')(acontext, {
        'user_id': _user_id(context),
        'object_id': res.package_id,
        'activity_type': activity_type,
        'data': _jsonable(data),
    })


# ---------------------------------------------------------------------------
# actions encadeadas
# ---------------------------------------------------------------------------

@chained_action
def datastore_create(original_action, context, data_dict):
    records = data_dict.get('records', [])

    rval = original_action(context, data_dict)
    res = context['model'].Resource.get(rval['resource_id'])
    if res is None:
        return rval
    if res.url_type not in RW_URL_TYPES and _is_system_user(context):
        return rval

    create_data = {
        k: v for k, v in rval.items()
        if k not in ['records', 'method', 'resource']
    }
    create_data['existing'] = res.extras.get('datastore_active', False)
    create_data['url_type'] = res.url_type
    create_data['fields'] = _ds_fields(context, res.id)
    _create_activity(context, res, 'created datastore', create_data)

    if 'records' in rval:
        records = rval['records']
    if records:
        _create_activity(context, res, 'changed datastore', {
            'resource_id': rval['resource_id'],
            'method': rval.get('method', 'insert'),
            'fields': create_data['fields'],
            'records': records,
        })
    return rval


def _commit(context):
    context['model'].Session.commit()


def _rollback(context):
    try:
        context['model'].Session.rollback()
    except Exception:
        log.exception('dsaudit: rollback da sessao falhou')


def _write_with_audit(context, res, activity_type, activity_data,
                      original_action, data_dict):
    """Grava a atividade (pendente) -> executa a escrita -> confirma.

    Erros de validacao/serializacao da atividade acontecem ANTES de qualquer
    alteracao no DataStore. Se a escrita falhar, a atividade e descartada.
    """
    _create_activity(context, res, activity_type, activity_data, defer=True)
    try:
        rval = original_action(context, data_dict)
    except Exception:
        _rollback(context)
        raise
    try:
        _commit(context)
    except Exception:
        # a escrita ja foi confirmada no DataStore: registra o conteudo no log
        # para nao perder a informacao
        log.critical('dsaudit: falha ao gravar a atividade %s; dados: %s',
                     activity_type, json.dumps(_jsonable(activity_data)))
        raise
    return rval


@chained_action
def datastore_upsert(original_action, context, data_dict):
    records = data_dict.get('records', []) or []
    method = data_dict.get('method', 'upsert')
    resource_id = data_dict.get('resource_id', data_dict.get('id'))

    res = context['model'].Resource.get(resource_id) if resource_id else None
    if (res is None or res.url_type not in RW_URL_TYPES or not records
            or data_dict.get('dry_run')):
        return original_action(context, data_dict)

    # copia ANTES da gravacao (o backend altera os registros 'nested')
    records = copy.deepcopy(_plain(records))

    # captura o "antes" ANTES de gravar
    keys, old_rows = [], None
    if method in ('update', 'upsert'):
        if not _within_limit(len(records)):
            msg = ('upsert com %d linhas excede ckanext.dsaudit.'
                   'max_diff_records=%d; divida em lotes ou aumente o limite.'
                   % (len(records), _max_diff_records()))
            if _strict():
                _refuse(msg)
            log.warning('dsaudit: %s Gravando sem valores anteriores.', msg)
        else:
            try:
                keys = _unique_keys(res.id)
                if keys:
                    old_rows = _fetch_old_rows(context, res.id, records, keys)
            except Exception:
                log.exception('dsaudit: nao foi possivel ler valores anteriores')
                if _strict():
                    _refuse('Nao foi possivel ler os valores anteriores das '
                            'linhas para a auditoria.')
                old_rows = None

    all_fields = _ds_fields(context, res.id)
    activity_data = {
        'fields': [
            f for f in all_fields
            if any(f['id'] in r for r in records)
        ],
        'records': records,
        'method': method,
        'resource_id': res.id,
    }
    if old_rows is not None:
        activity_data['keys'] = keys
        activity_data['changes'] = _build_changes(records, old_rows, keys)
    return _write_with_audit(context, res, 'changed datastore', activity_data,
                             original_action, data_dict)


@chained_action
def datastore_delete(original_action, context, data_dict):
    res = context['model'].Resource.get(
        data_dict.get('resource_id', data_dict.get('id')))
    if not res or res.url_type not in RW_URL_TYPES:
        return original_action(context, data_dict)

    activity_data = {}
    has_filters = 'filters' in data_dict
    if has_filters or _capture_drop():
        try:
            fields = []
            rows = _search_all(context, res.id,
                               data_dict.get('filters') if has_filters
                               else None, fields_out=fields)
        except (ValidationError, ObjectNotFound):
            raise  # filtros invalidos / tabela inexistente: nada a excluir
        except Exception:
            log.exception('dsaudit: nao foi possivel ler as linhas a excluir')
            if _strict():
                _refuse('Nao foi possivel ler as linhas a excluir para a '
                        'auditoria.')
            fields, rows = [], None
        if rows is not None:
            if not _within_limit(len(rows)):
                msg = ('exclusao de %d linhas excede ckanext.dsaudit.'
                       'max_diff_records=%d.' % (len(rows),
                                                 _max_diff_records()))
                if _strict():
                    _refuse(msg)
                log.warning('dsaudit: %s Guardando so as primeiras.', msg)
                rows = rows[:_max_diff_records()]
            activity_data = {
                'fields': [f for f in fields if f['id'] != '_full_text'],
                'records': rows,
                'total': len(rows),
            }

    activity_data['filters'] = data_dict.get('filters') if has_filters \
        else None
    activity_data['resource_id'] = res.id
    return _write_with_audit(context, res, 'deleted datastore', activity_data,
                             original_action, data_dict)


# ---------------------------------------------------------------------------
# metadados do dataset campo a campo (autor, e-mail, titulo, tags, extras,
# metadados dos recursos...) -- inclusive datasets PRIVADOS, que no CKAN 2.9
# nao geram atividade nativa
# ---------------------------------------------------------------------------

META_IGNORE = {
    'metadata_modified', 'metadata_created', 'revision_id', 'num_resources',
    'num_tags', 'organization', 'tracking_summary', 'relationships_as_object',
    'relationships_as_subject', 'isopen', 'license_url', 'license_title',
    'resources', 'tags', 'groups', 'extras',
}
RES_IGNORE = {
    'metadata_modified', 'revision_id', 'datastore_active', 'position',
    'package_id', 'tracking_summary', 'id',
}


def _val(v):
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False, sort_keys=True, default=str)
    return v


def _flat_package(pkg):
    out = {}
    for k, v in (pkg or {}).items():
        if k not in META_IGNORE:
            out[k] = _val(v)
    out['tags'] = ', '.join(sorted(
        t.get('display_name') or t.get('name') or ''
        for t in (pkg or {}).get('tags') or [])) or None
    out['groups'] = ', '.join(sorted(
        g.get('name') or '' for g in (pkg or {}).get('groups') or [])) or None
    for e in (pkg or {}).get('extras') or []:
        out['extras.%s' % e.get('key')] = _val(e.get('value'))
    return out


def _flat_resources(pkg):
    res = []
    for r in (pkg or {}).get('resources') or []:
        res.append((r['id'], r.get('name') or r['id'], dict(
            (k, _val(v)) for k, v in r.items() if k not in RES_IGNORE)))
    return res


def _meta_same(a, b):
    if a in (None, '') or b in (None, ''):
        return a in (None, '') and b in (None, '')
    return a == b or u'%s' % (a,) == u'%s' % (b,)


def metadata_changes(before, after):
    changes = []
    fb, fa = _flat_package(before), _flat_package(after)
    for k in sorted(set(fb) | set(fa)):
        if not _meta_same(fb.get(k), fa.get(k)):
            changes.append({'scope': 'dataset', 'field': k,
                            'old': fb.get(k), 'new': fa.get(k)})
    rb = dict((rid, (name, f)) for rid, name, f in _flat_resources(before))
    ra = _flat_resources(after)
    for rid, name, fields in ra:
        if rid not in rb:
            for k in sorted(fields):
                if fields[k] not in (None, ''):
                    changes.append({'scope': 'resource', 'resource_id': rid,
                                    'resource_name': name, 'status': 'added',
                                    'field': k, 'old': None,
                                    'new': fields[k]})
            continue
        old = rb[rid][1]
        for k in sorted(set(old) | set(fields)):
            if not _meta_same(old.get(k), fields.get(k)):
                changes.append({'scope': 'resource', 'resource_id': rid,
                                'resource_name': name, 'status': 'changed',
                                'field': k, 'old': old.get(k),
                                'new': fields.get(k)})
    after_ids = set(rid for rid, _, _ in ra)
    for rid, (name, fields) in rb.items():
        if rid not in after_ids:
            for k in sorted(fields):
                if fields[k] not in (None, ''):
                    changes.append({'scope': 'resource', 'resource_id': rid,
                                    'resource_name': name,
                                    'status': 'removed', 'field': k,
                                    'old': fields[k], 'new': None})
    return changes


def _package_snapshot(context, id_or_name):
    return get_action('package_show')(
        dict(fresh_context(context), ignore_auth=True, use_cache=False,
             for_view=False),
        {'id': id_or_name, 'include_tracking': False})


def _pkg_header(pkg):
    return {'title': pkg.get('title') or pkg.get('name'),
            'name': pkg.get('name'), 'type': pkg.get('type') or 'dataset'}


def create_package_activity(context, package_id, activity_type, data,
                            defer=False):
    acontext = dict(
        fresh_context(context),
        ignore_auth=True,
        schema=dsaudit_create_activity_schema(),
    )
    if defer:
        acontext['defer_commit'] = True
    get_action('activity_create')(acontext, {
        'user_id': _user_id(context),
        'object_id': package_id,
        'activity_type': activity_type,
        'data': _jsonable(data),
    })


def _meta_activity(before, after, method):
    changes = metadata_changes(before, after)
    if not changes:
        return None
    rids = set(c['resource_id'] for c in changes if c.get('resource_id'))
    data = {'method': method, 'changes': changes,
            'package': _pkg_header(after or before)}
    if len(rids) == 1 and all(c.get('resource_id') for c in changes):
        data['resource_id'] = rids.pop()
    return data


def _run_deferred(context, original_action, data_dict):
    """Executa a action sem commit; quem chamou decide quando confirmar."""
    outer = context.get('defer_commit')
    context['defer_commit'] = True
    try:
        return original_action(context, data_dict), outer
    except Exception:
        if not outer:
            _rollback(context)
        raise
    finally:
        if not outer:
            context.pop('defer_commit', None)


@chained_action
def package_update(original_action, context, data_dict):
    ident = data_dict.get('id') or data_dict.get('name')
    try:
        before = _package_snapshot(context, ident)
    except ObjectNotFound:
        return original_action(context, data_dict)
    except Exception:
        log.exception('dsaudit: nao foi possivel ler o dataset antes')
        if _strict():
            _refuse('Nao foi possivel ler os metadados atuais do dataset '
                    'para a auditoria.')
        return original_action(context, data_dict)

    rval, outer = _run_deferred(context, original_action, data_dict)
    try:
        after = _package_snapshot(context, before['id'])
        data = _meta_activity(before, after, 'updated')
        if data:
            create_package_activity(context, before['id'], META_TYPE, data,
                                    defer=True)
    except Exception:
        log.exception('dsaudit: auditoria de metadados falhou')
        if _strict():
            if not outer:
                _rollback(context)
            _refuse('Nao foi possivel registrar a auditoria dos metadados.')
    if not outer:
        _commit(context)
    return rval


@chained_action
def package_create(original_action, context, data_dict):
    rval, outer = _run_deferred(context, original_action, data_dict)
    pkg_id = rval if isinstance(rval, str) else rval['id']
    try:
        after = _package_snapshot(context, pkg_id)
        data = _meta_activity({}, after, 'created')
        if data:
            create_package_activity(context, pkg_id, META_TYPE, data,
                                    defer=True)
    except Exception:
        log.exception('dsaudit: auditoria de metadados falhou')
        if _strict():
            if not outer:
                _rollback(context)
            _refuse('Nao foi possivel registrar a auditoria dos metadados.')
    if not outer:
        _commit(context)
    return rval


@chained_action
def package_delete(original_action, context, data_dict):
    # o package_delete do 2.9 sempre faz commit: a atividade e gravada logo
    # depois (o "antes" ja foi lido)
    try:
        before = _package_snapshot(context, data_dict.get('id'))
    except ObjectNotFound:
        return original_action(context, data_dict)
    rval = original_action(context, data_dict)
    try:
        after = _package_snapshot(context, before['id'])
    except ObjectNotFound:
        after = dict(before, state='deleted')
    data = _meta_activity(before, after, 'deleted')
    if data:
        try:
            create_package_activity(context, before['id'], META_TYPE, data)
        except Exception:
            log.critical('dsaudit: falha ao gravar a atividade %s; dados: %s',
                         META_TYPE, json.dumps(_jsonable(data)))
            raise
    return rval


# ---------------------------------------------------------------------------
# leitura das atividades (CKAN 2.9)
# ---------------------------------------------------------------------------
# No CKAN 2.9 package_activity_list SEMPRE descarta activity.data
# (data_dict['include_data'] = False em ckan/logic/action/get.py), entao a aba
# "Activity Stream" nunca receberia os registros/diff gravados acima. As duas
# funcoes abaixo devolvem o conteudo completo para quem pode editar o dataset.

def _can_update(context, package_id):
    try:
        check_access('package_update', dict(fresh_context(context)),
                     {'id': package_id})
        return True
    except NotAuthorized:
        return False


@chained_action
@side_effect_free
def package_activity_list(original_action, context, data_dict):
    result = original_action(context, data_dict)
    dsaudit_items = [a for a in result if a.get('activity_type') in DSAUDIT_TYPES]
    if not dsaudit_items:
        return result
    model = context['model']
    pkg = model.Package.get(data_dict.get('id'))
    if pkg is None or not _can_update(context, pkg.id):
        return result
    for item in dsaudit_items:
        act = model.Session.query(model.Activity).get(item['id'])
        if act is not None and act.data:
            item['data'] = act.data
    return result


@side_effect_free
def dsaudit_activity_list(context, data_dict):
    """Historico completo de alteracoes do DataStore de um dataset.

    :param id: id ou nome do dataset
    :param resource_id: (opcional) restringe a um recurso
    :param activity_type: (opcional) 'created datastore' | 'changed datastore'
        | 'deleted datastore'
    :param limit: (opcional, padrao 50, maximo 500)
    :param offset: (opcional, padrao 0)
    :returns: {'count': N, 'results': [atividades com data completo]}
    """
    model = context['model']
    pkg = model.Package.get(data_dict.get('id'))
    if pkg is None:
        raise ObjectNotFound('Dataset nao encontrado')
    check_access('package_update', context, {'id': pkg.id})

    types = DSAUDIT_TYPES
    if data_dict.get('activity_type') in DSAUDIT_TYPES:
        types = (data_dict['activity_type'],)
    try:
        limit = min(int(data_dict.get('limit', 50)), 500)
        offset = max(int(data_dict.get('offset', 0)), 0)
    except (TypeError, ValueError):
        limit, offset = 50, 0
    resource_id = data_dict.get('resource_id')

    q = model.Session.query(model.Activity).filter(
        model.Activity.object_id == pkg.id,
        model.Activity.activity_type.in_(types),
    ).order_by(model.Activity.timestamp.desc())

    rows = []
    for act in q:
        data = act.data or {}
        if resource_id and data.get('resource_id') != resource_id and \
                not any(c.get('resource_id') == resource_id
                        for c in data.get('changes') or []
                        if act.activity_type == META_TYPE):
            continue
        rows.append(act)
    page = rows[offset:offset + limit]
    return {
        'count': len(rows),
        'results': [{
            'id': a.id,
            'timestamp': a.timestamp.isoformat(),
            'user_id': a.user_id,
            'object_id': a.object_id,
            'activity_type': a.activity_type,
            'data': a.data,
        } for a in page],
    }


@chained_action
@side_effect_free
def activity_diff(original_action, context, data_dict):
    """Mantem o diff nativo de metadados ("Changes") funcionando.

    O core do 2.9 compara a atividade com a imediatamente anterior do mesmo
    object_id. Como as atividades do dsaudit usam o id do dataset como
    object_id, a "anterior" podia ser uma atividade de DataStore (sem
    data['package']) e a pagina /dataset/changes/<id> respondia 404.
    Aqui a busca da anterior ignora os tipos do dsaudit.
    """
    import difflib
    import re
    from ckan.lib.dictization import model_dictize

    if data_dict.get('object_type', 'package') != 'package':
        return original_action(context, data_dict)

    model = context['model']
    check_access('activity_diff', context, data_dict)
    activity = model.Session.query(model.Activity).get(data_dict.get('id'))
    if activity is None or activity.activity_type in DSAUDIT_TYPES:
        raise ObjectNotFound('Activity not found')
    prev_activity = model.Session.query(model.Activity) \
        .filter_by(object_id=activity.object_id) \
        .filter(model.Activity.timestamp < activity.timestamp) \
        .filter(~model.Activity.activity_type.in_(DSAUDIT_TYPES)) \
        .order_by(model.Activity.timestamp.desc()) \
        .first()
    if prev_activity is None:
        raise ObjectNotFound('Previous activity for this object not found')
    activity_objs = [prev_activity, activity]
    try:
        objs = [a.data['package'] for a in activity_objs]
    except (KeyError, TypeError):
        raise ObjectNotFound('Could not find object in the activity data')
    obj_lines = [json.dumps(obj, indent=2, sort_keys=True).split('\n')
                 for obj in objs]

    diff_type = data_dict.get('diff_type', 'unified')
    if diff_type == 'unified':
        diff = '\n'.join(difflib.unified_diff(*obj_lines))
    elif diff_type == 'context':
        diff = '\n'.join(difflib.context_diff(*obj_lines))
    elif diff_type == 'html':
        for i in (0, 1):
            wrapped = []
            for line in obj_lines[i]:
                wrapped.extend(re.findall(r'.{1,70}(?:\s+|$)', line))
            obj_lines[i] = wrapped
        diff = difflib.HtmlDiff().make_table(*obj_lines)
    else:
        from ckan.plugins.toolkit import ValidationError
        raise ValidationError('diff_type not recognized')

    return {
        'diff': diff,
        'activities': [
            model_dictize.activity_dictize(a, context, include_data=True)
            for a in activity_objs
        ],
    }


def dsaudit_create_activity_schema():
    '''
    remove as validacoes de object_id e activity_type, pois criamos
    tipos de atividade novos
    '''
    sch = default_create_activity_schema()
    del sch['object_id'][-1]
    del sch['activity_type'][-1]
    return sch
DSAUDIT_FILE_05

# --- helpers.py ---
COPY <<"DSAUDIT_FILE_06" /tmp/dsaudit-ckan29/helpers.py
# -*- coding: utf-8 -*-
from ckan import model
from ckan.plugins.toolkit import h, config


def dsaudit_resource_url(package_id, resource_id):
    pkg = model.Package.get(package_id)
    if not pkg:
        return '#'
    return h.url_for(
        (pkg.type or 'dataset') + '_resource.read',
        id=pkg.name,
        resource_id=resource_id,
    )


def dsaudit_resource_name(resource_id):
    res = model.Resource.get(resource_id) if resource_id else None
    if res is None:
        return resource_id or ''
    return res.name or res.id


def dsaudit_data_columns(data):
    if data.get('fields'):
        return [f['id'] for f in data['fields']]
    if data.get('records'):
        return list(data['records'][0].keys())
    return []


def dsaudit_preview_records():
    return int(config.get('ckanext.dsaudit.preview_records', 12))
DSAUDIT_FILE_06

# --- plugins.py ---
COPY <<"DSAUDIT_FILE_07" /tmp/dsaudit-ckan29/plugins.py
# -*- coding: utf-8 -*-
"""
ckanext-dsaudit -- plugin adaptado para CKAN 2.9.5 (substitui o upstream).

Diferencas para o upstream (ckan/ckanext-dsaudit@c398842):
  * encadeia tambem package_activity_list, que no 2.9 descarta activity.data;
  * encadeia activity_diff para o diff de metadados ignorar as atividades
    de DataStore (senao /dataset/changes/<id> dava 404);
  * nova action dsaudit_activity_list (API) e pagina /dataset/<id>/auditoria;
  * helper dsaudit_resource_name para exibir o nome do recurso.
"""
import logging

import ckan.plugins as p

from ckanext.dsaudit import views, helpers, actions, versions
from ckan.lib.plugins import DefaultTranslation

log = logging.getLogger(__name__)


class DSAuditPlugin(p.SingletonPlugin, DefaultTranslation):
    p.implements(p.IConfigurer)
    p.implements(p.IBlueprint)
    p.implements(p.IActions)
    p.implements(p.ITemplateHelpers, inherit=True)
    p.implements(p.ITranslation)
    p.implements(p.IResourceController, inherit=True)

    # --- arquivos enviados (upload) pela interface ou API ------------------

    def before_update(self, context, current, resource):
        # o CKAN sobrescreve o arquivo no mesmo caminho: guarda o atual antes
        try:
            versions.ensure_baseline(current)
        except Exception:
            log.exception('dsaudit: nao foi possivel guardar a versao atual')
            if versions.strict():
                raise p.toolkit.ValidationError({'dsaudit': [
                    'Nao foi possivel guardar a versao atual do arquivo '
                    'antes da substituicao. Nenhuma alteracao foi aplicada '
                    '(ckanext.dsaudit.strict).']})

    def after_create(self, context, resource):
        self._file_activity(context, resource)

    def after_update(self, context, resource):
        self._file_activity(context, resource)

    def _file_activity(self, context, resource):
        data = None
        try:
            data = versions.record_change(resource)
            if data is None:
                return
            pkg = context['model'].Package.get(resource['package_id'])
            if pkg is not None:
                data['package'] = {'title': pkg.title or pkg.name,
                                   'name': pkg.name,
                                   'type': pkg.type or 'dataset'}
            actions.create_package_activity(
                context, resource['package_id'], actions.FILE_TYPE, data)
        except Exception:
            # as versoes do arquivo ja estao guardadas em disco
            log.critical('dsaudit: falha ao registrar a troca do arquivo do '
                         'recurso %s; dados: %s', resource.get('id'),
                         actions.json.dumps(actions._jsonable(data or {})),
                         exc_info=True)

    def update_config(self, config):
        if not p.toolkit.check_ckan_version('2.10'):
            p.toolkit.add_template_directory(config, '2.9_templates')
        p.toolkit.add_template_directory(config, 'templates')

    def get_blueprint(self):
        return views.dsaudit

    def get_actions(self):
        return {
            'datastore_create': actions.datastore_create,
            'datastore_upsert': actions.datastore_upsert,
            'datastore_delete': actions.datastore_delete,
            'package_update': actions.package_update,
            'package_create': actions.package_create,
            'package_delete': actions.package_delete,
            'package_activity_list': actions.package_activity_list,
            'dsaudit_activity_list': actions.dsaudit_activity_list,
            'activity_diff': actions.activity_diff,
        }

    def get_helpers(self):
        return {
            'dsaudit_resource_url': helpers.dsaudit_resource_url,
            'dsaudit_resource_name': helpers.dsaudit_resource_name,
            'dsaudit_data_columns': helpers.dsaudit_data_columns,
            'dsaudit_preview_records': helpers.dsaudit_preview_records,
        }
DSAUDIT_FILE_07

# --- views.py ---
COPY <<"DSAUDIT_FILE_08" /tmp/dsaudit-ckan29/views.py
# -*- coding: utf-8 -*-
"""
ckanext-dsaudit -- pagina de auditoria do DataStore (CKAN 2.9)

  GET /dataset/<id>/auditoria                     todas as alteracoes
  GET /dataset/<id>/auditoria?resource_id=<rid>   apenas um recurso
  GET /dataset/<id>/auditoria.csv[?resource_id=]  exportacao CSV (1 linha por
                                                  campo alterado)

Acesso restrito a quem pode editar o dataset (package_update).
"""
import csv
import io
import json

from flask import Blueprint, Response, request

from ckan import model
from ckan.common import g
from ckan.plugins import toolkit as tk

dsaudit = Blueprint('dsaudit', __name__)

PER_PAGE = 20


def _context():
    return {
        'model': model,
        'session': model.Session,
        'user': g.user,
        'auth_user_obj': g.userobj,
        'for_view': True,
    }


def _load(id):
    context = _context()
    try:
        pkg_dict = tk.get_action('package_show')(context, {'id': id})
        tk.check_access('package_update', _context(), {'id': pkg_dict['id']})
    except tk.ObjectNotFound:
        return tk.abort(404, tk._('Dataset not found'))
    except tk.NotAuthorized:
        return tk.abort(403, u'Sem permissao para ver a auditoria deste dataset')
    return context, pkg_dict


def audit(id):
    context, pkg_dict = _load(id)
    resource_id = request.args.get('resource_id') or None
    activity_type = request.args.get('activity_type') or None
    try:
        page = max(int(request.args.get('page', 1)), 1)
    except ValueError:
        page = 1

    result = tk.get_action('dsaudit_activity_list')(_context(), {
        'id': pkg_dict['id'],
        'resource_id': resource_id,
        'activity_type': activity_type,
        'limit': PER_PAGE,
        'offset': (page - 1) * PER_PAGE,
    })

    g.pkg_dict = pkg_dict
    g.pkg = context.get('package') or model.Package.get(pkg_dict['id'])
    return tk.render('dsaudit/audit.html', {
        'dataset_type': pkg_dict.get('type') or 'dataset',
        'pkg_dict': pkg_dict,
        'pkg': g.pkg,
        'id': pkg_dict['name'],
        'activity_stream': result['results'],
        'count': result['count'],
        'page': page,
        'per_page': PER_PAGE,
        'resource_id': resource_id,
        'activity_type': activity_type,
    })


def audit_csv(id):
    context, pkg_dict = _load(id)
    resource_id = request.args.get('resource_id') or None
    # todas as atividades (a action devolve no maximo 500 por chamada)
    events, offset = [], 0
    while True:
        page = tk.get_action('dsaudit_activity_list')(_context(), {
            'id': pkg_dict['id'],
            'resource_id': resource_id,
            'limit': 500,
            'offset': offset,
        })
        events.extend(page['results'])
        offset += len(page['results'])
        if not page['results'] or offset >= page['count']:
            break
    result = {'results': events}
    users = {}

    def uname(uid):
        if uid not in users:
            u = model.User.get(uid)
            users[uid] = u.name if u else uid
        return users[uid]

    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(['timestamp_utc', 'usuario', 'tipo', 'metodo', 'resource_id',
                'chave_linha', '_id', 'status_linha', 'campo',
                'valor_anterior', 'valor_novo'])
    for a in result['results']:
        d = a['data'] or {}
        base = [a['timestamp'], uname(a['user_id']), a['activity_type'],
                d.get('method', ''), d.get('resource_id', '')]
        if a['activity_type'] == 'changed metadata':
            for c in d.get('changes') or []:
                scope = 'dataset' if c.get('scope') == 'dataset' else \
                    'recurso: %s' % c.get('resource_name')
                row = list(base)
                row[4] = c.get('resource_id') or d.get('resource_id', '')
                w.writerow(row + [scope, '', c.get('status', 'changed'),
                                  c.get('field'), c.get('old'), c.get('new')])
            continue
        if a['activity_type'] == 'changed resource file':
            v = d.get('version') or {}
            pv = d.get('previous_version') or {}
            w.writerow(base + ['', '', 'arquivo', 'arquivo',
                               '%s (v%s)' % (pv.get('filename'), pv.get('version')) if pv else '',
                               '%s (v%s)' % (v.get('filename'), v.get('version'))])
            if d.get('diff_error'):
                w.writerow(base + ['', '', 'aviso', '', '', d['diff_error']])
        if d.get('changes'):
            for c in d['changes']:
                key = json.dumps(c.get('key'), ensure_ascii=False)
                if not c.get('fields'):
                    w.writerow(base + [key, c.get('row_id'), c.get('status'),
                                       '', '', ''])
                for f in c.get('fields') or []:
                    w.writerow(base + [key, c.get('row_id'), c.get('status'),
                                       f.get('field'), f.get('old'),
                                       f.get('new')])
        elif d.get('records'):
            status = 'deleted' if a['activity_type'] == 'deleted datastore' \
                else 'sent'
            for r in d['records']:
                for field, value in r.items():
                    old, new = (value, '') if status == 'deleted' else ('', value)
                    w.writerow(base + ['', r.get('_id', ''), status, field,
                                       old, new])
        elif a['activity_type'] != 'changed resource file':
            w.writerow(base + ['', '', '', '', '', ''])
    filename = 'auditoria-%s.csv' % pkg_dict['name']
    return Response(
        out.getvalue(), mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=%s' % filename})


def version_file(id, resource_id, version):
    """Baixa uma versao guardada do arquivo de um recurso (so editores)."""
    from ckanext.dsaudit import versions
    context, pkg_dict = _load(id)
    res = model.Resource.get(resource_id)
    if res is None or res.package_id != pkg_dict['id']:
        return tk.abort(404, tk._('Resource not found'))
    entry = versions.get_version(res.id, version)
    if entry is None:
        return tk.abort(404, u'Versao nao encontrada')
    from flask import send_file
    return send_file(versions.version_path(res.id, entry),
                     as_attachment=True,
                     attachment_filename='v%d_%s' % (version,
                                                     entry['filename']))


dsaudit.add_url_rule('/dataset/<id>/auditoria', view_func=audit)
dsaudit.add_url_rule(
    '/dataset/<id>/auditoria/versao/<resource_id>/<int:version>',
    view_func=version_file, endpoint='version')
dsaudit.add_url_rule('/dataset/<id>/auditoria.csv', view_func=audit_csv)
DSAUDIT_FILE_08

# --- versions.py ---
COPY <<"DSAUDIT_FILE_09" /tmp/dsaudit-ckan29/versions.py
# -*- coding: utf-8 -*-
"""
ckanext-dsaudit -- versoes de arquivos enviados (upload) e diff linha a linha

Quando um recurso com arquivo enviado (url_type = 'upload') e criado ou tem o
arquivo substituido -- pela interface ou pela API --, cada versao do arquivo e
guardada em <ckan.storage_path>/dsaudit_versions/<resource_id>/ e uma
atividade 'changed resource file' registra:

  * a versao nova e a anterior (nome, tamanho, sha256, link para baixar);
  * para CSV/TSV/TXT/XLSX: o diff linha a linha (linha nova, removida,
    alterada com valor anterior -> novo de cada campo).

As linhas sao comparadas pela coluna-chave quando houver uma (campo do
recurso 'chave_auditoria' ou ckanext.dsaudit.file_key_columns, padrao 'id');
sem chave, pela posicao/sequencia das linhas.

O CKAN sobrescreve o arquivo no mesmo caminho ao substitui-lo; por isso a
versao atual e guardada em before_update, ANTES da troca. Em modo estrito,
se nao for possivel guardar a versao atual, a substituicao e recusada.
"""
import csv
import datetime
import difflib
import hashlib
import io
import json
import logging
import os
import re
import shutil

from ckan.plugins.toolkit import config, asbool

log = logging.getLogger(__name__)

TABULAR_EXT = ('csv', 'tsv', 'txt', 'xlsx', 'xlsm')


# ---------------------------------------------------------------------------
# armazenamento das versoes
# ---------------------------------------------------------------------------

def _root():
    custom = config.get('ckanext.dsaudit.versions_path')
    if custom:
        return custom
    base = config.get('ckan.storage_path') or '/var/lib/ckan'
    return os.path.join(base, 'dsaudit_versions')


def _rdir(resource_id):
    if not re.match(r'^[A-Za-z0-9_-]+$', resource_id or ''):
        raise ValueError('resource_id invalido')
    return os.path.join(_root(), resource_id)


def _index_path(resource_id):
    return os.path.join(_rdir(resource_id), 'index.json')


def load_index(resource_id):
    try:
        with io.open(_index_path(resource_id), encoding='utf-8') as f:
            return json.load(f)
    except (IOError, OSError, ValueError):
        return []


def _save_index(resource_id, index):
    path = _index_path(resource_id)
    tmp = path + '.tmp'
    with io.open(tmp, 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def latest(resource_id):
    index = load_index(resource_id)
    return index[-1] if index else None


def get_version(resource_id, number):
    for entry in load_index(resource_id):
        if entry.get('version') == number:
            return entry
    return None


def version_path(resource_id, entry):
    return os.path.join(_rdir(resource_id), entry['file'])


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def _safe_name(name):
    name = os.path.basename(name or '') or 'arquivo'
    return re.sub(r'[^A-Za-z0-9._-]+', '_', name)[-120:]


def snapshot(resource_id, src_path, filename, label, sha=None):
    """Copia src_path como nova versao (se diferente da ultima)."""
    sha = sha or sha256(src_path)
    index = load_index(resource_id)
    if index and index[-1].get('sha256') == sha:
        return index[-1], False
    os.makedirs(_rdir(resource_id), exist_ok=True)
    number = (index[-1]['version'] + 1) if index else 1
    fname = 'v%04d_%s' % (number, _safe_name(filename))
    shutil.copy2(src_path, os.path.join(_rdir(resource_id), fname))
    entry = {
        'version': number,
        'file': fname,
        'filename': os.path.basename(filename or '') or fname,
        'sha256': sha,
        'size': os.path.getsize(src_path),
        'saved_at': datetime.datetime.utcnow().isoformat(),
        'label': label,
    }
    index.append(entry)
    _save_index(resource_id, index)
    return entry, True


def resource_file_path(resource_id):
    from ckan.lib.uploader import ResourceUpload
    upload = ResourceUpload({})
    if not upload.storage_path:
        return None
    return upload.get_path(resource_id)


def filename_of(resource):
    url = resource.get('url') or ''
    return url.rsplit('/', 1)[-1] or resource.get('name') or resource['id']


# ---------------------------------------------------------------------------
# leitura de tabelas (CSV/TSV/TXT/XLSX)
# ---------------------------------------------------------------------------

def _ext(filename, fmt):
    ext = os.path.splitext(filename or '')[1].lower().lstrip('.')
    if ext in TABULAR_EXT:
        return ext
    fmt = (fmt or '').lower().strip('.')
    return fmt if fmt in TABULAR_EXT else ext


def _decode(raw):
    for enc in ('utf-8-sig', 'cp1252', 'latin-1'):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode('utf-8', 'replace')


def _cell(value):
    if value is None:
        return None
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()
    if isinstance(value, float) and value.is_integer():
        return u'%d' % value
    return u'%s' % (value,)


def read_table(path, filename=None, fmt=None):
    """(cabecalho, [linhas como dict]) ou None se o formato nao e tabular."""
    ext = _ext(filename, fmt)
    if ext in ('xlsx', 'xlsm'):
        import openpyxl
        # o CKAN guarda o upload sem extensao: abrir como objeto de arquivo
        with open(path, 'rb') as fh:
            wb = openpyxl.load_workbook(fh, read_only=True, data_only=True)
            try:
                ws = wb.worksheets[0]
                rows = [[_cell(v) for v in row]
                        for row in ws.iter_rows(values_only=True)]
            finally:
                wb.close()
    elif ext in ('csv', 'tsv', 'txt'):
        with open(path, 'rb') as f:
            text = _decode(f.read())
        if ext == 'tsv':
            delim = '\t'
        else:
            try:
                delim = csv.Sniffer().sniff(text[:65536], ',;\t|').delimiter
            except csv.Error:
                delim = ';' if text[:4096].count(';') > \
                    text[:4096].count(',') else ','
        rows = [[c if c != '' else None for c in r]
                for r in csv.reader(io.StringIO(text), delimiter=delim)]
    else:
        return None

    while rows and not any(v not in (None, '') for v in rows[-1]):
        rows.pop()
    if not rows:
        return [], []
    header, seen = [], {}
    for i, h in enumerate(rows[0]):
        name = (u'%s' % h).strip() if h not in (None, '') else 'coluna_%d' % (i + 1)
        if name in seen:
            seen[name] += 1
            name = '%s_%d' % (name, seen[name])
        else:
            seen[name] = 1
        header.append(name)
    data = []
    for r in rows[1:]:
        r = list(r) + [None] * (len(header) - len(r))
        extra = r[len(header):]
        row = dict(zip(header, r[:len(header)]))
        for j, v in enumerate(extra):
            if v not in (None, ''):
                row['coluna_%d' % (len(header) + j + 1)] = v
        data.append(row)
    return header, data


# ---------------------------------------------------------------------------
# diff entre duas versoes
# ---------------------------------------------------------------------------

def _same(a, b):
    if a in (None, '') or b in (None, ''):
        return a in (None, '') and b in (None, '')
    if a == b:
        return True
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return False


def _field_diffs(before, after, columns):
    return [
        {'field': c, 'old': before.get(c), 'new': after.get(c)}
        for c in columns if not _same(before.get(c), after.get(c))
    ]


def _key_candidates(resource):
    explicit = (resource or {}).get('chave_auditoria') or \
        (resource or {}).get('dsaudit_key')
    if explicit:
        return [[k.strip() for k in explicit.split(',') if k.strip()]]
    names = config.get('ckanext.dsaudit.file_key_columns', 'id')
    return [[n] for n in names.split()]


def _unique_key(rows, keys):
    seen = set()
    for r in rows:
        k = tuple(u'%s' % r.get(c) for c in keys)
        if any(r.get(c) in (None, '') for c in keys) or k in seen:
            return False
        seen.add(k)
    return True


def _choose_keys(resource, old, new):
    (oh, orows), (nh, nrows) = old, new
    for keys in _key_candidates(resource):
        if keys and all(k in oh and k in nh for k in keys) and \
                _unique_key(orows, keys) and _unique_key(nrows, keys):
            return keys
    return []


def diff_tables(old, new, resource=None):
    (oh, orows), (nh, nrows) = old, new
    columns = list(nh) + [c for c in oh if c not in nh]
    keys = _choose_keys(resource, old, new)
    changes, unchanged = [], 0

    if keys:
        def kt(r):
            return tuple(u'%s' % r.get(c) for c in keys)
        old_by = dict((kt(r), r) for r in orows)
        new_keys = set()
        for r in nrows:
            k = kt(r)
            new_keys.add(k)
            key = dict((c, r.get(c)) for c in keys)
            before = old_by.get(k)
            if before is None:
                changes.append({'key': key, 'status': 'inserted',
                                'fields': _field_diffs({}, r, [
                                    c for c in columns if c not in keys])})
                continue
            diffs = _field_diffs(before, r, [c for c in columns if c not in keys])
            if diffs:
                changes.append({'key': key, 'status': 'updated',
                                'fields': diffs})
            else:
                unchanged += 1
        for r in orows:
            if kt(r) not in new_keys:
                changes.append({
                    'key': dict((c, r.get(c)) for c in keys),
                    'status': 'deleted',
                    'fields': _field_diffs(r, {}, [
                        c for c in columns if c not in keys]),
                })
    else:
        def tup(r):
            return tuple(u'%s' % (r.get(c) if r.get(c) is not None else '')
                         for c in columns)
        sm = difflib.SequenceMatcher(
            None, [tup(r) for r in orows], [tup(r) for r in nrows],
            autojunk=False)
        for op, i1, i2, j1, j2 in sm.get_opcodes():
            if op == 'equal':
                unchanged += i2 - i1
                continue
            pairs = min(i2 - i1, j2 - j1) if op == 'replace' else 0
            for n in range(pairs):
                changes.append({
                    'key': {'linha': j1 + n + 2, 'linha_anterior': i1 + n + 2},
                    'status': 'updated',
                    'fields': _field_diffs(orows[i1 + n], nrows[j1 + n],
                                           columns),
                })
            for i in range(i1 + pairs, i2):
                changes.append({'key': {'linha_anterior': i + 2},
                                'status': 'deleted',
                                'fields': _field_diffs(orows[i], {}, columns)})
            for j in range(j1 + pairs, j2):
                changes.append({'key': {'linha': j + 2},
                                'status': 'inserted',
                                'fields': _field_diffs({}, nrows[j], columns)})

    return {
        'mode': 'chave' if keys else 'posicao',
        'keys': keys,
        'changes': changes,
        'unchanged': unchanged,
        'rows_old': len(orows),
        'rows_new': len(nrows),
        'columns_added': [c for c in nh if c not in oh],
        'columns_removed': [c for c in oh if c not in nh],
    }


# ---------------------------------------------------------------------------
# ganchos chamados pelo plugin (IResourceController)
# ---------------------------------------------------------------------------

def strict():
    return asbool(config.get('ckanext.dsaudit.strict', True))


def ensure_baseline(current):
    """before_update: guarda o arquivo ATUAL antes que seja sobrescrito."""
    if not current or current.get('url_type') != 'upload':
        return
    path = resource_file_path(current['id'])
    if not path or not os.path.exists(path):
        return
    snapshot(current['id'], path, filename_of(current), 'versao anterior')


def record_change(resource):
    """after_create / after_update: se o arquivo mudou, guarda e compara.

    Devolve os dados da atividade, ou None se o arquivo nao mudou.
    """
    if not resource or resource.get('url_type') != 'upload':
        return None
    rid = resource['id']
    path = resource_file_path(rid)
    if not path or not os.path.exists(path):
        return None
    sha = sha256(path)
    prev = latest(rid)
    if prev and prev.get('sha256') == sha:
        return None
    entry, _ = snapshot(rid, path, filename_of(resource), 'enviado', sha=sha)

    data = {
        'resource_id': rid,
        'method': 'replaced' if prev else 'new',
        'version': entry,
        'previous_version': prev,
    }
    fmt = resource.get('format')
    try:
        new_tab = read_table(path, entry['filename'], fmt)
        if new_tab is None:
            data['diff_error'] = (u'formato nao tabular: o diff linha a linha '
                                  u'nao se aplica; as versoes foram guardadas')
        elif prev is None:
            data['columns'] = new_tab[0]
            data['rows_new'] = len(new_tab[1])
        else:
            old_tab = read_table(version_path(rid, prev),
                                 prev.get('filename'), fmt)
            if old_tab is None:
                data['diff_error'] = (u'versao anterior em formato nao '
                                      u'tabular; as versoes foram guardadas')
            else:
                data.update(diff_tables(old_tab, new_tab, resource))
    except Exception as e:  # o arquivo ja foi guardado: registra o motivo
        log.exception('dsaudit: diff do arquivo %s falhou', rid)
        data['diff_error'] = u'nao foi possivel comparar: %s' % (e,)
    return data
DSAUDIT_FILE_09

# --- aplica a camada ---------------------------------------------------------
RUN set -eu; \
    SRC=/tmp/dsaudit-ckan29; \
    DST=/srv/app/src/ckanext-dsaudit/ckanext/dsaudit; \
    test -f "$DST/plugins.py"; \
    find "$SRC" -type f -exec sed -i 's/\r$//' {} +; \
    cp "$SRC/plugins.py" "$SRC/actions.py" "$SRC/helpers.py" "$SRC/views.py" "$SRC/versions.py" "$DST/"; \
    mkdir -p "$DST/2.9_templates"; \
    cp -R "$SRC/2.9_templates/." "$DST/2.9_templates/"; \
    if grep -rnE "in h\.datastore_rw_resource_url_types|snippet 'datastore/snippets/dictionary_view" "$DST"/*.py "$DST/2.9_templates"; then echo "camada incompleta" >&2; exit 1; fi; \
    python3 -m py_compile "$DST/plugins.py" "$DST/actions.py" "$DST/helpers.py" "$DST/views.py" "$DST/versions.py"; \
    rm -rf "$SRC"; \
    echo "ckanext-dsaudit: camada CKAN 2.9 aplicada"

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

# ===========================================================================
# prerun corrigido (substitui /srv/app/prerun.py da imagem base)
# ===========================================================================

COPY <<"PRERUN_FILE" /srv/app/prerun.py
# -*- coding: utf-8 -*-
"""
prerun.py -- substitui /srv/app/prerun.py da imagem ckan/ckan-base:2.9.5

O start_ckan.sh da imagem executa este script (como usuario ckan) antes de
subir o uwsgi. Correcoes em relacao ao original da imagem:

  * a checagem do Solr fazia eval() da resposta JSON; com o Solr 8 da imagem
    ckan/ckan-solr:2.9 a resposta contem `true`/`false` e o eval estourava
    NameError, abortando o prerun ANTES de criar o sysadmin;
  * CalledProcessError.output e bytes no Python 3; o teste
    `"OperationalError" in e.output` levantava TypeError e escondia o erro real;
  * a lista de plugins agora e gravada ANTES do `ckan db init`, entao um plugin
    inexistente (ex.: `activity`, que so existe a partir do CKAN 2.10) aparece
    aqui como erro explicito em vez de virar "Internal Server Error" no uwsgi;
  * esperas com retry sem recursao e mensagens claras nos logs.
"""
import json
import os
import re
import subprocess
import sys
import time

import psycopg2

try:
    from urllib.request import urlopen
    from urllib.error import URLError
except ImportError:  # pragma: no cover
    from urllib2 import urlopen, URLError

CKAN_INI = os.environ.get('CKAN_INI', '/srv/app/ckan.ini')
RETRIES = int(os.environ.get('PRERUN_RETRIES', '30'))
WAIT = int(os.environ.get('PRERUN_WAIT', '5'))


def log(msg):
    print('[prerun] {}'.format(msg))
    sys.stdout.flush()


def fail(msg, output=None):
    log('ERRO: ' + msg)
    if output:
        if isinstance(output, bytes):
            output = output.decode('utf-8', 'replace')
        print(output)
    sys.stdout.flush()
    sys.exit(1)


def run(cmd, stdout_only=False):
    """Executa um comando do CKAN e devolve a saida (str).

    stdout_only=True descarta o stderr (logs do CKAN) do resultado -- usado
    quando a saida e SQL a ser executado.
    """
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE if stdout_only else subprocess.STDOUT)
    out, err = proc.communicate()
    if proc.returncode != 0:
        fail('comando falhou: {}'.format(' '.join(cmd)),
             (out or b'') + (err or b''))
    return out.decode('utf-8', 'replace')


def wait_db(env_var):
    conn_str = os.environ.get(env_var)
    if not conn_str:
        log('{} nao definido, pulando checagem'.format(env_var))
        return
    for attempt in range(1, RETRIES + 1):
        try:
            psycopg2.connect(conn_str).close()
            log('{}: banco acessivel'.format(env_var))
            return
        except psycopg2.Error as e:
            log('{}: banco indisponivel ({}/{}): {}'.format(
                env_var, attempt, RETRIES, str(e).strip()))
            time.sleep(WAIT)
    fail('nao foi possivel conectar ao banco ({})'.format(env_var))


def wait_solr():
    url = os.environ.get('CKAN_SOLR_URL', '')
    if not url:
        log('CKAN_SOLR_URL nao definido, pulando checagem')
        return
    search_url = '{}/select/?q=*:*&rows=0&wt=json'.format(url.rstrip('/'))
    for attempt in range(1, RETRIES + 1):
        try:
            json.loads(urlopen(search_url, timeout=10).read().decode('utf-8'))
            log('Solr acessivel')
            return
        except (URLError, ValueError, OSError) as e:
            log('Solr indisponivel ({}/{}): {}'.format(attempt, RETRIES, e))
            time.sleep(WAIT)
    fail('nao foi possivel conectar ao Solr em {}'.format(url))


def update_plugins():
    plugins = os.environ.get('CKAN__PLUGINS', '').strip()
    if not plugins:
        return
    log('ckan.plugins = {}'.format(plugins))
    run(['ckan', 'config-tool', CKAN_INI, 'ckan.plugins = {}'.format(plugins)])


def init_db():
    log('ckan db init (cria ou atualiza as tabelas) - inicio')
    out = run(['ckan', '-c', CKAN_INI, 'db', 'init'])
    if 'PluginNotFoundException' in out:
        fail('plugin nao encontrado', out)
    log('ckan db init - fim')


def init_datastore_db():
    conn_str = os.environ.get('CKAN_DATASTORE_WRITE_URL')
    if not conn_str:
        log('DataStore nao configurado, pulando permissoes')
        return
    log('permissoes do DataStore - inicio')
    perms_sql = run(['ckan', '-c', CKAN_INI, 'datastore', 'set-permissions'],
                    stdout_only=True)
    # remove o meta-comando do psql, que o psycopg2 nao entende
    perms_sql = re.sub(r'\\connect "(.*)"', '', perms_sql)
    if 'GRANT' not in perms_sql.upper():
        fail('saida inesperada de "ckan datastore set-permissions"', perms_sql)
    connection = psycopg2.connect(conn_str)
    try:
        with connection.cursor() as cursor:
            cursor.execute(perms_sql)
        connection.commit()
    except psycopg2.Error as e:
        fail('nao foi possivel aplicar as permissoes do DataStore', str(e))
    finally:
        connection.close()
    log('permissoes do DataStore - fim')


def create_sysadmin():
    name = os.environ.get('CKAN_SYSADMIN_NAME')
    password = os.environ.get('CKAN_SYSADMIN_PASSWORD')
    email = os.environ.get('CKAN_SYSADMIN_EMAIL')
    if not (name and password and email):
        log('CKAN_SYSADMIN_* nao definidos, pulando sysadmin')
        return
    out = run(['ckan', '-c', CKAN_INI, 'user', 'show', name])
    if 'User:None' not in re.sub(r'\s', '', out):
        log('usuario {} ja existe'.format(name))
    else:
        run(['ckan', '-c', CKAN_INI, 'user', 'add', name,
             'password=' + password, 'email=' + email])
        log('usuario {} criado'.format(name))
    run(['ckan', '-c', CKAN_INI, 'sysadmin', 'add', name])
    log('{} e sysadmin'.format(name))


if __name__ == '__main__':
    if os.environ.get('MAINTENANCE_MODE', '').lower() == 'true':
        log('modo manutencao, nada a fazer')
        sys.exit(0)
    wait_db('CKAN_SQLALCHEMY_URL')
    update_plugins()
    init_db()
    wait_db('CKAN_DATASTORE_WRITE_URL')
    init_datastore_db()
    wait_solr()
    create_sysadmin()
    log('concluido com sucesso')
PRERUN_FILE

RUN sed -i 's/\r$//' /srv/app/prerun.py \
    && chown -R ckan:ckan /srv/app /var/lib/ckan
