# Publica o produto final no servidor por SSH, sempre a partir da main do GitHub (ADR-0035).
# Faz tudo de uma vez: busca a origin/main, cria a versão (tag) se for nova, gera o pacote
# (deploy/empacotar.ps1), envia por scp e, no servidor, troca a pasta e roda o docker compose.
# A pasta do servidor guarda o .env, deploy/certificados/ e os volumes; a versão anterior fica em
# <pasta>.anterior para voltar com -Voltar. O CKAN local nunca vai ao servidor.
#
#   .\produtofinal\deploy\publicar.ps1 -Versao 1.0.0   # cria a tag v1.0.0 na origin/main (se não existir) e publica
#   .\produtofinal\deploy\publicar.ps1 -Versao 1.0.0   # mesma tag de novo: republica exatamente essa versão
#   .\produtofinal\deploy\publicar.ps1                 # publica a origin/main atual, sem criar versão
#   .\produtofinal\deploy\publicar.ps1 -Status         # mostra a versão e os containers do servidor
#   .\produtofinal\deploy\publicar.ps1 -Voltar         # volta para a versão anterior
#
# Pré-requisito: o servidor como "Host" no ~/.ssh/config, com chave (o padrão é "ufg"; ver deploy/README.md).
param(
    [string]$Versao = "",
    [string]$Servidor = "ufg",
    [string]$Pasta = "gda",
    [switch]$Voltar,
    [switch]$Status,
    [switch]$Sim
)

$ErrorActionPreference = "Stop"
if ($Pasta -notmatch '^[A-Za-z0-9._-]+$') { throw "-Pasta deve ser um nome simples dentro da home do servidor (ex.: gda)." }

function Remoto([string]$comando) {
    # Comando em uma linha, só com aspas simples: o PowerShell 5.1 estraga aspas duplas ao chamar o ssh
    ssh $Servidor $comando
    if ($LASTEXITCODE -ne 0) { throw "Falhou no servidor (código $LASTEXITCODE)." }
}

if ($Status) {
    Remoto "cd ~/$Pasta && cat VERSAO 2>/dev/null; docker compose ps"
    return
}

if ($Voltar) {
    Write-Host "Voltando ~/$Pasta para ~/$Pasta.anterior em $Servidor."
    Write-Host "Atenção: migrações de banco já aplicadas pela versão atual não são desfeitas."
    Remoto ("set -e; cd ~; [ -d @P@.anterior ] || { echo Nao ha versao anterior em ~/@P@.anterior; exit 1; }; " +
            "mv @P@ @P@.troca; mv @P@.anterior @P@; mv @P@.troca @P@.anterior; cd @P@; " +
            "docker compose up -d --build --remove-orphans; docker compose ps; cat VERSAO").Replace("@P@", $Pasta)
    return
}

$raiz = git rev-parse --show-toplevel
if ($LASTEXITCODE -ne 0) { throw "Rode dentro do repositório." }
Set-Location $raiz

git fetch origin main --tags --quiet
if ($LASTEXITCODE -ne 0) { throw "Não consegui buscar a origin/main." }

if ($Versao) {
    $tag = if ($Versao.StartsWith("v")) { $Versao } else { "v$Versao" }
    if ($tag -notmatch '^v\d+\.\d+\.\d+$') { throw "Versão deve ser MAIOR.MENOR.CORRECAO, ex.: 1.0.0 (ADR-0035)." }
    git rev-parse -q --verify "refs/tags/$tag" | Out-Null
    if ($LASTEXITCODE -eq 0) {
        git merge-base --is-ancestor "$tag^{commit}" origin/main
        if ($LASTEXITCODE -ne 0) { throw "A tag $tag não está na main; só versões da main vão ao servidor." }
        Write-Host "Versão $tag já existe: publicando exatamente ela."
    } else {
        $alvo = git log -1 --format="%h %s (%an, %ad)" --date=short origin/main
        Write-Host "Nova versão $tag na origin/main: $alvo"
        # Via cmd: no PowerShell 5.1, redirecionar o stderr de um programa com "Stop" vira exceção
        $anterior = cmd /c "git describe --tags --abbrev=0 origin/main 2>nul"
        if ($anterior) {
            Write-Host "Mudanças desde $anterior`:"
            git log --oneline --no-merges "$anterior..origin/main" -- produtofinal | Select-Object -First 30 | ForEach-Object { "  $_" }
        }
        if (-not $Sim) {
            $ok = Read-Host "Criar a tag $tag e enviá-la ao GitHub? [s/N]"
            if ($ok -notmatch '^[sS]') { Write-Host "Cancelado."; return }
        }
        git tag -a $tag -m "Versão $tag" origin/main
        if ($LASTEXITCODE -ne 0) { throw "Não consegui criar a tag $tag." }
        git push origin "refs/tags/$tag"
        if ($LASTEXITCODE -ne 0) { git tag -d $tag | Out-Null; throw "Não consegui enviar a tag $tag ao GitHub (tag local removida)." }
    }
    $ref = $tag
    $rotulo = $tag
} else {
    $ref = "origin/main"
    $rotulo = git describe --tags --always origin/main
    Write-Warning "Sem -Versao: publicando a origin/main atual como '$rotulo', sem criar versão."
}

$nome = "gda-$rotulo.tar.gz"
$pacote = Join-Path ([IO.Path]::GetTempPath()) $nome
& (Join-Path $PSScriptRoot "empacotar.ps1") -Ref $ref -Versao $rotulo -Saida $pacote | Out-Null

try {
    Write-Host "Enviando $nome para ${Servidor}..."
    scp -q $pacote "${Servidor}:~/$nome"
    if ($LASTEXITCODE -ne 0) { throw "scp falhou." }
} finally {
    Remove-Item -Force $pacote -ErrorAction SilentlyContinue
}

# No servidor: extrai em P.novo, traz o .env e os certificados, faz o build com a pasta antiga ainda
# no ar (se o build falhar, nada muda) e só então troca as pastas e recria os containers.
Write-Host "Atualizando ~/$Pasta em $Servidor (o build pode levar alguns minutos)..."
Remoto ("set -e; cd ~; rm -rf @P@.novo; mkdir @P@.novo; tar -xzf @ARQ@ -C @P@.novo; rm -f @ARQ@; " +
        "if [ -f @P@/.env ]; then cp -p @P@/.env @P@.novo/gda/.env; fi; " +
        "if [ -d @P@/deploy/certificados ]; then cp -a @P@/deploy/certificados/. @P@.novo/gda/deploy/certificados/; fi; " +
        "cd @P@.novo/gda; docker compose build; cd ~; " +
        "if [ -d @P@ ]; then rm -rf @P@.anterior; mv @P@ @P@.anterior; fi; " +
        "mv @P@.novo/gda @P@; rmdir @P@.novo; cd @P@; " +
        "docker compose up -d --remove-orphans; docker compose ps; cat VERSAO").Replace("@ARQ@", $nome).Replace("@P@", $Pasta)

Write-Host ""
Write-Host "Publicado: $rotulo em $Servidor (~/$Pasta). Anterior guardada em ~/$Pasta.anterior (-Voltar)."
