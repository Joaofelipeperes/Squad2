# Tutorial: teste de alta fidelidade da auditoria do CKAN

Passo a passo para:

1. subir o CKAN local com os datasets do portal dadosabertos.go.gov.br **e os arquivos reais**
   (não só os links);
2. aplicar alterações variadas em **100 datasets**, com usuários diferentes, cobrindo cada campo
   do dataset e do recurso, a troca de arquivo e o DataStore;
3. conferir que a extensão de auditoria (`ckanext-dsaudit`) registrou cada alteração;
4. **comprovar que um usuário só com permissão de edição na organização, sem ser administrador,
   consegue ler esses registros**, e que membros e visitantes não conseguem.

O teste não cria recursos nem datasets novos: usa somente o que veio do portal.

---

## 0. Pré-requisitos

| Item | Detalhe |
|---|---|
| Docker Desktop | Instalado e em execução ("running") |
| PowerShell | Windows PowerShell 5.1 ou PowerShell 7 |
| Pasta do projeto | Os comandos supõem `C:\Users\<usuario>\Desktop\Squad2\Squad2`. A pasta **precisa se chamar `Squad2`** (o Docker usa o nome para os volumes) |
| Internet | O container do CKAN baixa os arquivos de `dadosabertos.go.gov.br` |
| Disco | Para 130 datasets, algumas centenas de MB. Para o portal inteiro (até 20 MB por arquivo), cerca de 4 GB livres no Docker |
| Tempo | Importação de 130 datasets: 5 a 20 minutos (depende da rede). Simulação de 100 datasets: 5 a 15 minutos |

Todos os comandos abaixo são executados **na mesma janela do PowerShell**, na pasta do projeto.

---

## 1. Abrir o PowerShell na pasta do projeto

```powershell
cd $HOME\Desktop\Squad2\Squad2
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
```

O `Set-ExecutionPolicy -Scope Process` libera os scripts **só nesta janela**.

---

## 2. (Opcional) Começar do zero

Só se quiser apagar dados de execuções anteriores do CKAN (datasets, usuários, auditoria e
arquivos). **Não tem volta.**

```powershell
docker compose down -v --remove-orphans
[Environment]::SetEnvironmentVariable("CKAN_API_KEY", $null, "User")
Remove-Item Env:CKAN_API_KEY -ErrorAction SilentlyContinue
```

---

## 3. Subir o CKAN e importar os datasets com os arquivos

```powershell
.\subir_ambiente.ps1 -Reconstruir -ImportarArquivos -LimiteDatasets 130
```

| Parâmetro | Por quê |
|---|---|
| `-Reconstruir` | Refaz a imagem do CKAN com a extensão do repositório |
| `-ImportarArquivos` | Cria os datasets com os mesmos IDs do portal e **envia os arquivos reais** para o CKAN local |
| `-LimiteDatasets 130` | Importa 130 datasets. São mais de 100 porque alguns datasets do portal não têm arquivo disponível (só link ou só arquivos acima do limite) |

Para importar o portal inteiro (445 datasets), omita `-LimiteDatasets`.

**Resultado esperado** no final da etapa "Carga de alta fidelidade":

```
[verificação] OK
OK   arquivos enviados e conferidos
```

Linhas como `x ...: download falhou (HTTP 404); continua como link` são normais: o portal não
entregou aquele arquivo, e o recurso continua apontando para o portal.

Se a importação for interrompida, rode o mesmo comando de novo (sem `-Reconstruir`): ela continua
de onde parou.

---

## 4. Rodar a simulação em 100 datasets

```powershell
.\subir_ambiente.ps1 -Simular -QuantidadeSimulacao 100
```

A simulação:

* cria (ou reaproveita) quatro usuários de teste e os vincula à organização de cada dataset:

  | Usuário | Papel na organização |
  |---|---|
  | `aud-editora-ana` | editor |
  | `aud-editor-bruno` | editor |
  | `aud-admin-carla` | admin da organização |
  | `aud-membro-davi` | member (só leitura) |

* aplica em cada dataset uma combinação diferente dos cenários abaixo, com autores alternados;
* consulta a auditoria de cada dataset e confere, **campo a campo**, se cada alteração foi
  registrada com o valor anterior e o novo.

### Cenários

| Grupo | Cenário | Campo conferido na auditoria |
|---|---|---|
| Dataset | título | `title` |
| | descrição | `notes` |
| | autor | `author` |
| | e-mail do autor | `author_email` |
| | mantenedor | `maintainer` |
| | e-mail do mantenedor | `maintainer_email` |
| | licença | `license_id` |
| | versão | `version` |
| | URL da fonte | `url` |
| | inclusão e remoção de tag | `tags` |
| | alteração, inclusão e remoção de campo extra (ex.: "Atualização") | `extras.<nome>` |
| | inclusão e remoção de grupo (feito pelo sysadmin) | `groups` |
| | privado e de volta a público | `private` (2 registros) |
| | nome na URL: renomeia e volta (a cada 10 datasets) | `name` (2 registros) |
| | organização: move e volta (a cada 10 datasets, sysadmin) | `owner_org` (2 registros) |
| | exclusão e restauração (a cada 10 datasets, sysadmin) | `state` (2 registros) |
| Recurso | nome | `name` |
| | descrição | `description` |
| | **data de publicação** | `created` |
| | data de atualização | `last_modified` |
| | campo extra | `observacao_auditoria` |
| | formato: muda e volta (a cada 10 datasets) | `format` (2 registros) |
| Conteúdo | troca do arquivo CSV: 2 células alteradas, 1 linha removida e 1 incluída | `changed resource file` com diff linha a linha |
| | carga do CSV no DataStore do próprio recurso | `created datastore` + `changed datastore` |
| Acesso | membro tenta editar e ler a auditoria (a cada 5 datasets) | recusado (HTTP 403) |

A data de criação do **dataset** (`metadata_created`) é preenchida pelo próprio CKAN e não pode
ser alterada pela API; por isso a "data de publicação" testada é a do recurso.

**Resultado esperado** no final:

```
Cobertura por cenário (aplicado / pulado por não se aplicar / erro):
  titulo              36     0     0   título
  ...
  troca_arquivo       91     9     0   troca do arquivo (diff linha a linha)
  datastore           85    15     0   carga do arquivo no DataStore
  ...
Resumo: 100 dataset(s), 1333 registro(s) de auditoria, 0 problema(s)
[simulação] OK
```

(Os números variam conforme os datasets.)

| Coluna | Significado |
|---|---|
| aplicado | Quantas vezes o cenário foi executado e conferido |
| pulado | O cenário não se aplica àquele dataset (ex.: não há tag para remover, não há CSV com coluna de valores únicos, o recurso já tem DataStore de uma rodada anterior). **Não é erro** |
| erro | A API recusou a alteração. Deve ser 0 |

Qualquer linha `PROBLEMA:` indica uma alteração que não apareceu na auditoria como esperado.

### Guardar o relatório completo (opcional)

```powershell
docker compose exec -T -e CKAN_API_KEY=$env:CKAN_API_KEY -w /tmp ckan python3 simular_alteracoes.py --quantidade 100 --relatorio /tmp/relatorio.json
docker compose cp ckan:/tmp/relatorio.json .\relatorio_simulacao.json
```

O arquivo `relatorio_simulacao.json` traz, por dataset, cada cenário aplicado, o resultado e a
contagem de registros por tipo e por autor. (Use este comando depois de ter rodado o passo 4 pelo
menos uma vez: é ele que copia o script para dentro do container.)

**Atenção:** os datasets usados são alterados de verdade. Para voltar o arquivo e as datas de um
recurso ao estado do portal:

```powershell
docker compose exec -T -e CKAN_API_KEY=$env:CKAN_API_KEY -w /tmp ckan python3 importar_ckan_goias_arquivos.py --datasets <nome-do-dataset> --refazer
```

---

## 5. Conferir os resultados como administrador

### 5.1 Datasets alterados pela simulação

Todos recebem a tag `auditoria-teste`:

```powershell
(Invoke-RestMethod "http://127.0.0.1:5000/api/3/action/package_search?fq=tags:auditoria-teste&rows=200").result.count
```

### 5.2 Registros de um dataset, por tipo

A consulta `dsaudit_activity_list` é **por dataset**: devolve só os registros daquele dataset
(incluindo os dos recursos dele). Para a comprovação do passo 6 mostrar todos os tipos de
registro, o comando abaixo escolhe um dataset em que a simulação **trocou o arquivo**
(registro `changed resource file` com `method = replaced`).

Isso é necessário porque a troca de arquivo só é feita nos datasets que têm um CSV com coluna de
valores únicos (cerca de um terço dos datasets reais). Nos demais, os registros
`changed resource file` são apenas do envio inicial do arquivo na importação (`method = new`),
sem diff linha a linha.

```powershell
$lista = (Invoke-RestMethod "http://127.0.0.1:5000/api/3/action/package_search?fq=tags:auditoria-teste&rows=200").result.results.name
$ds = $null
foreach ($nome in $lista) {
    $r = Invoke-RestMethod "http://127.0.0.1:5000/api/3/action/dsaudit_activity_list?id=$nome&limit=500" -Headers @{ Authorization = $env:CKAN_API_KEY }
    if ($r.result.results | Where-Object { $PSItem.activity_type -eq 'changed resource file' -and $PSItem.data.method -eq 'replaced' }) {
        $ds = $nome; $adm = $r; break
    }
}
if (-not $ds) { Write-Host "Nenhum dataset com troca de arquivo. Veja o cenario troca_arquivo no relatorio do passo 4." -ForegroundColor Yellow }
"Dataset: $ds  -  $($adm.result.count) registros"
$adm.result.results | Group-Object activity_type | Select-Object Name, Count
```

Esperado: tipos `changed metadata` e `changed resource file`; quando o dataset também passou
pelo cenário DataStore, aparece ainda `created datastore`.

Para olhar um dataset específico, defina o nome manualmente e consulte de novo:

```powershell
$ds = "nome-do-dataset"   # troque pelo nome real, como aparece na URL do CKAN
$adm = Invoke-RestMethod "http://127.0.0.1:5000/api/3/action/dsaudit_activity_list?id=$ds&limit=500" -Headers @{ Authorization = $env:CKAN_API_KEY }
```

### 5.3 Totais no banco

```powershell
docker exec ckansquad2-db-1 psql -U ckan -d ckan -c "SELECT activity_type, count(*) FROM activity GROUP BY 1 ORDER BY 2 DESC;"
```

`changed metadata`, `changed resource file`, `created datastore` e `changed datastore` são da
extensão; `new package` e `changed package` são o histórico nativo do CKAN.

---

## 6. Comprovação: acesso aos registros com permissão mínima de edição

**O que se quer comprovar:** um usuário que é apenas **editor** da organização dona do dataset,
sem ser administrador do sistema (sysadmin), consegue ler o conteúdo completo da auditoria
(valor anterior → novo, diff linha a linha). Um **membro** da mesma organização e um **visitante**
não conseguem.

| Usuário | Papel | É sysadmin? |
|---|---|---|
| `aud-editora-ana` | editor da organização | não |
| `aud-membro-davi` | member da organização | não |
| (sem login) | visitante | não |

Os comandos usam o dataset `$ds` do passo 5.2 (um dataset com troca de arquivo). Rode o 5.2
antes, na mesma janela. Se trocar o `$ds`, repita o 5.2 e o 6.3 para atualizar `$adm` e `$ed`.

### 6.1 Confirmar que a editora não é administradora

```powershell
$ana = (Invoke-RestMethod "http://127.0.0.1:5000/api/3/action/user_show?id=aud-editora-ana" -Headers @{ Authorization = $env:CKAN_API_KEY }).result
"sysadmin: $($ana.sysadmin)"

$org = (Invoke-RestMethod "http://127.0.0.1:5000/api/3/action/package_show?id=$ds").result.owner_org
$membros = (Invoke-RestMethod "http://127.0.0.1:5000/api/3/action/member_list?id=$org&object_type=user" -Headers @{ Authorization = $env:CKAN_API_KEY }).result
foreach ($m in $membros) {
    $u = (Invoke-RestMethod "http://127.0.0.1:5000/api/3/action/user_show?id=$($m[0])" -Headers @{ Authorization = $env:CKAN_API_KEY }).result
    if ($u.name -like "aud-*") { "$($u.name): papel na organizacao = $($m[2])" }
}
```

Esperado: `sysadmin: False` e `aud-editora-ana: papel na organizacao = Editor`.

### 6.2 Gerar um token de API para a editora e para o membro

As senhas dos usuários de teste são aleatórias; o token é gerado pelo terminal do CKAN, como
administrador do servidor:

```powershell
function TokenDe($usuario) {
    $saida = docker compose exec -T ckan sh -c "ckan -c /srv/app/ckan.ini user token add $usuario comprovacao 2>/dev/null"
    [regex]::Match(($saida -join "`n"), 'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+').Value
}
$tokEditor = TokenDe "aud-editora-ana"
$tokMembro = TokenDe "aud-membro-davi"
"token da editora: $($tokEditor.Substring(0, 12))..."
"token do membro:  $($tokMembro.Substring(0, 12))..."
```

### 6.3 Consultar a auditoria com cada perfil

```powershell
function Consultar($rotulo, $token) {
    $h = @{}; if ($token) { $h.Authorization = $token }
    try {
        $resp = Invoke-RestMethod "http://127.0.0.1:5000/api/3/action/dsaudit_activity_list?id=$ds&limit=500" -Headers $h
        Write-Host "$rotulo : PERMITIDO ($($resp.result.count) registros)" -ForegroundColor Green
        $resp.result.results | Group-Object activity_type | Select-Object Name, Count | Format-Table | Out-Host
        return $resp
    } catch {
        $codigo = [int]$PSItem.Exception.Response.StatusCode
        Write-Host "$rotulo : RECUSADO (HTTP $codigo)" -ForegroundColor Yellow
    }
}
$ed = Consultar "Editora (aud-editora-ana)" $tokEditor
Consultar "Membro (aud-membro-davi)" $tokMembro | Out-Null
Consultar "Visitante (sem login)" $null | Out-Null
```

Esperado:

```
Editora (aud-editora-ana) : PERMITIDO (N registros)     <- mesmo número que o admin viu no 5.2
Membro (aud-membro-davi) : RECUSADO (HTTP 403)
Visitante (sem login) : RECUSADO (HTTP 403)
```

### 6.4 A editora vê o mesmo conteúdo que o administrador

```powershell
"administrador: $($adm.result.count) registros | editora: $($ed.result.count) registros"
```

Valor anterior → novo de campos do dataset e dos recursos, como a editora vê:

```powershell
$ed.result.results | Where-Object { $PSItem.activity_type -eq 'changed metadata' } | Select-Object -First 5 | ForEach-Object {
    $quando = $PSItem.timestamp
    foreach ($m in $PSItem.data.changes) { "$quando  [$($m.scope)] $($m.field): '$($m.old)' -> '$($m.new)'" }
}
```

Diff linha a linha da troca de arquivo, como a editora vê:

```powershell
$troca = $ed.result.results | Where-Object { $PSItem.activity_type -eq 'changed resource file' -and $PSItem.data.method -eq 'replaced' } | Select-Object -First 1
"Arquivo: $($troca.data.version.filename)  versao $($troca.data.previous_version.version) -> $($troca.data.version.version)  em $($troca.timestamp)"
foreach ($c in $troca.data.changes) {
    $chave = ($c.key.PSObject.Properties | ForEach-Object { "$($PSItem.Name)=$($PSItem.Value)" }) -join ", "
    foreach ($f in $c.fields) { "  [$chave] $($c.status): $($f.field): '$($f.old)' -> '$($f.new)'" }
}
```

Esperado: linhas `updated` com valor antigo e novo, uma `deleted` e uma `inserted`.

Se a saída vier vazia (`Arquivo:   versao  ->   em`), o `$ds` em uso não teve troca de arquivo:
os registros `changed resource file` dele são só do envio inicial (`method = new`). Rode de novo
o 5.2 e o 6.3, que escolhem um dataset com troca.

### 6.5 A editora não tem acesso de administrador

As APIs nativas de atividade do CKAN só entregam o conteúdo desses registros a sysadmins. A
editora é recusada nelas, o que confirma que o acesso dela vem só da permissão de edição:

```powershell
$id = $ed.result.results[0].id
try { Invoke-RestMethod "http://127.0.0.1:5000/api/3/action/activity_data_show?id=$id" -Headers @{ Authorization = $tokEditor } | Out-Null; "API nativa: permitido" }
catch { "API nativa (activity_data_show) para a editora: RECUSADO (HTTP $([int]$PSItem.Exception.Response.StatusCode))" }

try { Invoke-RestMethod "http://127.0.0.1:5000/api/3/action/activity_data_show?id=$id" -Headers @{ Authorization = $env:CKAN_API_KEY } | Out-Null; "API nativa para o sysadmin: PERMITIDO" }
catch { "API nativa para o sysadmin: RECUSADO" }
```

Esperado: `RECUSADO (HTTP 403)` para a editora e `PERMITIDO` para o sysadmin.

### 6.6 (Opcional) Pelo navegador, logado como editora

1. Defina uma senha para a editora (pedida na tela):
   ```powershell
   docker compose exec ckan ckan -c /srv/app/ckan.ini user setpass aud-editora-ana
   ```
2. Numa janela anônima do navegador, entre em <http://localhost:5000/user/login> como
   `aud-editora-ana`.
3. Na mesma janela, abra
   `http://localhost:5000/api/3/action/dsaudit_activity_list?id=<nome-do-dataset>`.
   O navegador usa o login da editora e mostra os registros em JSON.

### 6.7 (Opcional) Com um editor criado por vocês

```powershell
docker compose exec ckan ckan -c /srv/app/ckan.ini user add maria.editora email=maria@cge.go.gov.br password=SenhaForte123
Invoke-RestMethod -Method Post "http://127.0.0.1:5000/api/3/action/organization_member_create" `
  -Headers @{ Authorization = $env:CKAN_API_KEY } -ContentType "application/json" `
  -Body (@{ id = $org; username = "maria.editora"; role = "editor" } | ConvertTo-Json)
$tokEditor = TokenDe "maria.editora"
Consultar "Editora (maria.editora)" $tokEditor | Out-Null
```

Troque `role = "editor"` por `role = "member"` para ver a mesma consulta ser recusada.

### Resumo da comprovação

| Consulta | Sysadmin | Editor da organização | Membro | Visitante |
|---|---|---|---|---|
| `dsaudit_activity_list` (API da extensão) | permitido | **permitido, mesmo conteúdo** | recusado (403) | recusado (403) |
| `activity_data_show` (API nativa do CKAN) | permitido | recusado (403) | recusado (403) | recusado (403) |

---

## 7. Problemas comuns

| Sintoma | Causa e solução |
|---|---|
| `Not found: Dataset nao encontrado` | O nome do dataset no comando está errado (ou é o texto de exemplo `<nome-do-dataset>`). Use o `$ds` do passo 5.2 |
| `O termo '$.activity_type' não é reconhecido` | O comando foi copiado de um lugar que removeu os sublinhados (`$_`). Copie deste arquivo, que usa `$PSItem` |
| `RECUSADO (HTTP 403)` para a editora | Ela não é editora da organização do dataset escolhido. Use um dataset com a tag `auditoria-teste` (passo 5.2) ou vincule-a (passo 6.7) |
| `Nenhum dataset com recursos importados` | Rode antes o passo 3 (`-ImportarArquivos`) |
| `Cenários não aplicados nesta rodada` | Poucos datasets na simulação. Use `-QuantidadeSimulacao 30` ou mais |
| Mensagens `dsaudit: diff do arquivo ... falhou` no log do CKAN | Recursos marcados como CSV que na verdade são ZIP. O envio funciona; só não há diff linha a linha desses arquivos |
| Alteração feita por um sistema externo não aparece na auditoria | Ver as limitações conhecidas: alterações por `package_patch` e edições forçadas no DataStore de recursos de arquivo não são registradas pela extensão |
