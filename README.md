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

* Aba **Auditoria** do dataset (`/dataset/<nome>/auditoria`) — visível para quem pode editar o dataset; filtros por recurso e tipo; paginação.
* **Exportar CSV** (`/dataset/<nome>/auditoria.csv`) — uma linha por campo alterado: `timestamp_utc, usuario, tipo, metodo, resource_id, chave_linha, _id, status_linha, campo, valor_anterior, valor_novo`.
* Aba **Activity Stream** — os mesmos eventos; detalhes só para editores (visitantes veem apenas "alterou registros do DataStore").
* API: `GET /api/3/action/dsaudit_activity_list?id=<dataset>&resource_id=<opcional>&activity_type=<opcional>&limit=&offset=` (exige permissão de edição).

**Configuração opcional** (variáveis no `docker-compose.yml`):

* `CKANEXT__DSAUDIT__PREVIEW_RECORDS` (padrão 12) — linhas exibidas por evento na tela (o CSV/API trazem tudo).
* `CKANEXT__DSAUDIT__MAX_DIFF_RECORDS` (padrão 1000) — acima disso, um `upsert` grava as linhas enviadas sem capturar o valor anterior.

**Limitações**

* O diff linha a linha vale para dados **no DataStore** (`url_type = datastore`, ou seja, gravados via API `datastore_*`). Um arquivo CSV/XLSX enviado por upload ou link externo não é comparado linha a linha — a troca do arquivo aparece no diff de metadados (camada 1). Para auditar o conteúdo, carregue os dados no DataStore via API.
* Linhas alteradas por SQL direto no banco, fora da API do CKAN, não são registradas.

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

