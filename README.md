# CkanSquad2 — CKAN 2.9.5 Infrastructure

Infraestrutura containerizada (Docker Compose) da plataforma de dados abertos **CKAN 2.9.5**, com PostgreSQL/PostGIS, Solr, Redis e **auditoria detalhada de alterações no DataStore — até o campo alterado de cada linha**.

---

## Pré-requisitos

* [Docker Desktop](https://www.docker.com/products/docker-desktop/) (ou Docker Engine + plugin Compose).
* [Git](https://git-scm.com/).

---

## Subir o ambiente

### 1. Clonar o repositório

```
git clone https://github.com/SEU_USUARIO/CkanSquad2.git
cd CkanSquad2
```

### 2. Construir e subir

```
docker compose up -d --build --force-recreate
```

`--force-recreate` é importante quando o container já existia: a lista de plugins fica gravada no `ckan.ini` **dentro** do container.

O `prerun` (substituído pela versão embutida no `Dockerfile`) faz a cada start: espera o Postgres, grava `ckan.plugins`, `ckan db init`, permissões do DataStore, espera o Solr e cria o sysadmin. Acompanhe com:

```
docker compose logs -f ckan
```

A linha `[prerun] concluido com sucesso` indica que está tudo certo. Qualquer problema aparece como `[prerun] ERRO: ...`.

### 3. Acessar

* Portal: <http://localhost:5000>
* Status da API: <http://localhost:5000/api/3/action/status_show>
* Sysadmin: `admin` / `Admin12345` (definido em `docker-compose.yml` — **troque a senha** antes de expor o ambiente).

### 4. Se já havia datasets (índice do Solr)

O volume do Solr passou a ser `solr_index` montado em `/var/solr` (o caminho antigo não era usado pelo Solr 8 e o índice se perdia a cada recriação). Depois do primeiro start, reindexe:

```
docker compose exec ckan ckan -c /srv/app/ckan.ini search-index rebuild
```

## Auditoria de alterações

### Camada 1 — Metadados (nativo do CKAN 2.9)

* **Activity Stream** — aba *Activity Stream* de cada dataset, organização e usuário.
* **Diff campo a campo** — link *Changes* de cada evento (`/dataset/changes/<activity_id>`): mostra exatamente o que mudou no dataset e nos recursos (nome, descrição, URL, formato...), com autor e data.

### Camada 1b — Metadados campo a campo, inclusive datasets privados (`changed metadata`)

O CKAN 2.9 **não gera atividade para datasets privados** e não guarda diff por campo. A camada `dsaudit` encadeia `package_create`, `package_update` (usado também pela interface, `package_patch`, `resource_create/update/delete`) e `package_delete`, e grava um evento `changed metadata` com **valor anterior → valor novo** de cada campo alterado:

* dataset: `author`, `author_email`, `maintainer`, `maintainer_email`, `title`, `notes`, `license_id`, `version`, `url`, `private`, `owner_org`, `state`, `tags`, `groups`, `extras.<chave>` e campos personalizados;
* recursos: recurso adicionado/removido e cada campo alterado (`name`, `description`, `url`, `format`, `size`, `last_modified`...).

O evento é gravado na **mesma transação** da alteração: se um falhar, o outro também é desfeito.

### Camada 1c — Arquivos enviados pela interface ou API, com versões e diff linha a linha (`changed resource file`)

Ao **adicionar** ou **substituir** o arquivo de um recurso (upload, `url_type = upload`):

* **Cada versão do arquivo é guardada** em `/var/lib/ckan/dsaudit_versions/<resource_id>/` (volume `ckan_storage`). O CKAN sobrescreve o arquivo no mesmo lugar; por isso a versão atual é copiada **antes** da troca (`before_update`). Em modo estrito, se não der para guardar a versão atual, a substituição é **recusada**.
* Para **CSV, TSV, TXT e XLSX** (1ª planilha), o evento traz o diff linha a linha: linhas *alteradas* (campo, valor anterior → novo), *novas* e *removidas*, além de colunas adicionadas/removidas.
  * As linhas são casadas pela **coluna-chave**: o campo `chave_auditoria` do recurso (ex.: `codigo` ou `ano,municipio`, definível pela API `resource_patch`) ou, se não houver, a primeira coluna de `CKANEXT__DSAUDIT__FILE_KEY_COLUMNS` que exista e seja única nas duas versões. Sem chave, compara pela **posição/sequência** das linhas.
  * Codificação (UTF-8, Windows-1252/Latin-1) e separador (`,` `;` tab `|`) são detectados automaticamente.
* Outros formatos (PDF, ZIP...): as versões são guardadas e o evento registra a troca, sem diff de conteúdo.
* Na aba Auditoria, editores podem **baixar qualquer versão** guardada (`/dataset/<nome>/auditoria/versao/<resource_id>/<n>`).

Recursos que já existiam antes desta versão: a versão atual é guardada automaticamente na primeira substituição.

### Camada 2 — Conteúdo do DataStore, linha a linha (`ckanext-dsaudit` + compatibilidade 2.9)

A imagem instala [`ckanext-dsaudit`](https://github.com/ckan/ckanext-dsaudit) fixado no commit `c398842` e aplica por cima a camada de compatibilidade CKAN 2.9 (arquivos `plugins.py`, `actions.py`, `helpers.py`, `views.py` e templates, embutidos no `Dockerfile` com blocos `COPY <<"..."`). Ela encadeia as actions de escrita do DataStore e grava uma atividade para cada uma:

| Action | Atividade | O que fica registrado |
|---|---|---|
| `datastore_create` | `created datastore` + `changed datastore` | estrutura (colunas, tipos, chave primária) e linhas inseridas |
| `datastore_upsert` `method=insert` | `changed datastore` | linhas inseridas |
| `datastore_upsert` `method=update` / `upsert` | `changed datastore` | **para cada linha**: chave, `_id`, status (*alterada* / *nova* / *sem mudança*) e cada campo com **valor anterior → valor novo** |
| `datastore_delete` com `filters` | `deleted datastore` | filtros e o **conteúdo completo das linhas removidas** |
| `datastore_delete` sem filtros | `deleted datastore` | exclusão da tabela |

Todas com usuário e data/hora. O valor anterior é lido do banco **antes** da gravação, usando a chave única (`primary_key`) da tabela.

**Onde ver**

* Aba **Auditoria** do dataset (`/dataset/<nome>/auditoria`) — visível para quem pode editar o dataset; reúne metadados, arquivos enviados e DataStore; filtros por recurso e tipo; paginação.
* **Exportar CSV** (`/dataset/<nome>/auditoria.csv`) — uma linha por campo alterado: `timestamp_utc, usuario, tipo, metodo, resource_id, chave_linha, _id, status_linha, campo, valor_anterior, valor_novo`.
* Aba **Activity Stream** — os mesmos eventos; detalhes só para editores (visitantes veem apenas "alterou registros do DataStore").
* API: `GET /api/3/action/dsaudit_activity_list?id=<dataset>&resource_id=<opcional>&activity_type=<opcional>&limit=&offset=` (exige permissão de edição).

**Garantia de não perder alterações** (padrão):

* O valor anterior é capturado para **qualquer quantidade de linhas** por chamada (leitura em blocos, paginada pelo `rows_max` do DataStore).
* O evento de auditoria é montado e validado **antes** da gravação e confirmado logo depois dela. Se a gravação falhar, o evento é descartado.
* **Modo estrito:** se não for possível capturar o "antes" (erro de leitura ou limite excedido), a chamada é **recusada** com erro `dsaudit` e **nada é alterado** no DataStore.
* `datastore_delete` guarda **todas** as linhas removidas, inclusive na exclusão da tabela inteira.
* O CSV exporta **todos** os eventos (sem o corte de 500).

**Configuração** (variáveis no `docker-compose.yml`):

* `CKANEXT__DSAUDIT__MAX_DIFF_RECORDS` (padrão 0 = sem limite) — limite opcional de linhas por chamada. Com modo estrito, chamadas acima do limite são recusadas.
* `CKANEXT__DSAUDIT__STRICT` (padrão `true`) — recusa a alteração quando a auditoria completa não pode ser garantida. Com `false`, a alteração é aplicada e só o aviso vai para o log (comportamento antigo).
* `CKANEXT__DSAUDIT__CAPTURE_DROP` (padrão `true`) — guarda o conteúdo da tabela quando ela é excluída por inteiro.
* `CKANEXT__DSAUDIT__FILE_KEY_COLUMNS` (padrão `id`) — nomes de coluna usados como chave no diff de arquivos enviados, separados por espaço.
* `CKANEXT__DSAUDIT__PREVIEW_RECORDS` (padrão 12) — linhas exibidas por evento na tela (o CSV/API trazem tudo).
* `UWSGI_HARAKIRI` (padrão 300) — tempo máximo de uma requisição, em segundos. Se uma carga grande passar desse tempo, a requisição é abortada e a alteração **não** é aplicada (nem registrada); aumente o valor ou envie em lotes.

**Limitações**

* Recursos por **link externo** (URL de outro site) não têm o conteúdo baixado nem comparado: a troca da URL aparece no evento de metadados.
* O diff de arquivos considera só a **primeira planilha** do XLSX; `.xls` (Excel 97-2003) e `.ods` só têm as versões guardadas.
* As ações em massa da página da organização (tornar público/privado, excluir vários datasets) não passam por `package_update` e não geram evento `changed metadata`.
* Linhas alteradas por SQL direto no banco, fora da API do CKAN, não são registradas.
* O DataStore e a tabela de atividades ficam em bancos diferentes (`datastore` e `ckan`), então não há uma transação única. A janela de risco é o instante entre a confirmação da gravação e a do evento; se o evento falhar nesse ponto, o conteúdo completo dele é escrito no log do container (`docker compose logs ckan`, nível CRITICAL).
* Cargas muito grandes geram eventos grandes (o JSON completo fica na tabela `activity`). Para centenas de milhares de linhas, prefira enviar em lotes: cada lote vira um evento com diff completo.

#### Como testar

```
# 1) criar tabela com chave primária
curl -X POST http://localhost:5000/api/3/action/datastore_create \
  -H "Authorization: <API_TOKEN>" -H "Content-Type: application/json" \
  -d '{"resource":{"package_id":"<DATASET>","name":"tabela"},
       "fields":[{"id":"id","type":"int"},{"id":"nome","type":"text"}],
       "primary_key":["id"],
       "records":[{"id":1,"nome":"antigo"}]}'

# 2) alterar uma linha
curl -X POST http://localhost:5000/api/3/action/datastore_upsert \
  -H "Authorization: <API_TOKEN>" -H "Content-Type: application/json" \
  -d '{"resource_id":"<RESOURCE_ID>","method":"upsert","records":[{"id":1,"nome":"novo valor"}]}'
```

Em `/dataset/<DATASET>/auditoria` aparece: `id=1 · alterada · nome · antigo → novo valor`.

O token de API é gerado em *Perfil do usuário → API Tokens* (ou `docker compose exec ckan ckan -c /srv/app/ckan.ini user token add admin meu_token`).



## Importação de dados

O script `importar_ckan_goias.py` carrega os metadados de `metadados_ckan_goias.json` na instância. Ajuste `CKAN_URL` e `API_KEY` (um token de API do sysadmin) no topo do arquivo antes de rodar.

## Comandos e Consultas Úteis

http://localhost:5000/api/3/action/status_show (Status do Ckan, versão, saúde, extenções)
http://localhost:5000/api/3/action/dsaudit_activity_list?id=SUBSTITUIRPORIDDODATASET&limit=500   (Consulta por HTTP para as alterações do dataset)

docker compose exec db psql -U ckan -d ckan -c "SELECT timestamp, activity_type, data FROM activity WHERE activity_type LIKE '%datastore%' ORDER BY timestamp DESC LIMIT 20;"   (Consulta diretamente no banco as alterações linha a linha)

Observação, ao substituir nas requisições HTTP o localhost pela API de dadosabertos.go.gov.br, podemos obter informações do sistema Ckan do portal de dados abertos.

Para consultar diretamente no banco de dados os logs podemos:

docker compose exec db psql -U ckan -d ckan

SELECT a.timestamp AT TIME ZONE 'UTC' AT TIME ZONE 'America/Sao_Paulo' AS data_hora,
       u.name AS usuario, p.name AS dataset, c->>'field' AS campo,
       c->>'old' AS valor_anterior, c->>'new' AS valor_novo
FROM activity a
JOIN "user" u  ON u.id = a.user_id
JOIN package p ON p.id = a.object_id
CROSS JOIN LATERAL json_array_elements(a.data::json->'changes') AS c
WHERE a.activity_type = 'changed metadata'
  AND c->>'field' IN ('author', 'author_email') //pode remover para consulta trazer todos os campos do recurso (tags, extras, nome, url, descricao)
ORDER BY a.timestamp;


SELECT a.timestamp AT TIME ZONE 'UTC' AT TIME ZONE 'America/Sao_Paulo' AS data_hora,
       u.name AS usuario, a.activity_type AS tipo, r.name AS recurso,
       ch->'key' AS chave_linha, ch->>'status' AS status,
       f->>'field' AS campo, f->>'old' AS valor_anterior, f->>'new' AS valor_novo
FROM activity a
JOIN "user" u ON u.id = a.user_id
LEFT JOIN resource r ON r.id = a.data::json->>'resource_id'
CROSS JOIN LATERAL json_array_elements(a.data::json->'changes') AS ch
CROSS JOIN LATERAL json_array_elements(ch->'fields') AS f
WHERE a.activity_type IN ('changed datastore', 'changed resource file')
ORDER BY a.timestamp DESC;