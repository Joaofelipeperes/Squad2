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
