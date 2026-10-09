# ---------------------------------------------------------------------------
# subir_ambiente.ps1 -- sobe o CKAN (Docker), gera o token de API do admin e
# deixa tudo pronto em variaveis de ambiente. Opcionalmente: carrega os
# datasets do portal, roda o teste de auditoria e sobe o produto final.
#
# Uso (PowerShell, na pasta do repositorio):
#   Set-ExecutionPolicy -Scope Process Bypass        # libera scripts SO nesta janela
#   .\subir_ambiente.ps1                             # CKAN + token
#   .\subir_ambiente.ps1 -Importar -Testar           # + 445 datasets + teste de auditoria
#   .\subir_ambiente.ps1 -ProdutoFinal -AdminEmail voce@cge.go.gov.br
#   .\subir_ambiente.ps1 -Tudo -AdminEmail voce@cge.go.gov.br
#
# Rodado como .\subir_ambiente.ps1, as variaveis ficam valendo nesta janela.
# Elas tambem sao gravadas para o seu usuario do Windows (novas janelas ja
# abrem com elas); use -NaoPersistir para nao gravar.
#
# Variaveis definidas:
#   CKAN_URL       endereco do CKAN (http://localhost:5000)
#   CKAN_API_KEY   token de API do sysadmin (usado pelo importar_ckan_goias.py
#                  e pelo teste_auditoria.ps1)
#   CKAN_NETWORK   rede Docker do CKAN (usada pelo produto final, com -ProdutoFinal)
#
# Parametros:
#   -Reconstruir   build sem cache e recria os containers (apos mudar Dockerfile
#                  ou a pasta ckanext-dsaudit-ckan29)
#   -Importar      carrega metadados_ckan_goias.json no CKAN (dentro do container,
#                  nao precisa de Python na maquina)
#   -Substituir    junto com -Importar: reimporta datasets da carga antiga (ID errado)
#   -Testar        roda o teste_auditoria.ps1 com o token gerado
#   -ProdutoFinal  sobe produtofinal/ ligado a rede do CKAN, preenchendo as chaves
#                  do produtofinal/.env que estiverem vazias
#   -AdminEmail    junto com -ProdutoFinal: cria o administrador do produto final
#                  (a senha e pedida na tela)
#   -Tudo          = -Importar -Testar -ProdutoFinal
# ---------------------------------------------------------------------------
param(
    [switch]$Reconstruir,
    [switch]$Importar,
    [switch]$Substituir,
    [switch]$Testar,
    [switch]$ProdutoFinal,
    [switch]$Tudo,
    [string]$AdminEmail = "",
    [string]$AdminNome = "Administrador",
    [string]$UsuarioCkan = "admin",
    [string]$Url = "http://localhost:5000",
    [int]$TimeoutMin = 10,
    [switch]$NaoPersistir
)
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

# Chamadas HTTP ao CKAN/produto final SEM o proxy do Windows: em redes
# corporativas o proxy do sistema costuma interceptar "localhost" e a chamada
# nunca responde, embora o navegador abra a pagina. Restaurado ao final.
$ProxyOriginal = [System.Net.WebRequest]::DefaultWebProxy
[System.Net.WebRequest]::DefaultWebProxy = $null
$PSDefaultParameterValues = @{ "Invoke-RestMethod:UseBasicParsing" = $true }
if ($PSVersionTable.PSVersion.Major -ge 6) { $PSDefaultParameterValues["Invoke-RestMethod:NoProxy"] = $true }
# Saida dos containers em UTF-8 (sem isso, acentos aparecem embaralhados no console)
$EncodingOriginal = [Console]::OutputEncoding
try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false } catch { }
function RestaurarProxy {
    [System.Net.WebRequest]::DefaultWebProxy = $ProxyOriginal
    try { [Console]::OutputEncoding = $EncodingOriginal } catch { }
}
if ($Tudo) { $Importar = $true; $Testar = $true; $ProdutoFinal = $true }

$ContainerCkan = "ckansquad2-ckan-1"
$HostApi = "localhost"

function Etapa([string]$t) { Write-Host ""; Write-Host "==> $t" -ForegroundColor Cyan }
function Ok([string]$t)    { Write-Host "    OK   $t" -ForegroundColor Green }
function Aviso([string]$t) { Write-Host "    !!   $t" -ForegroundColor Yellow }
function Falha([string]$t) { Write-Host "    ERRO $t" -ForegroundColor Red; RestaurarProxy; exit 1 }

# Executa um comando externo (docker) sem que as mensagens de progresso do
# stderr virem erro no Windows PowerShell 5.1; falha se o codigo de saida != 0.
function Nativo([string]$Descricao, [scriptblock]$Comando) {
    $eap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try { & $Comando } finally { $ErrorActionPreference = $eap }
    if ($LASTEXITCODE -ne 0) { Falha "$Descricao (codigo de saida $LASTEXITCODE)" }
}

# Executa e devolve a saida (stdout) como texto, sem falhar.
function Saida([scriptblock]$Comando) {
    $eap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try { $o = & $Comando 2>$null } finally { $ErrorActionPreference = $eap }
    return (($o | ForEach-Object { "$_" }) -join "`n")
}

function TokenValido([string]$t) {
    if (-not $t) { return $false }
    try {
        $body = @{ user = $UsuarioCkan } | ConvertTo-Json -Compress
        $r = Invoke-RestMethod -Method Post -Uri "$Url/api/3/action/api_token_list" `
            -Headers @{ Authorization = $t } -ContentType "application/json" `
            -Body $body -TimeoutSec 15
        return [bool]$r.success
    } catch { return $false }
}

function ChaveAleatoria([int]$bytes) {
    $b = New-Object byte[] $bytes
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
    # base64 "url-safe" (formato exigido pela chave Fernet do produto final)
    return [Convert]::ToBase64String($b).Replace("+", "-").Replace("/", "_")
}

function DefinirVariavel([string]$Nome, [string]$Valor) {
    Set-Item -Path "Env:$Nome" -Value $Valor
    if (-not $NaoPersistir) {
        [Environment]::SetEnvironmentVariable($Nome, $Valor, "User")
    }
}

# O produto final le o CKAN pelo package_search (indice Solr). Se o indice estiver
# incompleto (Solr recriado, carga antiga), os datasets existem no banco do CKAN
# mas nao aparecem na coleta. Compara package_list (banco) com package_search
# (indice) e reconstroi so o que falta.
function ConferirIndice {
    try {
        $noBanco = @((Invoke-RestMethod -Uri "$Url/api/3/action/package_list" -TimeoutSec 120).result).Count
        $noIndice = [int](Invoke-RestMethod -Uri "$Url/api/3/action/package_search?rows=0" -TimeoutSec 60).result.count
    } catch { Aviso "nao foi possivel conferir o indice de busca: $($_.Exception.Message)"; return }
    if ($noIndice -ge $noBanco) { Ok "indice de busca completo ($noIndice de $noBanco datasets publicos)"; return }
    Aviso "indice de busca incompleto: $noIndice de $noBanco datasets; reconstruindo o que falta (pode levar alguns minutos)..."
    Nativo "reconstrucao do indice" { docker compose exec -T ckan sh -c "ckan -c /srv/app/ckan.ini search-index rebuild -o 2>&1 | tail -3" }
    $noIndice = [int](Invoke-RestMethod -Uri "$Url/api/3/action/package_search?rows=0" -TimeoutSec 60).result.count
    if ($noIndice -ge $noBanco) { Ok "indice reconstruido ($noIndice de $noBanco datasets)" }
    else { Aviso "o indice continua incompleto ($noIndice de $noBanco). Rode: docker compose exec ckan ckan -c /srv/app/ckan.ini search-index rebuild" }
}

# ---------------------------------------------------------------------------
Etapa "1/4 Verificando o Docker"
$versao = Saida { docker info --format "{{.ServerVersion}}" }
if (-not $versao -or $LASTEXITCODE -ne 0) {
    Falha "o Docker nao esta respondendo. Abra o Docker Desktop, espere ficar 'running' e rode de novo."
}
Ok "Docker $versao"

# ---------------------------------------------------------------------------
Etapa "2/4 Subindo o CKAN (db, solr, redis, ckan)"
if ($Reconstruir) {
    Nativo "build do CKAN" { docker compose build --no-cache ckan }
    Nativo "subida dos containers" { docker compose up -d --force-recreate }
} else {
    Nativo "subida dos containers" { docker compose up -d --build }
}
Ok "containers iniciados"

if ($Url -like "https://*") {
    Aviso "o CKAN local responde em http, nao https; usando $($Url -replace '^https://', 'http://')"
    $Url = $Url -replace '^https://', 'http://'
}
Write-Host "    aguardando o CKAN responder em $Url (ate $TimeoutMin min)..."
# tenta tambem 127.0.0.1 (quando "localhost" resolve para IPv6 e a porta so
# esta publicada em IPv4, ou vice-versa)
$candidatos = @($Url)
if ($Url -match "//localhost") { $candidatos += ($Url -replace "//localhost", "//127.0.0.1") }
$limite = (Get-Date).AddMinutes($TimeoutMin)
$status = $null
$ultimoErro = ""
$proximoAviso = (Get-Date).AddSeconds(30)
while ((Get-Date) -lt $limite) {
    foreach ($c in $candidatos) {
        try {
            $status = (Invoke-RestMethod -Uri "$c/api/3/action/status_show" -TimeoutSec 15).result
            if ($c -ne $Url) { Aviso "o CKAN respondeu em $c (e nao em $Url); usando $c"; $Url = $c }
            break
        } catch { $ultimoErro = $_.Exception.Message }
    }
    if ($status) { break }
    if ((Get-Date) -gt $proximoAviso) {
        Write-Host "    ainda aguardando... ultimo erro: $ultimoErro" -ForegroundColor DarkYellow
        $proximoAviso = (Get-Date).AddSeconds(30)
    }
    $erroPrerun = (Saida { docker compose logs ckan --tail 300 }) -split "`n" |
        Select-String -Pattern "\[prerun\] ERRO" | Select-Object -Last 3
    if ($erroPrerun) {
        $erroPrerun | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
        Falha "o prerun do CKAN falhou (veja: docker compose logs ckan --tail 100)"
    }
    Start-Sleep -Seconds 5
}
if (-not $status) {
    Falha "o CKAN nao respondeu em $TimeoutMin min. Ultimo erro: $ultimoErro (veja tambem: docker compose logs ckan --tail 100)"
}
Ok "CKAN $($status.ckan_version) no ar"
if ($status.extensions -contains "dsaudit") { Ok "extensao dsaudit carregada" }
else { Aviso "a extensao dsaudit NAO aparece em status_show: $($status.extensions -join ', ')" }

# ---------------------------------------------------------------------------
Etapa "3/4 Token de API do usuario '$UsuarioCkan'"
$token = $env:CKAN_API_KEY
if (-not $token) { $token = [Environment]::GetEnvironmentVariable("CKAN_API_KEY", "User") }
if (TokenValido $token) {
    Ok "token ja existente e valido, reaproveitado"
} else {
    if ($token) { Aviso "o token guardado nao vale mais (CKAN recriado?); gerando outro" }
    $nomeToken = "ambiente-" + (Get-Date -Format "yyyyMMdd-HHmmss")
    # os logs do CLI do CKAN vao para o stderr: descartados dentro do container
    $saida = Saida { docker compose exec -T ckan sh -c "ckan -c /srv/app/ckan.ini user token add $UsuarioCkan $nomeToken 2>/dev/null" }
    $m = [regex]::Match($saida, "eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")
    if (-not $m.Success) {
        Write-Host $saida
        Falha "nao foi possivel gerar o token (o usuario '$UsuarioCkan' existe? veja CKAN_SYSADMIN_NAME no docker-compose.yml)"
    }
    $token = $m.Value
    if (-not (TokenValido $token)) { Falha "o token foi gerado mas a API o recusou" }
    Ok "token '$nomeToken' gerado"
}

# ---------------------------------------------------------------------------
Etapa "4/4 Variaveis de ambiente"
DefinirVariavel "CKAN_URL" $Url
DefinirVariavel "CKAN_API_KEY" $token
$onde = "nesta janela"
if (-not $NaoPersistir) { $onde = "nesta janela e para o seu usuario do Windows (novas janelas)" }
Ok "CKAN_URL e CKAN_API_KEY definidas $onde"

Etapa "Indice de busca do CKAN"
ConferirIndice

# ---------------------------------------------------------------------------
if ($Importar) {
    Etapa "Carga dos datasets do portal (importar_ckan_goias.py)"
    Nativo "copia do importador" { docker compose cp importar_ckan_goias.py ckan:/tmp/importar_ckan_goias.py }
    Nativo "copia dos metadados" { docker compose cp metadados_ckan_goias.json ckan:/tmp/metadados_ckan_goias.json }
    $argsImp = @("compose", "exec", "-T", "-e", "CKAN_API_KEY=$token", "-e", "CKAN_URL=http://localhost:5000",
                 "-w", "/tmp", "ckan", "python3", "importar_ckan_goias.py")
    if ($Substituir) { $argsImp += "--substituir" }
    Write-Host "    importando (pode levar alguns minutos)..."
    $eap = $ErrorActionPreference; $ErrorActionPreference = "Continue"
    try { $log = & docker @argsImp 2>&1 | ForEach-Object { "$_" } } finally { $ErrorActionPreference = $eap }
    $log | Where-Object { $_ -notmatch "^Processando dataset|^  -> (Sucesso|J.{1,3} existe)" } |
        ForEach-Object { Write-Host "    $_" }
    $textoLog = $log -join "`n"
    if ($textoLog -match "\[verifica.{1,4}o\] OK") { Ok "carga conferida" }
    else { Aviso "a verificacao final da carga nao deu OK (veja as mensagens acima)" }
    if (-not $Substituir -and $textoLog -match '"id_divergente": [1-9]') {
        Aviso "ha datasets da carga antiga com ID errado: rode de novo com -Importar -Substituir"
    }
    ConferirIndice
}

# ---------------------------------------------------------------------------
if ($Testar) {
    Etapa "Teste da auditoria (teste_auditoria.ps1)"
    & "$PSScriptRoot\teste_auditoria.ps1" -Token $token -Url $Url
}

# ---------------------------------------------------------------------------
if ($ProdutoFinal) {
    Etapa "Produto final ligado ao CKAN"

    $redes = Saida { docker inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}' $ContainerCkan }
    $rede = ($redes.Trim() -split "\s+")[0]
    if (-not $rede) { Falha "nao foi possivel descobrir a rede do container $ContainerCkan" }
    DefinirVariavel "CKAN_NETWORK" $rede
    Ok "rede do CKAN: $rede"

    $pf = Join-Path $PSScriptRoot "produtofinal"
    $envPath = Join-Path $pf ".env"
    if (-not (Test-Path $envPath)) {
        Copy-Item (Join-Path $pf ".env.example") $envPath
        Ok "produtofinal\.env criado a partir do .env.example"
    }
    $linhas = [System.IO.File]::ReadAllLines($envPath)
    $mudou = $false
    for ($i = 0; $i -lt $linhas.Length; $i++) {
        if ($linhas[$i] -match "^GDA_SECRET_KEY=(.*)$") {
            $v = $Matches[1].Trim()
            if (-not $v -or $v -like "troque*") {
                $linhas[$i] = "GDA_SECRET_KEY=" + (ChaveAleatoria 48); $mudou = $true
                Ok "GDA_SECRET_KEY gerada"
            }
        } elseif ($linhas[$i] -match "^GDA_ENCRYPTION_KEY=\s*$") {
            $linhas[$i] = "GDA_ENCRYPTION_KEY=" + (ChaveAleatoria 32); $mudou = $true
            Ok "GDA_ENCRYPTION_KEY gerada"
        }
    }
    if ($mudou) {
        # UTF-8 sem BOM (o BOM estragaria a primeira variavel do arquivo)
        [System.IO.File]::WriteAllLines($envPath, $linhas, (New-Object System.Text.UTF8Encoding $false))
        Aviso "produtofinal\.env tem chaves secretas: nao faca commit dele"
    }

    Push-Location $pf
    try {
        Nativo "subida do produto final" { docker compose -f docker-compose.yml -f docker-compose.ckan-local.yml up -d --build }
        # mesmo host em que o CKAN respondeu (localhost ou 127.0.0.1), e o outro como reserva
        $hostOk = ([Uri]$Url).Host
        $hostsApi = @($hostOk, "127.0.0.1", "localhost") | Select-Object -Unique
        Write-Host "    aguardando a API do produto final (http://${hostOk}:8000, ate $TimeoutMin min)..."
        $limite = (Get-Date).AddMinutes($TimeoutMin)
        $saude = $false
        $ultimoErro = ""
        $proximoAviso = (Get-Date).AddSeconds(30)
        while ((Get-Date) -lt $limite) {
            foreach ($h in $hostsApi) {
                try {
                    Invoke-RestMethod -Uri "http://${h}:8000/api/v1/saude" -TimeoutSec 15 | Out-Null
                    $saude = $true; $HostApi = $h; break
                } catch { $ultimoErro = $_.Exception.Message }
            }
            if ($saude) { break }
            # container da API parou ou reinicia em loop: mostra o motivo e para
            $estado = (Saida { docker compose -f docker-compose.yml -f docker-compose.ckan-local.yml ps -a api --format "{{.State}}" }).Trim()
            if ($estado -match "exited|dead|restarting") {
                Write-Host "    container 'api' esta '$estado'. Ultimas linhas do log:" -ForegroundColor Red
                (Saida { docker compose -f docker-compose.yml -f docker-compose.ckan-local.yml logs api --tail 40 }) -split "`n" |
                    ForEach-Object { Write-Host "      $_" }
                Falha "a API do produto final nao subiu (log acima; completo: docker compose logs api, em produtofinal)"
            }
            if ((Get-Date) -gt $proximoAviso) {
                Write-Host "    ainda aguardando... container api: '$estado'; ultimo erro: $ultimoErro" -ForegroundColor DarkYellow
                $proximoAviso = (Get-Date).AddSeconds(30)
            }
            Start-Sleep -Seconds 5
        }
        if (-not $saude) {
            (Saida { docker compose -f docker-compose.yml -f docker-compose.ckan-local.yml logs api --tail 40 }) -split "`n" |
                ForEach-Object { Write-Host "      $_" }
            Falha "a API do produto final nao respondeu em $TimeoutMin min. Ultimo erro: $ultimoErro"
        }
        Ok "API do produto final no ar (http://${HostApi}:8000)"

        $versaoVista = Saida { docker compose -f docker-compose.yml -f docker-compose.ckan-local.yml exec -T api python -c "from app.integrations.ckan.client import CkanClient; print(CkanClient().status()['ckan_version'])" }
        if ($versaoVista -match "2\.9") { Ok "a API do produto final enxerga o CKAN ($($versaoVista.Trim()))" }
        else { Aviso "a API do produto final NAO alcancou o CKAN. Saida: $versaoVista" }

        if ($AdminEmail) {
            $s1 = Read-Host "    Senha do administrador $AdminEmail (min. 8 caracteres)" -AsSecureString
            $senha = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
                [Runtime.InteropServices.Marshal]::SecureStringToBSTR($s1))
            $eap = $ErrorActionPreference; $ErrorActionPreference = "Continue"
            try {
                $r = $senha | docker compose -f docker-compose.yml -f docker-compose.ckan-local.yml exec -T api `
                    python -m app.cli criar-usuario --email $AdminEmail --nome $AdminNome --papel administrador 2>&1
            } finally { $ErrorActionPreference = $eap; $senha = $null }
            if ($LASTEXITCODE -eq 0) { Ok "administrador $AdminEmail criado" }
            else { Aviso "nao foi possivel criar o administrador (ja existe?): $(($r | Select-Object -Last 1))" }
        }
    } finally { Pop-Location }
}

# ---------------------------------------------------------------------------
RestaurarProxy
Write-Host ""
Write-Host "Pronto." -ForegroundColor Green
Write-Host "  CKAN ............ $Url   (admin definido em docker-compose.yml)"
Write-Host "  CKAN_API_KEY .... definido ($($token.Substring(0, 12))...)"
if ($ProdutoFinal) {
    Write-Host "  Produto final ... http://${HostApi}:8080   (API: http://${HostApi}:8000/api/v1/docs)"
    Write-Host "  Proximo passo ... entrar no produto final e clicar em 'Atualizar dados'"
}
