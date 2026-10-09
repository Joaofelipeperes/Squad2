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
