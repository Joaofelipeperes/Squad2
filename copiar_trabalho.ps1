# Copia o trabalho do Eixo 2 (pasta sem git) para o clone do repositorio, na branch atual.
# Uso, dentro da pasta do clone:  .\copiar_trabalho.ps1 -Origem C:\Users\lmfci\Squad2
# Para cada arquivo: se a versao do clone ainda e a original (a do zip), copia a sua.
# Se alguem da equipe mudou o arquivo na desenvolvimento, NAO sobrescreve: salva a sua
# versao ao lado como <arquivo>.meu e lista para juntar a mao.
param([Parameter(Mandatory=$true)][string]$Origem)
$ErrorActionPreference = "Stop"
if (-not (Test-Path ".git")) { Write-Host "Rode dentro da pasta do clone (onde fica a pasta .git)." -ForegroundColor Red; exit 1 }
# caminho, hash do arquivo no zip original (vazio = arquivo novo, nao existia no zip)
$arquivos = @(
    @("produtofinal\.env.example", "efa80015fb040a58f4fa1c761f2e6c100833b2b0"),
    @("produtofinal\.gitignore", "21dd520dc1d37b65cda8849e724dd0e8202fede9"),
    @("produtofinal\backend\alembic\versions\b5550bea284d_lgpd_fluxo_de_anonimizacao.py", ""),
    @("produtofinal\backend\alembic\versions\f43bd6d4ace1_lgpd_varredura_e_explicacao_do_achado.py", ""),
    @("produtofinal\backend\app\core\config.py", "a214f3dca8a6f646717c7bccc062f8ec0ee01a87"),
    @("produtofinal\backend\app\core\permissoes.py", "3c7d3daf78507d4937ebce6f8cb04f70bfb6a9f6"),
    @("produtofinal\backend\app\integrations\ai\__init__.py", "bdc4f1d298e848ebe02e989ff390dd438bffd949"),
    @("produtofinal\backend\app\integrations\ai\base.py", "b502cbfc8d5ab721dd1ab9ee4e0a959fd7a302cc"),
    @("produtofinal\backend\app\integrations\ai\policy.py", "b2a182bdeaeb19ac9982817279708415417d05a8"),
    @("produtofinal\backend\app\integrations\ai\providers\anthropic.py", ""),
    @("produtofinal\backend\app\integrations\ai\providers\ollama.py", "3e680012a1e9e225d3784e4bff397106d0dba9c6"),
    @("produtofinal\backend\app\integrations\ai\providers\openai_compat.py", "3f2a88585be896150822dc4f31fa5b545151255a"),
    @("produtofinal\backend\app\integrations\ckan\client.py", "60478261c0cbcee0e3b9231925c8004b44b0edf3"),
    @("produtofinal\backend\app\modules\assistente\regras.py", ""),
    @("produtofinal\backend\app\modules\assistente\router.py", "57fc90ee67362311aacba858f18bed4cbfaed169"),
    @("produtofinal\backend\app\modules\assistente\service.py", "4289d643a0957e734cf6251d6b1ee959de08a053"),
    @("produtofinal\backend\app\modules\ia\gateway.py", "9f2a1a85a087d3af98f7464bb3c827a0c8e81263"),
    @("produtofinal\backend\app\modules\ia\models.py", "326abe56e7252df1fab4b8a49d2046e5bcd53ea2"),
    @("produtofinal\backend\app\modules\ia\router.py", "5e1918f01eacc300fd172b7ed9b281ca661632b7"),
    @("produtofinal\backend\app\modules\ia\schemas.py", "de2b016031c32a5d5a76a400617accd5c8c25c11"),
    @("produtofinal\backend\app\modules\ia\service.py", "fe73557af38022a0178a672587858e5d599bf25d"),
    @("produtofinal\backend\app\modules\lgpd\__init__.py", "1332c016b76437cd3a6f62e24f8e4a065c8a90e4"),
    @("produtofinal\backend\app\modules\lgpd\anonimizacao.py", ""),
    @("produtofinal\backend\app\modules\lgpd\correcoes.py", ""),
    @("produtofinal\backend\app\modules\lgpd\deteccao.py", ""),
    @("produtofinal\backend\app\modules\lgpd\leitura.py", ""),
    @("produtofinal\backend\app\modules\lgpd\models.py", "01015640e637f6dd6f6986337520cbe4658c0f7d"),
    @("produtofinal\backend\app\modules\lgpd\regras.py", ""),
    @("produtofinal\backend\app\modules\lgpd\router.py", "939b6c156dcf7503c2091852a431bf889eb53630"),
    @("produtofinal\backend\app\modules\lgpd\schemas.py", ""),
    @("produtofinal\backend\app\modules\lgpd\service.py", "d0c5666d37e6d08cf9c2d706abd4fca147e6c48c"),
    @("produtofinal\backend\app\modules\parametros\catalogo.py", "bffbbca746bac16bb70abc8b98391d800ed41d0c"),
    @("produtofinal\backend\tests\test_assistente_contexto.py", ""),
    @("produtofinal\backend\tests\test_ia_anthropic.py", ""),
    @("produtofinal\backend\tests\test_ia_embeddings.py", ""),
    @("produtofinal\backend\tests\test_lgpd.py", ""),
    @("produtofinal\backend\tests\test_lgpd_anonimizacao.py", ""),
    @("produtofinal\docker-compose.yml", "3af265158340a79d37ffbf36159958fe827da81d"),
    @("produtofinal\docs\adr\0002-camada-ia-plugavel.md", "0dbe17ca97c1ae79f1e2950d91b1822dbdb3d8d8"),
    @("produtofinal\docs\adr\0008-anonimizacao-com-publicacao-no-ckan.md", "1db076989109d3d3c69f5a0c2c0c005ff5ff663c"),
    @("produtofinal\docs\adr\0010-deteccao-de-dados-pessoais-hibrida.md", "dd86d8f8d758b38b86e70f0b9392f5aea317c213"),
    @("produtofinal\docs\adr\0011-assistente-sem-banco-vetorial.md", "54f0ab619d10e32aa5a9225cd3704cbf0430fa2b"),
    @("produtofinal\docs\adr\0017-claude-haiku-no-assistente.md", ""),
    @("produtofinal\docs\adr\0018-varredura-lgpd-com-motor-do-detector3.md", ""),
    @("produtofinal\docs\adr\README.md", "c8657c23d7a3dc95fbf4b5426684f571784f39cf"),
    @("produtofinal\docs\banco\mer.md", "77803207b65ae4f545b1cf734ccaffefa840f354"),
    @("produtofinal\docs\modulos\acesso.md", "9145a646a3b1ea004e8a639d146ed8924c1e403b"),
    @("produtofinal\docs\modulos\assistente.md", "d6f9518ed5830ef45ea526e0ceb040be651d431f"),
    @("produtofinal\docs\modulos\atualizacoes.md", "b4aebbd5b3b7b6abf072b5394be6acc5fd3e8191"),
    @("produtofinal\docs\modulos\ia.md", "2806d36e036b00ae84ad438539eca8499cc78fa5"),
    @("produtofinal\docs\modulos\inventario.md", "219f2c9111dc8fe67ea41394d8a1c0aca071630e"),
    @("produtofinal\docs\modulos\lgpd.md", "beb4c7dc7f61a81ff1f6a3d63564a2ecf8e89717"),
    @("produtofinal\docs\modulos\parametros.md", "02588f437e87867420285d5e59c50986cd22b2f5"),
    @("produtofinal\docs\modulos\pda.md", "720e54e301df942e89e7650441899fbcf6a38b39"),
    @("produtofinal\frontend\src\design-system\overrides.css", "fda00d2d7152775c2e4cf952fc2e6c28f5c80c03"),
    @("produtofinal\frontend\src\modules\assistente\AssistenteChat.tsx", "c49fc06db981da356be5667a27eddb5d22fa9d0c"),
    @("produtofinal\frontend\src\modules\ia\ModelosIAPage.tsx", "14ab521ca0796d636128a4915c0d1a81f8729b47"),
    @("produtofinal\frontend\src\modules\ia\PerfilForm.tsx", "b10c91e1fe2c42cdfc0b37941e7338b02ef56c79"),
    @("produtofinal\frontend\src\modules\ia\api.ts", "0ce9afe7b8f77a1bb5614986a1a870df5cebe7cb"),
    @("produtofinal\frontend\src\modules\lgpd\AchadoModal.tsx", ""),
    @("produtofinal\frontend\src\modules\lgpd\CorrecaoModal.tsx", ""),
    @("produtofinal\frontend\src\modules\lgpd\CorrecoesPainel.tsx", ""),
    @("produtofinal\frontend\src\modules\lgpd\LgpdPage.tsx", "114232292a7d6a8a0b1fd66cafecf1d5c9ba63e1"),
    @("produtofinal\frontend\src\modules\lgpd\NovaCorrecaoModal.tsx", ""),
    @("produtofinal\frontend\src\modules\lgpd\VarreduraPainel.tsx", ""),
    @("produtofinal\frontend\src\modules\lgpd\api.ts", ""),
    @("produtofinal\frontend\src\modules\lgpd\formato.tsx", ""),
    @("produtofinal\frontend\src\shared\acesso\permissoes.gen.ts", "a4aee19d757e63ac266bce92b24e6610a3450340"),
    @("produtofinal\frontend\src\shared\ui\Modal.tsx", "0f66846029322192abf20069f264b0162e93b95b"),
    @("produtofinal\scripts\gerar_mer.py", "5dba379864865344c1371df17f471814abcb9f26")
)
$copiados = 0; $conflitos = @()
foreach ($a in $arquivos) {
    $rel, $base = $a[0], $a[1]
    $de = Join-Path $Origem $rel
    if (-not (Test-Path $de)) { Write-Host "  falta na origem: $rel" -ForegroundColor Yellow; continue }
    $para = Join-Path (Get-Location) $rel
    if (Test-Path $para) {
        $atual = (git hash-object -- "$rel").Trim()
        if ($atual -ne $base) {
            Copy-Item $de "$para.meu" -Force
            $conflitos += $rel
            continue
        }
    } else {
        New-Item -ItemType Directory -Force -Path (Split-Path $para) | Out-Null
    }
    Copy-Item $de $para -Force
    $copiados++
}
Write-Host ""
Write-Host "$copiados arquivo(s) copiados." -ForegroundColor Green
if ($conflitos.Count) {
    Write-Host "$($conflitos.Count) arquivo(s) tambem foram alterados na desenvolvimento e NAO foram sobrescritos." -ForegroundColor Yellow
    Write-Host "A sua versao ficou ao lado, com final .meu:" -ForegroundColor Yellow
    $conflitos | ForEach-Object { Write-Host "  $_" }
} else {
    Write-Host "Nenhum conflito com a desenvolvimento." -ForegroundColor Green
}
