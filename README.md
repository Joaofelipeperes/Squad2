# CkanSquad2 — CKAN 2.9.5 Infrastructure

Infraestrutura containerizada (Docker Compose) da plataforma de dados abertos **CKAN 2.9.5**, com PostgreSQL/PostGIS, Solr, Redis e **auditoria detalhada de alterações no DataStore — até o campo alterado de cada linha**.

---

## Pré-requisitos

* [Docker Desktop](https://www.docker.com/products/docker-desktop/) (ou Docker Engine + plugin Compose).
* [Git](https://git-scm.com/).

---

## Subir o ambiente

### Script facilitador (Windows): `subir_ambiente.ps1`

Sobe todo o ambiente com um comando: o CKAN em Docker, o token de API, a carga dos datasets do portal, o teste da auditoria e, se pedido, o produto final (`produtofinal/`) já ligado ao CKAN. Foi feito para Windows (PowerShell 5.1 ou 7) com o Docker Desktop.

**Como rodar** (PowerShell, na pasta do repositório):

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force   # libera scripts só nesta janela
.\subir_ambiente.ps1                                                # CKAN + token
.\subir_ambiente.ps1 -Importar -Testar                              # + 445 datasets + teste da auditoria
.\subir_ambiente.ps1 -Tudo -AdminEmail voce@cge.go.gov.br           # tudo, inclusive o produto final
.\subir_ambiente.ps1 -Tudo -Reconstruir -AdminEmail voce@cge.go.gov.br   # 1ª vez ou após mudar a extensão
```

O `-Scope Process` vale só para a janela aberta; nada muda na política do Windows. A pasta precisa se chamar `Squad2`: o Docker usa o nome dela para nomear volumes e a rede (`squad2_default`).

**O que ele faz, em ordem**

| Etapa | O que acontece |
|---|---|
| 1. Docker | Confere se o Docker Desktop está respondendo |
| 2. CKAN | `docker compose up -d --build` (ou build sem cache com `-Reconstruir`); espera o CKAN responder em `http://localhost:5000` (ou `127.0.0.1`), mostrando o último erro a cada 30 s; para se o `prerun` falhar; confere se a extensão `dsaudit` carregou |
| 3. Token | Reaproveita o token guardado se ainda for válido; senão gera um novo para o `admin` pelo CLI do CKAN e testa na API |
| 4. Variáveis | Define `CKAN_URL` e `CKAN_API_KEY` nesta janela e no usuário do Windows (novas janelas já abrem com elas) |
| Índice de busca | Compara os datasets do banco do CKAN (`package_list`) com os da busca (`package_search`, que é o que o produto final lê) e reconstrói o índice do Solr se faltar algum |
| `-Importar` | Copia `importar_ckan_goias.py` e `metadados_ckan_goias.json` para o container e importa os datasets do portal com os mesmos IDs e datas; mostra o resumo e a verificação final |
| `-Testar` | Roda o `teste_auditoria.ps1` com o token gerado (DataStore com antes → depois) |
| `-ProdutoFinal` | Descobre a rede Docker do CKAN (`CKAN_NETWORK`); cria `produtofinal/.env` se faltar e gera `GDA_SECRET_KEY` e `GDA_ENCRYPTION_KEY` vazias; sobe o produto final com `docker-compose.ckan-local.yml`; espera a API (`/api/v1/saude`), mostrando o estado do container e o log se ele parar; testa se a API alcança o CKAN |
| `-AdminEmail` | Cria o administrador do produto final (a senha é pedida na tela) |

Durante a execução, as chamadas HTTP ignoram o proxy do Windows (que pode interceptar `localhost`) e a saída dos containers aparece em UTF-8; as duas configurações voltam ao normal no final.

**Parâmetros**

| Parâmetro | Efeito |
|---|---|
| `-Reconstruir` | Build sem cache e recria os containers (após mudar o `Dockerfile` ou `ckanext-dsaudit-ckan29/`) |
| `-Importar` | Carga dos datasets do portal |
| `-Substituir` | Com `-Importar`: reimporta datasets da carga antiga (ID diferente do portal) |
| `-Testar` | Teste da auditoria |
| `-ProdutoFinal` | Sobe o produto final ligado ao CKAN |
| `-AdminEmail` / `-AdminNome` | Com `-ProdutoFinal`: cria o administrador do produto final |
| `-Tudo` | `-Importar -Testar -ProdutoFinal` |
| `-NaoPersistir` | Não grava as variáveis no usuário do Windows (só nesta janela) |
| `-UsuarioCkan` | Usuário do CKAN dono do token (padrão `admin`) |
| `-Url` | Endereço do CKAN (padrão `http://localhost:5000`) |
| `-TimeoutMin` | Tempo máximo de espera do CKAN e da API, em minutos (padrão 10) |

**Endereços ao final**

* CKAN: <http://127.0.0.1:5000> (`admin` / `Admin12345`, definidos no `docker-compose.yml`).
* Produto final: <http://127.0.0.1:8080> · API e documentação: <http://127.0.0.1:8000/api/v1/docs>.

**Rodar de novo é seguro:** o token é reaproveitado enquanto for válido, a importação pula o que já existe e as chaves já preenchidas no `.env` não são trocadas. O `produtofinal/.env` passa a ter chaves secretas: não faça commit dele.

**Problemas comuns**

| Sintoma | O que fazer |
|---|---|
| "o Docker nao esta respondendo" | Abrir o Docker Desktop e esperar ficar *running* |
| Para em "aguardando o CKAN responder" | Ler a linha "ultimo erro"; ver `docker compose logs ckan --tail 100` |
| Produto final com poucos datasets | O índice de busca estava incompleto; rodar o script de novo (ele reconstrói) ou `docker compose exec ckan ckan -c /srv/app/ckan.ini search-index rebuild -o` |
| `role "gda" does not exist` no `psql` | O comando foi para o banco do CKAN; usar `docker exec produtofinal-db-1 psql -U gda -d gda ...` |

Os passos abaixo são o mesmo processo, manualmente.

### 1. Clonar o repositório

```
git clone https://github.com/Joaofelipeperes/Squad2.git
cd Squad2
```

### 2. Construir e subir

```
docker compose up -d --build --force-recreate
```

`--force-recreate` é importante quando o container já existia: a lista de plugins fica gravada no `ckan.ini` **dentro** do container.

O `prerun` (substituído pela versão em `docker/prerun.py`) faz a cada start: espera o Postgres, grava `ckan.plugins`, `ckan db init`, permissões do DataStore, espera o Solr e cria o sysadmin. Acompanhe com:

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
* As versões ficam só no volume do CKAN (não há download pela interface). Para inspecionar: `docker compose exec ckan ls /var/lib/ckan/dsaudit_versions/<resource_id>/`.

Recursos que já existiam antes desta versão: a versão atual é guardada automaticamente na primeira substituição.

### Camada 2 — Conteúdo do DataStore, linha a linha (`ckanext-dsaudit` + compatibilidade 2.9)

A imagem instala [`ckanext-dsaudit`](https://github.com/ckan/ckanext-dsaudit) fixado no commit `c398842` e aplica por cima a camada enxuta da pasta [`ckanext-dsaudit-ckan29/`](ckanext-dsaudit-ckan29/README.md) (`plugins.py`, `actions.py`, `versions.py`), que só **captura e armazena** — sem telas. Ela encadeia as actions de escrita do DataStore e grava uma atividade para cada uma:

| Action | Atividade | O que fica registrado |
|---|---|---|
| `datastore_create` | `created datastore` + `changed datastore` | estrutura (colunas, tipos, chave primária) e linhas inseridas |
| `datastore_upsert` `method=insert` | `changed datastore` | linhas inseridas |
| `datastore_upsert` `method=update` / `upsert` | `changed datastore` | **para cada linha**: chave, `_id`, status (*alterada* / *nova* / *sem mudança*) e cada campo com **valor anterior → valor novo** |
| `datastore_delete` com `filters` | `deleted datastore` | filtros e o **conteúdo completo das linhas removidas** |
| `datastore_delete` sem filtros | `deleted datastore` | exclusão da tabela |

Todas com usuário e data/hora. O valor anterior é lido do banco **antes** da gravação, usando a chave única (`primary_key`) da tabela.

**Onde fica e como ler**

* Armazenamento: tabela `activity` do banco `ckan` (coluna `data` com o diff completo) e versões dos arquivos no volume `ckan_storage`.
* API (é como o produto final lê): `GET /api/3/action/dsaudit_activity_list?id=<dataset>&resource_id=<opcional>&activity_type=<opcional>&limit=&offset=` — exige permissão de edição do dataset (token de API).
* SQL: `docker compose exec db psql -U ckan -d ckan -c "SELECT timestamp, activity_type, object_id FROM activity WHERE activity_type IN ('changed metadata','changed resource file','created datastore','changed datastore','deleted datastore') ORDER BY timestamp DESC LIMIT 20;"`
* Não há telas próprias (aba Auditoria, exportação CSV e templates foram removidos na versão enxuta). No **Activity Stream** nativo os eventos aparecem com o texto genérico do CKAN.

**Garantia de não perder alterações** (padrão):

* O valor anterior é capturado para **qualquer quantidade de linhas** por chamada (leitura em blocos, paginada pelo `rows_max` do DataStore).
* O evento de auditoria é montado e validado **antes** da gravação e confirmado logo depois dela. Se a gravação falhar, o evento é descartado.
* **Modo estrito:** se não for possível capturar o "antes" (erro de leitura ou limite excedido), a chamada é **recusada** com erro `dsaudit` e **nada é alterado** no DataStore.
* `datastore_delete` guarda **todas** as linhas removidas, inclusive na exclusão da tabela inteira.

**Configuração** (variáveis no `docker-compose.yml`):

* `CKANEXT__DSAUDIT__MAX_DIFF_RECORDS` (padrão 0 = sem limite) — limite opcional de linhas por chamada. Com modo estrito, chamadas acima do limite são recusadas.
* `CKANEXT__DSAUDIT__STRICT` (padrão `true`) — recusa a alteração quando a auditoria completa não pode ser garantida. Com `false`, a alteração é aplicada e só o aviso vai para o log (comportamento antigo).
* `CKANEXT__DSAUDIT__CAPTURE_DROP` (padrão `true`) — guarda o conteúdo da tabela quando ela é excluída por inteiro.
* `CKANEXT__DSAUDIT__FILE_KEY_COLUMNS` (padrão `id`) — nomes de coluna usados como chave no diff de arquivos enviados, separados por espaço.
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

Em `GET /api/3/action/dsaudit_activity_list?id=<DATASET>` o evento `changed datastore` traz em `data.changes`: `id=1 · alterada · nome · antigo → novo valor`. O script `teste_auditoria.ps1` faz esse roteiro completo.

O token de API é gerado em *Perfil do usuário → API Tokens* (ou `docker compose exec ckan ckan -c /srv/app/ckan.ini user token add admin meu_token`).



## Importação de dados

O script `importar_ckan_goias.py` carrega os metadados de `metadados_ckan_goias.json` na instância, **preservando os IDs de dataset/recurso/organização e as datas (`created`, `last_modified`) dos recursos do portal** — o produto final (`produtofinal/`) vincula tudo pelo ID e mede atualização pelo `last_modified`. O token vem de variável de ambiente (precisa ser de um sysadmin):

```
$env:CKAN_API_KEY = "<token do admin>"        # PowerShell  (bash: export CKAN_API_KEY=...)
$env:CKAN_URL     = "http://localhost:5000"   # opcional
python importar_ckan_goias.py                 # importa o que falta e confere uma amostra no final
python importar_ckan_goias.py --substituir    # reimporta datasets carregados pela versão antiga (ID diferente)
```

`--substituir` apaga (`dataset_purge`) e recria só os datasets que existem com ID diferente do portal. Ao final o script imprime um resumo e uma verificação (`[verificação] OK`).

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