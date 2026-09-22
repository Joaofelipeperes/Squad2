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
    [string]$Token = "a4a52af9-1b74-4ceb-80be-11a5f9d08789",
    [string]$Url = "http://localhost:5000"
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
    if ($d.changes) {
        foreach ($c in $d.changes) {
            $key = ($c.key.PSObject.Properties | ForEach-Object { "$($_.Name)=$($_.Value)" }) -join ", "
            if (-not $c.fields -or $c.fields.Count -eq 0) {
                Write-Host "   linha [$key] $($c.status) (nenhum campo mudou)"
            }
            foreach ($f in $c.fields) {
                Write-Host ("   linha [{0}] {1,-9} {2}: {3} -> {4}" -f $key, $c.status, $f.field, (Show $f.old), (Show $f.new))
            }
        }
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
