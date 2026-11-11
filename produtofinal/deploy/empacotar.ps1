# Gera o pacote de entrega para o servidor (ADR-0032): um .tar.gz com o produto final pronto para
# `docker compose up -d`. No pacote:
#   - docker-compose.prod.yml vira docker-compose.yml (o ambiente de dev e o CKAN local ficam fora);
#   - deploy/env.producao.example vira .env.example;
#   - com -ArquivoEnv, o arquivo informado vira o .env (só configurações; os segredos o servidor gera).
# Por padrão usa o último commit (o .env, chaves, certificados e dados locais nunca entram).
# .tar.gz porque o tar existe em qualquer Linux; o unzip nem sempre (e instalar pede sudo).
#
#   .\produtofinal\deploy\empacotar.ps1                          # ..\gda-<data>-<commit>.tar.gz
#   .\produtofinal\deploy\empacotar.ps1 -ArquivoEnv C:\caminho\ufg.env  # já com o .env do servidor
#   .\produtofinal\deploy\empacotar.ps1 -Pendentes               # inclui o que não foi commitado
#   .\produtofinal\deploy\empacotar.ps1 -Saida C:\x.tar.gz
#   .\produtofinal\deploy\empacotar.ps1 -Ref v1.0.0              # de uma versão (tag) ou branch
# O pacote leva o arquivo VERSAO (versão, commit e data), que o servidor mostra após a subida.
# Para publicar no servidor da main, use deploy/publicar.ps1 (ADR-0034), que chama este script.
param(
    [string]$Saida = "",
    [string]$ArquivoEnv = "",
    [switch]$Pendentes,
    [string]$Ref = "HEAD",
    [string]$Versao = ""
)

$ErrorActionPreference = "Stop"
$raiz = git rev-parse --show-toplevel
if ($LASTEXITCODE -ne 0) { throw "Rode dentro do repositório." }
Set-Location $raiz
if ($ArquivoEnv -and -not (Test-Path $ArquivoEnv)) { throw "Arquivo -ArquivoEnv não encontrado: $ArquivoEnv" }
if ($Pendentes -and $Ref -ne "HEAD") { throw "-Pendentes só vale para a cópia de trabalho; não combine com -Ref." }

$commit = git rev-parse --short "$Ref^{commit}"
if ($LASTEXITCODE -ne 0) { throw "Referência não encontrada: $Ref" }
if (-not $Versao) { $Versao = git describe --tags --always $commit }
if ($Ref -eq "HEAD" -and -not $Pendentes -and (git status --porcelain -- produtofinal)) {
    Write-Warning "Há alterações não commitadas em produtofinal/; o pacote usa só o último commit (use -Pendentes para incluí-las)."
}
if (-not $Saida) {
    $sufixo = if ($Pendentes) { "$commit-pendentes" } elseif ($Versao -ne $commit) { "$Versao-$commit" } else { $commit }
    $Saida = Join-Path (Split-Path $raiz -Parent) ("gda-{0}-{1}.tar.gz" -f (Get-Date -Format "yyyyMMdd"), $sufixo)
}

$tmp = Join-Path ([IO.Path]::GetTempPath()) ("gda-pacote-" + [guid]::NewGuid().ToString("N"))
$gda = Join-Path $tmp "gda"
New-Item -ItemType Directory -Force $gda | Out-Null
try {
    if ($Pendentes) {
        # Arquivos versionados + novos ainda não versionados (respeita o .gitignore: sem .env etc.)
        git ls-files -co --exclude-standard -- produtofinal | ForEach-Object {
            if (Test-Path $_ -PathType Leaf) {
                $destino = Join-Path $gda ($_.Substring("produtofinal/".Length))
                New-Item -ItemType Directory -Force (Split-Path $destino -Parent) | Out-Null
                Copy-Item $_ $destino
            }
        }
    } else {
        # Arquivos exatamente como estão no repositório (fim de linha LF, normalizado pelo
        # .gitattributes). Sem o core.autocrlf=false, o Git do Windows converteria tudo para CRLF:
        # arquivando a subpasta, o .gitattributes da raiz não é lido, e o docker-entrypoint.sh com
        # CRLF não executa no Linux ("exec ...: no such file or directory").
        $tar = Join-Path $tmp "codigo.tar"
        git -c core.autocrlf=false -c core.eol=lf archive --format=tar -o $tar "${commit}:produtofinal"
        if ($LASTEXITCODE -ne 0) { throw "git archive falhou." }
        tar -xf $tar -C $gda
        if ($LASTEXITCODE -ne 0) { throw "tar falhou ao extrair." }
        Remove-Item $tar
    }

    if (-not (Test-Path (Join-Path $gda "docker-compose.prod.yml"))) {
        throw "Em '$Ref' ainda não existe produtofinal/docker-compose.prod.yml: essa versão não tem o deploy de servidor (ADR-0032)."
    }
    # Só o ambiente de produção: o compose de dev e o do CKAN local de testes não vão ao servidor
    Move-Item -Force (Join-Path $gda "docker-compose.prod.yml") (Join-Path $gda "docker-compose.yml")
    Move-Item -Force (Join-Path $gda "deploy\env.producao.example") (Join-Path $gda ".env.example")
    foreach ($fora in @("docker-compose.dev.yml", "docker-compose.ckan-local.yml", "deploy\empacotar.ps1", "deploy\publicar.ps1", ".env")) {
        $p = Join-Path $gda $fora
        if (Test-Path $p) { Remove-Item -Force $p }
    }
    if ($ArquivoEnv) { Copy-Item $ArquivoEnv (Join-Path $gda ".env") }

    # Identifica o que está no servidor (LF e sem BOM, para o `cat` no Linux)
    $origem = if ($Pendentes) { "$commit + alteracoes pendentes" } else { $commit }
    $texto = "versao=$Versao`ncommit=$origem`ngerado=$(Get-Date -Format 'yyyy-MM-dd HH:mm')`n"
    [IO.File]::WriteAllText((Join-Path $gda "VERSAO"), $texto, (New-Object Text.UTF8Encoding $false))

    tar -czf $Saida -C $tmp gda
    if ($LASTEXITCODE -ne 0) { throw "tar falhou ao compactar." }
} finally {
    Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
}

$nome = Split-Path $Saida -Leaf
Write-Host "Pacote gerado: $Saida (versão $Versao, commit $commit$(if ($Pendentes) { ' + alterações pendentes' }))"
Write-Host ""
Write-Host "No servidor:"
Write-Host "  tar -xzf $nome && cd gda && docker compose up -d"
Write-Host "Atualizar uma instalação existente: extraia por cima (o .env e os volumes ficam) e rode o mesmo comando."
