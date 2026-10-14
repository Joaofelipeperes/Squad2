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

Versao enxuta (sem telas): os registros ficam na tabela `activity` do banco
do CKAN e sao lidos pela API `dsaudit_activity_list`. Nao ha aba Auditoria,
pagina /dataset/<id>/auditoria, exportacao CSV nem templates proprios; no
Activity Stream nativo os eventos aparecem com o template generico do CKAN.

Configuracao (ckan.ini ou variavel de ambiente via envvars):
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
    ObjectNotFound, ValidationError, asbool,
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
# leitura das atividades pela API (usada pelo produto final e pelo
# teste_auditoria.ps1)
# ---------------------------------------------------------------------------

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
