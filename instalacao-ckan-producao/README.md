# Instalação da extensão de auditoria `ckanext-dsaudit` no CKAN 2.9

Guia para a equipe que administra o CKAN. Esta pasta tem tudo o que é necessário para instalar a
extensão, inclusive num servidor sem acesso à internet.

## 1. O que a extensão faz

Registra, na tabela `activity` do próprio CKAN, **o que mudou, quando e por quem**, com o valor
anterior e o novo:

| Tipo de registro (`activity_type`) | Quando é gerado | O que fica guardado |
|---|---|---|
| `created datastore` | criação de uma tabela no DataStore | estrutura (colunas, tipos, chave) |
| `changed datastore` | inclusão/alteração de linhas no DataStore | linhas enviadas e, em `update`/`upsert`, cada campo alterado (antes → depois) |
| `deleted datastore` | exclusão de linhas ou da tabela no DataStore | todas as linhas removidas |
| `changed metadata` | criação, edição ou exclusão de dataset | campos do dataset e dos recursos alterados (antes → depois), inclusive em datasets privados |
| `changed resource file` | envio ou troca de arquivo de um recurso | versão nova e anterior (nome, tamanho, sha256) e diff linha a linha de CSV/TSV/TXT/XLSX |

Cada versão de arquivo enviado também é guardada em disco, em `<ckan.storage_path>/dsaudit_versions/`.

A extensão **não tem telas**. Os registros são consultados pela API `dsaudit_activity_list`
(seção 7). No histórico nativo do CKAN ("Activity Stream") os eventos aparecem com o modelo
genérico.

## 2. Conteúdo desta pasta

| Item | Para que serve |
|---|---|
| `README.md` | Este guia |
| `ckanext-dsaudit/` | Código-fonte completo da extensão (pacote Python instalável) |
| `pacotes/` | Dependências para instalação sem internet: `openpyxl` 3.0.10 e `et_xmlfile` 1.1.0 |
| `ckan.ini.exemplo` | Trecho de configuração a acrescentar no `ckan.ini` |
| `verificar_instalacao.sh` | Verificação pós-instalação (só faz leituras) |

## 3. Requisitos

* **CKAN 2.9.x em Python 3.** A extensão foi adaptada para o 2.9 e **não funciona no 2.10 ou
  superior**.
* Plugin **`datastore`** ativo.
* **Activity stream** habilitado (`ckan.activity_streams_enabled = true`, padrão do 2.9).
* `pip` e `setuptools` no ambiente virtual do CKAN (já fazem parte de uma instalação padrão).
* Permissão de escrita do usuário que executa o CKAN em `ckan.storage_path` (ou no diretório
  definido em `ckanext.dsaudit.versions_path`).
* **Não há migração de banco.** A extensão não cria tabelas, só grava na tabela `activity`.

## 4. Antes de instalar

1. **Instale primeiro num ambiente de homologação**, de preferência com uma cópia dos dados de
   produção, e repita lá as cargas que costumam ser feitas no DataStore.
2. Faça **backup** do banco do CKAN e do `ckan.ini`.
3. Leia a seção 8 (impactos na operação), principalmente sobre o modo estrito e o crescimento dos
   dados.

## 5. Instalação

Os comandos usam os caminhos de uma instalação "from source" padrão do CKAN 2.9
(`/usr/lib/ckan/default` e `/etc/ckan/default/ckan.ini`). Ajuste-os ao ambiente de vocês.

### 5.1 Copiar a pasta para o servidor

```bash
# exemplo: pasta copiada para /opt/instalacao-ckan-producao
cd /opt/instalacao-ckan-producao
```

### 5.2 Instalar o pacote no ambiente virtual do CKAN

```bash
. /usr/lib/ckan/default/bin/activate

# servidor COM acesso à internet:
pip install ./ckanext-dsaudit

# servidor SEM acesso à internet (usa as dependências da pasta pacotes/):
pip install --no-index --find-links ./pacotes --no-build-isolation ./ckanext-dsaudit
```

Confira:

```bash
pip show ckanext-dsaudit openpyxl
python -c "import ckanext.dsaudit.plugins; print('ok')"
```

### 5.3 Configurar o `ckan.ini`

Acrescente as linhas de `ckan.ini.exemplo` na seção `[app:main]` do `ckan.ini`. O essencial é
incluir **`dsaudit`** em `ckan.plugins`, **depois de `datastore`**, mantendo os plugins que já
estão em uso:

```ini
ckan.plugins = ... datastore dsaudit ...
```

Se a configuração do CKAN é feita por variáveis de ambiente (plugin `envvars`, comum em Docker),
use os nomes da coluna "Variável de ambiente" da seção 6.

### 5.4 Diretório das versões de arquivos

```bash
# padrão: <ckan.storage_path>/dsaudit_versions (a extensão cria a pasta se tiver permissão)
sudo -u www-data mkdir -p /var/lib/ckan/default/dsaudit_versions   # ajuste usuário e caminho
```

### 5.5 Reiniciar o CKAN

Use o procedimento já adotado no servidor, por exemplo:

```bash
sudo supervisorctl restart ckan-uwsgi:*      # ou
sudo systemctl restart ckan                  # ou o serviço equivalente
```

### 5.6 Instalação em Docker

Copie a pasta `ckanext-dsaudit/` para o contexto de build da imagem e acrescente no `Dockerfile`:

```dockerfile
COPY ckanext-dsaudit/ /srv/app/src/ckanext-dsaudit/
RUN pip3 install --no-cache-dir -e /srv/app/src/ckanext-dsaudit
```

Depois inclua `dsaudit` em `CKAN__PLUGINS` e configure as variáveis da seção 6.

## 6. Configuração

| `ckan.ini` | Variável de ambiente | Padrão | Efeito |
|---|---|---|---|
| `ckanext.dsaudit.strict` | `CKANEXT__DSAUDIT__STRICT` | `true` | Recusa a alteração quando a auditoria completa não pode ser gravada (seção 8) |
| `ckanext.dsaudit.max_diff_records` | `CKANEXT__DSAUDIT__MAX_DIFF_RECORDS` | `0` (sem limite) | Limite de linhas cujo valor anterior é capturado por chamada |
| `ckanext.dsaudit.capture_drop` | `CKANEXT__DSAUDIT__CAPTURE_DROP` | `true` | Guarda o conteúdo inteiro da tabela quando ela é excluída |
| `ckanext.dsaudit.file_key_columns` | `CKANEXT__DSAUDIT__FILE_KEY_COLUMNS` | `id` | Colunas-chave candidatas (separadas por espaço) para comparar versões de arquivos; usa a primeira com valores únicos e, sem nenhuma, compara por posição |
| `ckanext.dsaudit.versions_path` | `CKANEXT__DSAUDIT__VERSIONS_PATH` | `<ckan.storage_path>/dsaudit_versions` | Onde guardar as versões dos arquivos enviados |

Por recurso, o campo extra `chave_auditoria` (ex.: `codigo` ou `ano,municipio`) tem prioridade
sobre `file_key_columns`.

## 7. Verificação

### 7.1 Script

```bash
chmod +x verificar_instalacao.sh
CKAN_URL=https://endereco-do-ckan \
CKAN_API_KEY=<token de um usuário que edita o dataset> \
./verificar_instalacao.sh <nome-ou-id-de-um-dataset>
```

O script confere a versão do CKAN, se os plugins `dsaudit` e `datastore` estão carregados e se a
API da extensão responde. Ele **não altera nada**.

### 7.2 Teste funcional (em homologação)

1. Edite um campo de um dataset (ex.: a descrição) pela interface.
2. Consulte a API e confira que há um registro `changed metadata` com o valor anterior e o novo:

```bash
curl -H "Authorization: <token>" \
  "https://endereco-do-ckan/api/3/action/dsaudit_activity_list?id=<dataset>&limit=5"
```

### 7.3 API de consulta

```
GET /api/3/action/dsaudit_activity_list
    id             nome ou id do dataset (obrigatório)
    resource_id    restringe a um recurso (opcional)
    activity_type  um dos tipos da seção 1 (opcional)
    limit          padrão 50, máximo 500
    offset         padrão 0
```

Só responde para quem tem permissão de **editar** o dataset.

## 8. Impactos na operação

* **Modo estrito (`strict = true`).** Se a auditoria completa não puder ser gravada (falha ao ler
  o valor anterior, limite excedido, erro de disco), a alteração é **recusada** e nada muda. Quem
  fez a chamada recebe um erro de validação com a chave `dsaudit`. Com `strict = false` a
  alteração é aplicada mesmo sem auditoria completa, e o problema fica registrado no log.
* **Volume de dados.** Com `max_diff_records = 0` e `capture_drop = true`, cada carga ou exclusão
  grande grava todas as linhas na tabela `activity`, e cada arquivo enviado fica guardado em
  `dsaudit_versions`. Acompanhe o tamanho do banco e do diretório e inclua os dois no backup.
* **Tempo de resposta.** Em `update`/`upsert` e exclusões, as linhas afetadas são lidas antes da
  gravação. Cargas grandes ficam mais lentas e podem precisar de um tempo limite maior no servidor
  de aplicação (ex.: `harakiri` do uWSGI, `timeout` do Gunicorn, `proxy_read_timeout` do Nginx).
  Se o processo for interrompido no meio, a alteração é desfeita e não é registrada.
* **Logs.** As mensagens da extensão começam com `dsaudit:`.

## 9. Limitações conhecidas

* Funciona só no CKAN **2.9.x**. Uma migração para o 2.10 ou superior exigirá adaptar a extensão.
* Não passam pela extensão, e por isso ficam só no histórico nativo sem antes → depois: as ações
  em massa da página da organização (`bulk_update_private`, `bulk_update_public`,
  `bulk_update_delete`) e o `dataset_purge`.
* Sem interface própria: a consulta é pela API (seção 7.3) ou por SQL na tabela `activity`.
* O CKAN 2.9 é uma versão antiga (já existem as séries 2.10, 2.11 e 2.12). Confirmem na
  [política de versões suportadas do CKAN](https://ckan.org/blog/new-supported-versions-policy-going-forward)
  se ela ainda recebe correções de segurança.

## 10. Desativar ou remover

1. Retire `dsaudit` de `ckan.plugins` e reinicie o CKAN. O CKAN volta ao comportamento padrão.
2. Opcional: `pip uninstall ckanext-dsaudit`.

Os registros já gravados continuam na tabela `activity` e as versões de arquivos continuam em
`dsaudit_versions`. Nada é apagado.

## 11. Licença

A extensão é uma versão modificada de [`ckan/ckanext-dsaudit`](https://github.com/ckan/ckanext-dsaudit)
(commit `c3988427821c43e5dac5078c6adc42f7f16d3fa4`), do Governo do Canadá, distribuída sob a
**licença MIT**. Ela permite usar, modificar e redistribuir o código, inclusive em produção, desde
que o aviso de copyright e o texto da licença sejam mantidos. Por isso, **não remova os arquivos
`COPYING` e `COPYING.fr`** de `ckanext-dsaudit/`. A licença não autoriza o uso das marcas do
Governo do Canadá, e o software é fornecido sem garantia.

As dependências incluídas em `pacotes/` (`openpyxl` e `et_xmlfile`) também são distribuídas sob a
licença MIT.

O detalhamento técnico das alterações em relação ao original está em
`ckanext-dsaudit/README-CKAN29.md`.
