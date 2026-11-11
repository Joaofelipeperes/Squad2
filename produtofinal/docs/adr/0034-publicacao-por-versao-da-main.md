# ADR-0034 — Publicar no servidor só versões da `main`, marcadas com tag, por um script que faz o deploy por SSH

| | |
|---|---|
| **Status** | Aceita |
| **Tipo** | Processo |
| **Data da decisão** | 11/11/2026 |
| **Data do registro** | 11/11/2026 |
| **Decisores** | Victor Hugo Benatti (coordenação) |
| **Consultados** | — |
| **Origem** | Sessão de trabalho de 11/11/2026 (deploy na VM da UFG com Docker já instalado) |
| **Afeta** | `deploy/publicar.ps1` (novo), `deploy/empacotar.ps1`, `deploy/README.md`; complementa a ADR-0032 |

## Contexto
A ADR-0032 definiu a entrega como pacote do código-fonte (`deploy/empacotar.ps1`) e subida com
`docker compose up -d`. Na prática, cada atualização da VM da UFG exigia quatro passos manuais
(gerar o pacote, `scp`, entrar por SSH com senha, extrair e subir), o pacote saía do `HEAD` de
qualquer branch local e nada registrava qual versão estava no servidor. O repositório também guarda
o CKAN local de testes, que não pode ir ao servidor.

## Critérios de decisão
1. Saber sempre o que está no servidor e conseguir voltar.
2. Um comando para atualizar, sem passos manuais na VM (usuário sem `sudo`).
3. Só código revisado (que passou por PR) chega ao servidor.
4. Manter a ADR-0032: código-fonte, build no servidor, CKAN local fora.

## Opções consideradas

### Opção A — Script local que empacota uma tag da `main` e publica por SSH
- **Prós:** um comando; o servidor não precisa de acesso ao GitHub nem de credencial; reaproveita
  o `empacotar.ps1`; a tag identifica a versão e o arquivo `VERSAO` mostra no servidor o que está no ar;
  a versão anterior fica guardada para voltar.
- **Contras:** depende do computador de quem publica (PowerShell, Git, OpenSSH); o build ocorre no
  servidor (alguns minutos).

### Opção B — Clone do repositório na VM com `git pull` (sparse-checkout de `produtofinal/`)
- **Prós:** atualização incremental; nada a enviar.
- **Contras:** a VM precisaria de acesso ao GitHub com deploy key (o GitHub não está entre os destinos
  confirmados da VM); o compose de produção não é o padrão no repositório (`-f docker-compose.prod.yml`
  em todo comando); arquivos de desenvolvimento ficariam no servidor.

### Opção C — Integração contínua (GitHub Actions) publicando a cada merge na `main`
- **Prós:** automático, sem depender de um computador.
- **Contras:** o GitHub precisaria alcançar a VM por SSH e guardar credencial dela como segredo do
  repositório; publicar a cada merge tira o controle de quando a Paloma recebe mudanças.

## Decisão
**Opção A.** Só vai ao servidor o que está na `main`, identificado por tag `vMAIOR.MENOR.CORRECAO`
(versionamento semântico). `deploy/publicar.ps1 -Versao X.Y.Z` busca a `origin/main`, cria e envia a
tag se ela não existir (ou republica a tag existente, desde que esteja na `main`), gera o pacote com
`empacotar.ps1 -Ref`, envia por `scp` e, no servidor, faz o build ao lado da versão atual, troca as
pastas (`~/gda` → `~/gda.anterior`) mantendo `.env` e certificados, e roda `docker compose up -d`.
`-Voltar` restaura a anterior e `-Status` mostra a versão no ar.

## Consequências
- **Positivas:** atualização em um comando; versão rastreável (tag no GitHub + `VERSAO` no servidor);
  build falho não derruba o que está no ar; volta rápida.
- **Negativas e riscos:** `-Voltar` não desfaz migrações de banco — migração incompatível com a versão
  anterior exige restaurar o backup (deploy/README.md). A `main` precisa receber o merge de
  `desenvolvimento` antes de cada versão; o `empacotar.ps1` recusa referência sem
  `docker-compose.prod.yml`.

## Validação
Time do Squad 2, no primeiro deploy na VM da UFG.

## Revisões

| Data | Revisão | Autor |
|---|---|---|
