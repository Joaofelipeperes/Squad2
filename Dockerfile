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
# ---------------------------------------------------------------------------

FROM ckan/ckan-base:2.9.5

# A imagem base roda como root: o start_ckan.sh dela usa `sudo -u ckan` para o
# prerun e para o uwsgi. NAO troque o usuario final (USER ckan).
USER root

# Commit fixado para builds reprodutiveis.
ARG DSAUDIT_REF=c3988427821c43e5dac5078c6adc42f7f16d3fa4
RUN pip3 install --no-cache-dir -e \
    "git+https://github.com/ckan/ckanext-dsaudit.git@${DSAUDIT_REF}#egg=ckanext-dsaudit"

# ===========================================================================
# Camada de compatibilidade CKAN 2.9 + auditoria linha a linha
# (gravada em /tmp/dsaudit-ckan29 e copiada sobre a extensao instalada)
# ===========================================================================

# --- 2.9_templates/dsaudit/audit.html ---
COPY <<"DSAUDIT_FILE_00" /tmp/dsaudit-ckan29/2.9_templates/dsaudit/audit.html
{% extends "package/read_base.html" %}

{% block subtitle %}Auditoria {{ g.template_title_delimiter }} {{ super() }}{% endblock %}

{% block primary_content_inner %}
  <h2>Auditoria de altera&ccedil;&otilde;es do DataStore</h2>
  <p class="text-muted">
    Cada inser&ccedil;&atilde;o, altera&ccedil;&atilde;o e exclus&atilde;o de linhas nos recursos DataStore deste dataset,
    com usu&aacute;rio, data/hora e &mdash; para altera&ccedil;&otilde;es &mdash; o valor anterior e o novo de cada campo.
    Altera&ccedil;&otilde;es de metadados (nome, descri&ccedil;&atilde;o, URL do recurso etc.) ficam na aba
    <a href="{{ h.url_for(dataset_type ~ '.activity', id=pkg.name) }}">Activity Stream</a> (link &laquo;Changes&raquo;).
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
      <option value="changed datastore" {% if activity_type == 'changed datastore' %}selected{% endif %}>Inser&ccedil;&otilde;es / altera&ccedil;&otilde;es</option>
      <option value="deleted datastore" {% if activity_type == 'deleted datastore' %}selected{% endif %}>Exclus&otilde;es</option>
      <option value="created datastore" {% if activity_type == 'created datastore' %}selected{% endif %}>Estrutura da tabela</option>
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

Configuracao (ckan.ini ou variavel de ambiente via envvars):
  ckanext.dsaudit.preview_records   (padrao 12)   linhas exibidas por atividade
  ckanext.dsaudit.max_diff_records  (padrao 1000) limite de linhas para as
                                                  quais o "antes" e capturado
"""
import json
import logging

import sqlalchemy

from ckan.plugins.toolkit import (
    chained_action, get_action, config, check_access, side_effect_free,
    NotAuthorized, ObjectNotFound,
)
from ckan.logic.schema import default_create_activity_schema

log = logging.getLogger(__name__)

RW_URL_TYPES = ('datastore',)
DSAUDIT_TYPES = ('created datastore', 'changed datastore', 'deleted datastore')


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
    try:
        return int(config.get('ckanext.dsaudit.max_diff_records', 1000))
    except (TypeError, ValueError):
        return 1000


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
        for r in wanted:
            srval = search(scontext, {
                'resource_id': resource_id,
                'filters': {k: r[k] for k in keys},
                'limit': 1,
                'include_total': False,
            })
            for row in _plain(srval['records']):
                old[_key_of(row, keys)] = row
    return old


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


def _create_activity(context, res, activity_type, data):
    acontext = dict(
        fresh_context(context),
        ignore_auth=True,
        schema=dsaudit_create_activity_schema(),
    )
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


@chained_action
def datastore_upsert(original_action, context, data_dict):
    records = data_dict.get('records', []) or []
    method = data_dict.get('method', 'upsert')
    resource_id = data_dict.get('resource_id', data_dict.get('id'))

    # captura o "antes" ANTES de gravar
    keys, old_rows = [], None
    res = context['model'].Resource.get(resource_id) if resource_id else None
    if (res is not None and res.url_type in RW_URL_TYPES
            and method in ('update', 'upsert') and records
            and not data_dict.get('dry_run')
            and len(records) <= _max_diff_records()):
        try:
            keys = _unique_keys(res.id)
            if keys:
                old_rows = _fetch_old_rows(context, res.id, records, keys)
        except Exception:
            log.exception('dsaudit: nao foi possivel ler valores anteriores')
            old_rows = None

    rval = original_action(context, data_dict)
    res = context['model'].Resource.get(rval.get('resource_id', resource_id))
    if res is None or res.url_type not in RW_URL_TYPES:
        return rval
    if rval.get('dry_run'):
        return rval

    if 'records' in rval:
        records = rval['records']
    all_fields = _ds_fields(context, res.id)
    activity_data = {
        'fields': [
            f for f in all_fields
            if any(f['id'] in r for r in records)
        ],
        'records': records,
        'method': rval.get('method', method),
        'resource_id': res.id,
    }
    if old_rows is not None:
        activity_data['keys'] = keys
        activity_data['changes'] = _build_changes(records, old_rows, keys)
    _create_activity(context, res, 'changed datastore', activity_data)
    return rval


@chained_action
def datastore_delete(original_action, context, data_dict):
    res = context['model'].Resource.get(
        data_dict.get('resource_id', data_dict.get('id')))
    if not res or res.url_type not in RW_URL_TYPES:
        return original_action(context, data_dict)

    activity_data = {}
    if 'filters' in data_dict:
        srval = get_action('datastore_search')(_search_context(context), {
            'resource_id': res.id,
            'filters': data_dict['filters'],
            'limit': _max_diff_records(),
        })
        activity_data = {
            'fields': srval['fields'],
            'records': _plain(srval['records']),
            'total': srval.get('total'),
        }

    rval = original_action(context, data_dict)

    activity_data['filters'] = rval.get('filters', data_dict.get('filters'))
    activity_data['resource_id'] = res.id
    _create_activity(context, res, 'deleted datastore', activity_data)
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
        if resource_id and data.get('resource_id') != resource_id:
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
import ckan.plugins as p

from ckanext.dsaudit import views, helpers, actions
from ckan.lib.plugins import DefaultTranslation


class DSAuditPlugin(p.SingletonPlugin, DefaultTranslation):
    p.implements(p.IConfigurer)
    p.implements(p.IBlueprint)
    p.implements(p.IActions)
    p.implements(p.ITemplateHelpers, inherit=True)
    p.implements(p.ITranslation)

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
    result = tk.get_action('dsaudit_activity_list')(_context(), {
        'id': pkg_dict['id'],
        'resource_id': resource_id,
        'limit': 500,
    })
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
        else:
            w.writerow(base + ['', '', '', '', '', ''])
    filename = 'auditoria-%s.csv' % pkg_dict['name']
    return Response(
        out.getvalue(), mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=%s' % filename})


dsaudit.add_url_rule('/dataset/<id>/auditoria', view_func=audit)
dsaudit.add_url_rule('/dataset/<id>/auditoria.csv', view_func=audit_csv)
DSAUDIT_FILE_08

# --- aplica a camada ---------------------------------------------------------
RUN set -eu; \
    SRC=/tmp/dsaudit-ckan29; \
    DST=/srv/app/src/ckanext-dsaudit/ckanext/dsaudit; \
    test -f "$DST/plugins.py"; \
    find "$SRC" -type f -exec sed -i 's/\r$//' {} +; \
    cp "$SRC/plugins.py" "$SRC/actions.py" "$SRC/helpers.py" "$SRC/views.py" "$DST/"; \
    mkdir -p "$DST/2.9_templates"; \
    cp -R "$SRC/2.9_templates/." "$DST/2.9_templates/"; \
    if grep -rnE "in h\.datastore_rw_resource_url_types|snippet 'datastore/snippets/dictionary_view" "$DST"/*.py "$DST/2.9_templates"; then echo "camada incompleta" >&2; exit 1; fi; \
    python3 -m py_compile "$DST/plugins.py" "$DST/actions.py" "$DST/helpers.py" "$DST/views.py"; \
    rm -rf "$SRC"; \
    echo "ckanext-dsaudit: camada CKAN 2.9 aplicada"

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
