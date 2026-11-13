# ADR-0032 — Entregar o sistema ao servidor como código-fonte com compose de produção que se prepara sozinho no `docker compose up -d`

| | |
|---|---|
| **Status** | Aceita |
| **Tipo** | Técnica |
| **Data da decisão** | 05/11/2026 (forma de entrega); 09/11/2026 (preparação automática, sem instalador) |
| **Data do registro** | 09/11/2026 |
| **Decisores** | Victor Hugo Benatti (coordenação) |
| **Consultados** | Philippe Augusto (proxy reverso da UFG) |
| **Origem** | Sessões de trabalho de 05/11/2026 (revisão de segurança do deploy atrás do proxy da UFG) e 09/11/2026 (acesso à VM da UFG: usuário sem `sudo`; pedido da coordenação de subir tudo só com `docker compose up -d`) |
| **Afeta** | `docker-compose.prod.yml` (novo), `docker-compose.yml`, `backend/Dockerfile`, `backend/docker-entrypoint.sh`, `frontend/Dockerfile`, `frontend/nginx/`, `deploy/`, `app/segredos.py`, `app/instalacao.py`, `app/cli.py`, `app/worker.py`, módulos `acesso`, `ia`, `ckan_config` e `inventario`; ADR-0016; ADR-0024; ADR-0004 (não muda a questão em aberto) |

## Contexto
O sistema vai rodar em dois lugares: uma VM temporária da UFG (`gestao-dadosabertos.rsi.inf.ufg.br`,
atrás de um proxy reverso administrado por terceiros) para a Paloma testar, e depois a
infraestrutura da SECTI/CGE-GO, onde o time não terá acesso contínuo. Nos dois, só vai o produto
final e a IA local; o CKAN local é só do ambiente de desenvolvimento.

O `docker-compose.yml` existente é de desenvolvimento: senha do banco fixa (`gda`), API publicada em
todas as interfaces e uvicorn aceitando `X-Forwarded-For` de qualquer origem — o IP do log de acesso
podia ser forjado chamando a porta 8000 direto (achado de severidade alta da revisão de 05/11).
Também não havia cabeçalhos de segurança, limite de tentativas de login, `.dockerignore` (a pasta
`dados_lgpd`, com dado pessoal, entrava na imagem) nem usuário sem privilégio nos containers.

A varredura LGPD do Eixo 2 precisa do Ollama com `qwen2.5:7b-instruct` e `bge-m3` no servidor
(dado pessoal não sai para provedor externo, ADR-0002).

Na VM da UFG (09/11), o usuário do time não tem `sudo`; quem opera o servidor da SECTI também não
será o time. Qualquer passo além de "copiar o código e subir" depende de alguém disponível.

## Critérios de decisão
1. Quem recebe instala e atualiza sem o time: copiar o código e rodar **um** comando padrão do
   Docker, sem editar arquivos nem rodar scripts.
2. Segurança por padrão: segredos gerados no próprio servidor, só uma porta publicada, IP do log
   confiável.
3. Mesma receita para a UFG e para a SECTI/CGE.
4. Manutenção simples pelo time durante a residência.

## Opções consideradas

### Forma de entrega

#### Opção A — Código-fonte + compose de produção (build no servidor)
- **Prós:** um pacote `.tar.gz` com o código; auditável pela CGE; nada de registry nem conta
  externa; atualizar = trocar o código e subir de novo.
- **Contras:** o servidor precisa de internet na instalação (Docker Hub, npm, PyPI, ollama.com);
  o build demora alguns minutos; versões de dependências resolvidas no dia do build.

#### Opção B — Imagens prontas exportadas (`docker save`, arquivo .tar)
- **Prós:** instalação offline e reprodutível; sem build no servidor.
- **Contras:** pacote de vários GB por versão; o time precisa gerar e transferir imagens a cada
  atualização; a CGE recebe binários em vez de código.

#### Opção C — Imagens publicadas em registry (GHCR)
- **Prós:** atualização com `docker compose pull`.
- **Contras:** exige conta e repositório de imagens, o servidor acessando o GitHub e imagens com o
  código fora da infraestrutura do Estado.

### Preparação da primeira subida (segredos, administrador, IA, CKAN)

#### Opção A1 — Script instalador (`deploy/instalar.sh`) que gera o `.env` e roda comandos
- **Prós:** passo a passo explícito; pergunta o que falta (URL, proxy, e-mail do administrador).
- **Contras:** mais um passo além do Docker; interativo; quem opera precisa rodar o script certo a
  cada atualização; segredos num arquivo `.env` em texto na pasta do código.

#### Opção A2 — Os próprios containers se preparam no `docker compose up -d`
- **Prós:** o comando padrão do Docker basta; idempotente a cada subida; nada a lembrar na
  atualização; segredos num volume do Docker, fora da pasta do código.
- **Contras:** a preparação fica espalhada (serviço `segredos`, API e worker); administrador inicial
  com senha padrão até a primeira troca; perder o volume `segredos` exige backup.

## Decisão
**Opção A** (05/11) com **preparação A2** (09/11), escolhidas pela coordenação. A2 substitui o
instalador da primeira versão desta decisão, que não chegou a ser usado em servidor.

Desenho:
- `docker-compose.prod.yml` (no pacote, vira o `docker-compose.yml`): só o `web` publica porta
  (`GDA_IP_PUBLICACAO:GDA_PORTA_HTTP`, e a HTTPS); `db`, `api`, `worker` e `ollama` só na rede
  interna `interna` (sub-rede fixa configurável, `web` com IP fixo). A API aceita `X-Forwarded-For`
  **apenas do IP do `web`** (`FORWARDED_ALLOW_IPS`). Logs rotacionados; `restart: unless-stopped`;
  `no-new-privileges`. O `.env` é opcional (só muda padrões; modelo em `deploy/env.producao.example`).
- Serviço `segredos` (`app/segredos.py`): na primeira subida gera chave JWT, chave Fernet, sal da
  anonimização e senha do banco no volume `segredos`; depois nunca os troca. O Postgres lê a senha
  por `POSTGRES_PASSWORD_FILE`; o `docker-entrypoint.sh` da API e do worker transforma os arquivos
  nas variáveis `GDA_*` (variável já definida no ambiente prevalece).
- API, a cada subida (`app/instalacao.py`, depois do `alembic upgrade head`), só cria o que falta:
  papéis `administrador` e `gerente_geda` (`GDA_PAPEIS_INICIAIS`; os demais a GEDA cria na tela),
  administrador inicial `admin@cge.go.gov.br` com senha `12345` se o banco não tem usuário
  (aviso no log enquanto a senha não for trocada), perfil do CKAN = portal oficial, e perfis do
  Ollama vinculados às tarefas da varredura LGPD se não há nenhum perfil de IA. O Assistente
  (modelo externo com chave de API) fica para o administrador configurar. Parâmetros usam os
  padrões do catálogo.
- Worker: com `GDA_COLETA_INICIAL=true`, faz a primeira coleta do CKAN ao iniciar se nunca houve
  nenhuma; depois, só o cron.
- `ollama-modelos`: serviço que baixa os modelos uma vez e termina (alteráveis no `.env`).
- HTTPS configurável: sem certificado, modo HTTP atrás do proxy (UFG, CGE); com `fullchain.pem` e
  `privkey.pem` em `deploy/certificados/`, o nginx do container faz TLS 1.2/1.3 com HSTS.
- nginx do container (`frontend/nginx/`): `real_ip` só para `GDA_PROXY_CONFIAVEL`, cabeçalhos de
  segurança (CSP nas telas, `nosniff`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`),
  limite de 20 tentativas de login por minuto por IP e `server_tokens off`.
- API e worker rodam com o usuário `gda` (uid 10001); `.dockerignore` tira `.env`, `dados_lgpd`,
  `.venv` e `node_modules` das imagens. Imagem do Ollama com versão fixa (0.40.14).
- `docker-compose.yml` continua para desenvolvimento, com a API só em `127.0.0.1`.
- `deploy/empacotar.ps1` gera o `.tar.gz` do último commit (`git archive`, sem segredos), já com o
  compose de produção como `docker-compose.yml`, sem o compose de dev e o do CKAN local; `-ArquivoEnv`
  inclui um `.env` de configuração (ex.: IP do proxy da UFG).

## Consequências
- **Positivas:** instalação e atualização com `docker compose up -d`; segredos nunca passam pelo
  repositório, por chat nem por arquivo na pasta do código; IP do log de acesso não pode mais ser
  forjado por quem alcança o servidor; a CGE recebe código auditável.
- **Negativas e riscos:**
  - **Senha inicial `12345` do administrador** num sistema exposto na internet até a primeira troca:
    trocar logo após subir (o log da API avisa a cada subida). Configurável no `.env`
    (`GDA_ADMIN_INICIAL_SENHA`). Melhoria possível: obrigar a troca no primeiro login.
  - **Backup do volume `segredos`** junto com o banco: sem a chave Fernet, as chaves de IA e de CKAN
    salvas ficam ilegíveis; sem a senha, a API não alcança o banco (`deploy/README.md`).
  - Porta publicada pelo Docker ignora o firewall do sistema: documentado em `deploy/README.md`
    (`GDA_IP_PUBLICACAO` na interface interna ou regra em `DOCKER-USER`).
  - O IP real depende do proxy sobrescrever o `X-Forwarded-For` e de o IP dele estar em
    `GDA_PROXY_CONFIAVEL`; sem isso o log registra o IP do proxy (e o limite de login vira coletivo).
  - Build no dia da instalação pode trazer versão nova de dependência sem versão fixa; mitigar com
    lockfile do backend em decisão futura.
  - Servidor sem os ~12 GB de RAM deixa a varredura com IA lenta ou falhando (a VM da UFG tem 7,8 GB
    sem swap em 09/11).
  - Docker Compose 2.24 ou mais novo (`env_file` opcional).

## Validação
- Teste local do pacote completo (build, subida, nginx nos dois modos, IP forjado recusado) em 05/11.
- Teste local da subida do zero só com `docker compose up -d` a partir do pacote — 09/11.
- Primeira instalação na VM da UFG — pendente (Docker não instalado; usuário sem `sudo`).
- Requisitos do servidor e quem opera o backup na SECTI/CGE-GO — validar com a Paloma e a SECTI.

## Revisões
| Data | Revisão | Autor |
|---|---|---|
| 12/11/2026 | A senha inicial `12345` deixa de existir: com `GDA_ADMIN_INICIAL_SENHA` vazia ou fraca, o administrador inicial recebe uma senha aleatória, mostrada uma vez no log da API (ADR-0036) | Victor |
