# ckanext-dsaudit — versão enxuta de auditoria para CKAN 2.9.5

Código completo da extensão, vendorizado neste repositório. Ponto de partida: a extensão oficial
[`ckan/ckanext-dsaudit`](https://github.com/ckan/ckanext-dsaudit), commit
`c3988427821c43e5dac5078c6adc42f7f16d3fa4`. A oficial é escrita para CKAN 2.10/2.11 e quebra no
2.9.5; os arquivos abaixo corrigem isso e ampliam a captura. O `Dockerfile` copia esta pasta para
`/srv/app/src/ckanext-dsaudit` e instala com `pip install -e`.

**Só captura e armazena.** Não há telas: os registros são lidos pela API
`dsaudit_activity_list` (pelo produto final, pelo `teste_auditoria.ps1` ou por SQL).

## Arquivos

| Arquivo | Situação | O que faz |
|---|---|---|
| `ckanext/dsaudit/plugins.py` | alterado (era do upstream) | Registra as actions (`IActions`) e os ganchos de upload (`IResourceController`). Não registra templates, helpers nem páginas. |
| `ckanext/dsaudit/actions.py` | alterado (era do upstream) | Captura do DataStore com valor anterior → novo, metadados campo a campo, modo estrito, API `dsaudit_activity_list` e correção do `activity_diff` nativo. |
| `ckanext/dsaudit/versions.py` | novo | Guarda cada versão de arquivo enviado e calcula o diff linha a linha de CSV/TSV/TXT/XLSX. |

Foram **removidos** do upstream os arquivos que só servem para telas: `views.py`, `helpers.py`,
`templates/` e `2.9_templates/`. No `setup.py` foi declarada a dependência `openpyxl` e foi
acrescentado o `MANIFEST.in`; `setup.cfg`, `i18n/` e as licenças (`COPYING*`) são os originais.

## Requisitos e instalação

* CKAN **2.9.x** em Python 3 (não funciona no 2.10 ou superior), com o plugin `datastore` ativo e o
  activity stream habilitado (padrão do 2.9).
* Dependência instalada automaticamente pelo `pip`: `openpyxl` (diff de planilhas `.xlsx`).
* Não cria tabelas nem exige migração de banco: grava na tabela `activity` do próprio CKAN.

```bash
pip install -e /caminho/ckanext-dsaudit      # ou: pip install /caminho/ckanext-dsaudit
```

No `ckan.ini`, acrescente `dsaudit` em `ckan.plugins` (depois de `datastore`) e reinicie o CKAN.

## O que é registrado (tabela `activity` do banco `ckan`)

| `activity_type` | Origem | Conteúdo de `data` |
|---|---|---|
| `created datastore` | `datastore_create` | estrutura da tabela (campos, tipos, chave) |
| `changed datastore` | `datastore_create` / `datastore_upsert` | linhas enviadas; em `update`/`upsert`, `changes` com cada campo valor anterior → novo |
| `deleted datastore` | `datastore_delete` | filtros e todas as linhas removidas (ou a tabela inteira, com `capture_drop`) |
| `changed metadata` | `package_create` / `package_update` / `package_delete` | campos do dataset e dos recursos alterados (antes → depois), inclusive datasets privados |
| `changed resource file` | upload de arquivo (interface ou API) | versão nova e anterior (nome, tamanho, sha256) e diff linha a linha do conteúdo |

Versões dos arquivos: `<ckan.storage_path>/dsaudit_versions/<resource_id>/` (no Docker deste
repositório, `/var/lib/ckan/dsaudit_versions`, volume `ckan_storage`).

Não passam pela extensão (ficam só no histórico nativo do CKAN, sem antes → depois): ações em
massa da página da organização (`bulk_update_private/public/delete`) e `dataset_purge`.

## Leitura

```
GET /api/3/action/dsaudit_activity_list?id=<dataset>&resource_id=&activity_type=&limit=&offset=
Authorization: <token de quem pode editar o dataset>
```

## Configuração

Cada opção pode ir no `ckan.ini` ou, com o plugin `envvars`, numa variável de ambiente (como no
`docker-compose.yml`).

| `ckan.ini` | Variável de ambiente | Padrão | Efeito |
|---|---|---|---|
| `ckanext.dsaudit.strict` | `CKANEXT__DSAUDIT__STRICT` | `true` | Recusa a alteração se a auditoria completa não puder ser gravada |
| `ckanext.dsaudit.max_diff_records` | `CKANEXT__DSAUDIT__MAX_DIFF_RECORDS` | `0` (sem limite) | Limite de linhas cujo "antes" é capturado por chamada |
| `ckanext.dsaudit.capture_drop` | `CKANEXT__DSAUDIT__CAPTURE_DROP` | `true` | Guarda o conteúdo da tabela excluída por inteiro |
| `ckanext.dsaudit.file_key_columns` | `CKANEXT__DSAUDIT__FILE_KEY_COLUMNS` | `id` | Colunas-chave candidatas, separadas por espaço (usa a primeira com valores únicos) para casar linhas entre versões de arquivo; sem nenhuma, compara por posição |
| `ckanext.dsaudit.versions_path` | `CKANEXT__DSAUDIT__VERSIONS_PATH` | `<storage_path>/dsaudit_versions` | Onde as versões dos arquivos ficam |

Por recurso, o campo extra `chave_auditoria` (ex.: `codigo` ou `ano,municipio`) tem prioridade
sobre `file_key_columns`.

## Diferenças para o upstream

1. Correções para o 2.9.5: helper `datastore_rw_resource_url_types` (só existe no 2.11),
   `datastore_info` sem `fields`, `LazyJSONObject` não serializável, `rval['method']` inexistente.
2. Captura do valor anterior das linhas em `upsert`/`update`, modo estrito e captura de exclusões.
3. Auditoria de metadados (`changed metadata`) e de arquivos enviados (`changed resource file`).
4. Action `dsaudit_activity_list` e correção do `activity_diff` (página nativa "Changes").
5. Removido: páginas, exportação CSV, templates, helpers e o encadeamento de
   `package_activity_list` (só servia para a tela).
