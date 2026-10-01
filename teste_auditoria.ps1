# ---------------------------------------------------------------------------
# teste_auditoria.ps1 -- testa a auditoria linha a linha do DataStore
#
# Uso (na pasta do projeto, com os containers no ar):
#   powershell -ExecutionPolicy Bypass -File .\teste_auditoria.ps1
#
# Parametros opcionais:
#   -Org   nome de uma organizacao existente (padrao: a primeira encontrada)
#   -Token token de API de um sysadmin (padrao: gera um para o usuario admin)
#   -Url   endereco do CKAN (padrao: http://localhost:5000)
#
# O script cria um dataset "teste-auditoria-<data>" com uma tabela no
# DataStore, faz alteracoes conhecidas e depois le o que a auditoria gravou.
# ---------------------------------------------------------------------------
param(
    [string]$Org = "agencia-goiana-de-infraestrtutura-e-transportes-goinfra",
    [string]$Token = "7446a8f0-5431-4e39-a1d5-aede1a387167",
    [string]$Url = "http://localhost:5000",
    # teste de volume: upsert com N linhas (0 = nao executa)
    [int]$Linhas = 5000
)
$ErrorActionPreference = "Stop"

function Api([string]$Action, $Body) {
    $json = $Body | ConvertTo-Json -Depth 10 -Compress
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
    try {
        $r = Invoke-RestMethod -Method Post -Uri "$Url/api/3/action/$Action" `
            -Headers @{ Authorization = $Token } `
            -ContentType "application/json; charset=utf-8" -Body $bytes
    } catch {
        Write-Host "ERRO em $Action : $($_.ErrorDetails.Message)" -ForegroundColor Red
        throw
    }
    return $r.result
}

function Show($v) {
    if ($null -eq $v) { return "(vazio)" }
    return "$v"
}

# 1) token de API ------------------------------------------------------------
if (-not $Token) {
    Write-Host "Gerando token de API para o usuario admin..."
    # o CLI do CKAN escreve logs no stderr; no Windows PowerShell 5.1 isso
    # viraria erro com ErrorActionPreference=Stop
    $ErrorActionPreference = "Continue"
    $out = docker compose exec -T ckan ckan -c /srv/app/ckan.ini user token add admin teste-auditoria 2>$null
    $ErrorActionPreference = "Stop"
    $Token = ($out | Where-Object { $_.Trim() -ne "" } | Select-Object -Last 1).Trim()
    if (-not $Token) { throw "Nao foi possivel gerar o token. Passe -Token manualmente." }
}

# 2) organizacao --------------------------------------------------------------
if (-not $Org) {
    $orgs = Invoke-RestMethod -Uri "$Url/api/3/action/organization_list" -Headers @{ Authorization = $Token }
    if ($orgs.result.Count -eq 0) {
        $Org = "org-teste-auditoria"
        Api "organization_create" @{ name = $Org; title = "Org teste auditoria" } | Out-Null
    } else {
        $Org = $orgs.result[0]
    }
}
Write-Host "Organizacao: $Org"

# 3) dataset + tabela no DataStore -------------------------------------------
$ds = "teste-auditoria-" + (Get-Date -Format "yyyyMMdd-HHmmss")
Api "package_create" @{ name = $ds; title = "Teste auditoria $ds"; owner_org = $Org } | Out-Null
Write-Host "Dataset criado: $ds"

$created = Api "datastore_create" @{
    resource    = @{ package_id = $ds; name = "Tabela de teste" }
    fields      = @(
        @{ id = "id";    type = "int" },
        @{ id = "nome";  type = "text" },
        @{ id = "valor"; type = "numeric" }
    )
    primary_key = @("id")
    records     = @(
        @{ id = 1; nome = "a"; valor = 10 },
        @{ id = 2; nome = "b"; valor = 20 },
        @{ id = 3; nome = "c"; valor = 30 }
    )
}
$rid = $created.resource_id
Write-Host "Recurso DataStore criado: $rid (3 linhas)"

# 4) alteracoes conhecidas ----------------------------------------------------
Api "datastore_upsert" @{ resource_id = $rid; method = "update"
    records = @( @{ id = 2; valor = 25 } ) } | Out-Null
Write-Host "UPDATE : id=2 valor 20 -> 25"

Api "datastore_upsert" @{ resource_id = $rid; method = "upsert"
    records = @( @{ id = 3; nome = "C"; valor = 30 }, @{ id = 4; nome = "d"; valor = 40 } ) } | Out-Null
Write-Host "UPSERT : id=3 nome c -> C ; id=4 nova linha"

Api "datastore_delete" @{ resource_id = $rid; filters = @{ id = 1 } } | Out-Null
Write-Host "DELETE : id=1"

# 4b) teste de volume: N linhas inseridas e depois TODAS alteradas -----------
if ($Linhas -gt 0) {
    $ini = 1000
    $base = @(); for ($i = 1; $i -le $Linhas; $i++) { $base += @{ id = $ini + $i; nome = "v$i"; valor = $i } }
    Api "datastore_upsert" @{ resource_id = $rid; method = "insert"; records = $base } | Out-Null
    $alt = @(); for ($i = 1; $i -le $Linhas; $i++) { $alt += @{ id = $ini + $i; valor = $i * 10 } }
    Api "datastore_upsert" @{ resource_id = $rid; method = "update"; records = $alt } | Out-Null
    Write-Host "VOLUME : $Linhas linhas alteradas em uma unica chamada (valor x10)"
}

# 4c) arquivo enviado (upload, como pela interface) e substituicao ------------
# usa curl.exe (Windows 10+) para o envio multipart
function Upload([string]$Action, [hashtable]$Fields, [string]$File) {
    $cargs = @("-s", "-X", "POST", "$Url/api/3/action/$Action", "-H", "Authorization: $Token")
    foreach ($k in $Fields.Keys) { $cargs += @("-F", "$k=$($Fields[$k])") }
    $cargs += @("-F", "upload=@$File")
    $r = (& curl.exe @cargs) | ConvertFrom-Json
    if (-not $r.success) { throw "ERRO em $Action : $($r.error | ConvertTo-Json -Compress)" }
    return $r.result
}
$tmp1 = Join-Path $env:TEMP "dados_v1.csv"; $tmp2 = Join-Path $env:TEMP "dados_v2.csv"
[IO.File]::WriteAllText($tmp1, "id;nome;valor`n1;Ana;10`n2;Bruno;20`n3;Carla;30`n")
[IO.File]::WriteAllText($tmp2, "id;nome;valor`n1;Ana;10`n2;Bruno;25`n4;Davi;40`n")
$fres = Upload "resource_create" @{ package_id = $ds; name = "Arquivo CSV" } $tmp1
Write-Host "UPLOAD : arquivo CSV com 3 linhas (recurso $($fres.id))"
Upload "resource_update" @{ id = $fres.id; name = "Arquivo CSV" } $tmp2 | Out-Null
Write-Host "TROCA  : arquivo substituido (id=2 valor 20->25 ; id=3 removida ; id=4 nova)"

# 4d) metadados do dataset (autor / e-mail) ----------------------------------
Api "package_patch" @{ id = $ds; author = "Fulano de Tal"; author_email = "fulano@exemplo.gov.br" } | Out-Null
Write-Host "META   : author e author_email alterados"

# 5) le a auditoria -----------------------------------------------------------
Write-Host ""
Write-Host "==== O que a auditoria gravou ====" -ForegroundColor Cyan
$audit = Invoke-RestMethod -Uri "$Url/api/3/action/dsaudit_activity_list?id=$ds&limit=50" `
    -Headers @{ Authorization = $Token }
$events = @($audit.result.results)
[array]::Reverse($events)
foreach ($a in $events) {
    $d = $a.data
    Write-Host ""
    Write-Host ("[{0} UTC] {1} {2}" -f $a.timestamp, $a.activity_type, $d.method) -ForegroundColor Yellow
    if ($a.activity_type -eq "changed metadata") {
        foreach ($c in $d.changes) {
            $onde = if ($c.scope -eq "dataset") { "dataset" } else { "recurso '$($c.resource_name)'" }
            Write-Host ("   {0} {1}: {2} -> {3}" -f $onde, $c.field, (Show $c.old), (Show $c.new))
        }
        continue
    }
    if ($a.activity_type -eq "changed resource file") {
        $pv = if ($d.previous_version) { "v$($d.previous_version.version)" } else { "-" }
        Write-Host ("   arquivo {0}: {1} -> v{2}" -f $d.version.filename, $pv, $d.version.version)
        if ($d.diff_error) { Write-Host "   aviso: $($d.diff_error)" }
    }
    if ($d.changes -and $d.changes.Count -gt 20) {
        $comAntes = @($d.changes | Where-Object { $_.status -eq "updated" -and $_.fields.Count -gt 0 -and $null -ne $_.fields[0].old }).Count
        $cor = if ($comAntes -eq $d.changes.Count) { "Green" } else { "Red" }
        Write-Host ("   {0} linhas enviadas; {1} com valor anterior -> novo registrado" -f $d.changes.Count, $comAntes) -ForegroundColor $cor
        $f = $d.changes[-1].fields[0]
        Write-Host ("   ex.: ultima linha {0}: {1} -> {2}" -f $f.field, $f.old, $f.new)
    } elseif ($d.changes) {
        foreach ($c in $d.changes) {
            $key = ($c.key.PSObject.Properties | ForEach-Object { "$($_.Name)=$($_.Value)" }) -join ", "
            if (-not $c.fields -or $c.fields.Count -eq 0) {
                Write-Host "   linha [$key] $($c.status) (nenhum campo mudou)"
            }
            foreach ($f in $c.fields) {
                Write-Host ("   linha [{0}] {1,-9} {2}: {3} -> {4}" -f $key, $c.status, $f.field, (Show $f.old), (Show $f.new))
            }
        }
    } elseif ($d.records -and $d.records.Count -gt 20) {
        Write-Host ("   {0} linhas registradas" -f $d.records.Count)
    } elseif ($d.records) {
        foreach ($r in $d.records) {
            $row = ($r.PSObject.Properties | ForEach-Object { "$($_.Name)=$($_.Value)" }) -join ", "
            if ($a.activity_type -eq "deleted datastore") { Write-Host "   removida: $row" }
            else { Write-Host "   enviada : $row" }
        }
    } elseif ($d.fields) {
        Write-Host ("   colunas: " + (($d.fields | ForEach-Object { "$($_.id) ($($_.type))" }) -join ", "))
    }
}

Write-Host ""
Write-Host ("Total de eventos: {0}" -f $audit.result.count)
Write-Host "Veja no navegador (logado como admin): $Url/dataset/$ds/auditoria" -ForegroundColor Green
Write-Host "CSV: $Url/dataset/$ds/auditoria.csv"
