# -*- coding: utf-8 -*-
"""
ckanext-dsaudit -- plugin enxuto para CKAN 2.9.5 (substitui o plugins.py do
upstream ckan/ckanext-dsaudit@c398842).

So captura e armazena; nao ha telas. Registra:
  * DataStore: linhas inseridas/alteradas/removidas com valor anterior -> novo
    (datastore_create / datastore_upsert / datastore_delete);
  * metadados do dataset e dos recursos campo a campo, inclusive de datasets
    privados (package_create / package_update / package_delete);
  * arquivos enviados (upload): cada versao guardada em disco e diff linha a
    linha de CSV/TSV/TXT/XLSX (IResourceController).

Leitura: action `dsaudit_activity_list` (API). `activity_diff` e encadeada so
para a pagina nativa "Changes" do CKAN continuar funcionando com os eventos
acima no historico.

Os templates e helpers do upstream nao sao registrados (sem IConfigurer /
ITemplateHelpers): no Activity Stream nativo os eventos usam o template
generico do CKAN (snippets/activities/fallback.html).
"""
import logging

import ckan.plugins as p

from ckanext.dsaudit import actions, versions

log = logging.getLogger(__name__)


class DSAuditPlugin(p.SingletonPlugin):
    p.implements(p.IActions)
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

    def get_actions(self):
        return {
            'datastore_create': actions.datastore_create,
            'datastore_upsert': actions.datastore_upsert,
            'datastore_delete': actions.datastore_delete,
            'package_update': actions.package_update,
            'package_create': actions.package_create,
            'package_delete': actions.package_delete,
            'dsaudit_activity_list': actions.dsaudit_activity_list,
            'activity_diff': actions.activity_diff,
        }
