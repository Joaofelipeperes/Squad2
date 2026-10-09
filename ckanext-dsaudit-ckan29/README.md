# ckanext-dsaudit-ckan29 — camada enxuta de auditoria para CKAN 2.9.5

Arquivos aplicados pelo `Dockerfile` **por cima** da extensão oficial
[`ckan/ckanext-dsaudit`](https://github.com/ckan/ckanext-dsaudit) (commit `c398842`).
A oficial é escrita para CKAN 2.10/2.11 e quebra no 2.9.5; esta pasta corrige isso e amplia a
captura.

**Só captura e armazena.** Não há telas: os registros são lidos pela API
`dsaudit_activity_list` (pelo produto final, pelo `teste_auditoria.ps1` ou por SQL).

## Arquivos

| Arquivo | No container | O que faz |
|---|---|---|
| `plugins.py` | substitui o do upstream | Registra as actions (`IActions`) e os ganchos de upload (`IResourceController`). Não registra templates, helpers nem páginas. |
| `actions.py` | substitui o do upstream | Captura do DataStore com valor anterior → novo, metadados campo a campo, modo estrito, API `dsaudit_activity_list` e correção do `activity_diff` nativo. |
| `versions.py` | novo | Guarda cada versão de arquivo enviado e calcula o diff linha a linha de CSV/TSV/TXT/XLSX. |

O `Dockerfile` também **remove** do upstream o que só serve para telas: `views.py`, `helpers.py`,
`templates/` e `2.9_templates/`. O `prerun.py` corrigido do CKAN fica em `docker/prerun.py`.

## O que é registrado (tabela `activity` do banco `ckan`)

| `activity_type` | Origem | Conteúdo de `data` |
|---|---|---|
| `created datastore` | `datastore_create` | estrutura da tabela (campos, tipos, chave) |
| `changed datastore` | `datastore_create` / `datastore_upsert` | linhas enviadas; em `update`/`upsert`, `changes` com cada campo valor anterior → novo |
| `deleted datastore` | `datastore_delete` | filtros e todas as linhas removidas (ou a tabela inteira, com `capture_drop`) |
| `changed metadata` | `package_create` / `package_update` / `package_delete` | campos do dataset e dos recursos alterados (antes → depois), inclusive datasets privados |
| `changed resource file` | upload de arquivo (interface ou API) | versão nova e anterior (nome, tamanho, sha256) e diff linha a linha do conteúdo |

Versões dos arquivos: `/var/lib/ckan/dsaudit_versions/<resource_id>/` (volume `ckan_storage`).

Não passam pela extensão (ficam só no histórico nativo do CKAN, sem antes → depois): ações em
massa da página da organização (`bulk_update_private/public/delete`) e `dataset_purge`.

## Leitura

```
GET /api/3/action/dsaudit_activity_list?id=<dataset>&resource_id=&activity_type=&limit=&offset=
Authorization: <token de quem pode editar o dataset>
```

## Configuração (variáveis no `docker-compose.yml`)

| Variável | Padrão | Efeito |
|---|---|---|
| `CKANEXT__DSAUDIT__STRICT` | `true` | Recusa a alteração se a auditoria completa não puder ser gravada |
| `CKANEXT__DSAUDIT__MAX_DIFF_RECORDS` | `0` (sem limite) | Limite de linhas cujo "antes" é capturado por chamada |
| `CKANEXT__DSAUDIT__CAPTURE_DROP` | `true` | Guarda o conteúdo da tabela excluída por inteiro |
| `CKANEXT__DSAUDIT__FILE_KEY_COLUMNS` | `id` | Colunas-chave para casar linhas entre versões de arquivo |
| `CKANEXT__DSAUDIT__VERSIONS_PATH` | `<storage_path>/dsaudit_versions` | Onde as versões dos arquivos ficam |

## Diferenças para o upstream

1. Correções para o 2.9.5: helper `datastore_rw_resource_url_types` (só existe no 2.11),
   `datastore_info` sem `fields`, `LazyJSONObject` não serializável, `rval['method']` inexistente.
2. Captura do valor anterior das linhas em `upsert`/`update`, modo estrito e captura de exclusões.
3. Auditoria de metadados (`changed metadata`) e de arquivos enviados (`changed resource file`).
4. Action `dsaudit_activity_list` e correção do `activity_diff` (página nativa "Changes").
5. Removido: páginas, exportação CSV, templates, helpers e o encadeamento de
   `package_activity_list` (só servia para a tela).
