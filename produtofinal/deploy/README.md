# Implantação em servidor (VM da UFG temporária · SECTI/CGE-GO definitiva)

Decisão: [ADR-0032](../docs/adr/0032-entrega-por-codigo-fonte-com-subida-automatica.md). No servidor
vai só o produto final e a IA local (Ollama); o CKAN local é apenas do desenvolvimento.

## Requisitos do servidor

| Item | Mínimo | Recomendado |
|---|---|---|
| Sistema | Linux x86-64 com Docker Engine 24+ e o plugin `docker compose` 2.24+ | Debian 12/13, Ubuntu Server 22.04/24.04 ou RHEL 9 |
| CPU | 4 núcleos | 8 núcleos (a IA local roda em CPU) |
| Memória | 12 GB | 16 GB |
| Disco livre | 30 GB | 60 GB |
| Internet de saída | Na instalação: Docker Hub, npm, PyPI, ollama.com. Sempre: `dadosabertos.go.gov.br` | — |
| Usuário | No grupo `docker` (ou com `sudo`) | — |

## Publicar uma versão (o jeito do dia a dia)

Decisão: [ADR-0035](../docs/adr/0035-publicacao-por-versao-da-main.md). **Só vai ao servidor o que
está na `main`** do GitHub, identificado por uma versão `vMAIOR.MENOR.CORRECAO` (tag). O fluxo é:
merge de `desenvolvimento` na `main` (PR) → um comando no seu computador:

```powershell
.\produtofinal\deploy\publicar.ps1 -Versao 1.0.0   # cria a tag v1.0.0 na origin/main e publica
.\produtofinal\deploy\publicar.ps1 -Versao 1.0.0   # republica a mesma versão (tag já existe)
.\produtofinal\deploy\publicar.ps1 -Status         # versão e containers no servidor
.\produtofinal\deploy\publicar.ps1 -Voltar         # volta para a versão anterior
```

O script busca a `origin/main` (sua branch atual e alterações locais não importam), cria e envia a
tag (pede confirmação; `-Sim` pula), gera o pacote, envia por `scp` e, no servidor:

1. extrai em `~/gda.novo` e copia para lá o `.env` e `deploy/certificados/` da instalação atual;
2. faz o `docker compose build` com a versão atual ainda no ar (se o build falhar, nada muda);
3. move `~/gda` para `~/gda.anterior`, põe a nova no lugar e roda `docker compose up -d`;
4. mostra `docker compose ps` e o arquivo `VERSAO` (versão, commit e data do pacote).

Volumes (banco, segredos, modelos de IA) não mudam: o projeto se chama sempre `gda`. O `-Voltar`
troca as pastas de volta, mas **não desfaz migrações de banco** já aplicadas pela versão nova.

Numeração: `MAIOR` para mudança que exige ação de quem opera (ex.: nova variável obrigatória no
`.env`), `MENOR` para funcionalidade nova, `CORRECAO` para correção. Sem `-Versao`, o script publica
a `origin/main` atual com um rótulo como `v1.0.0-3-g1a2b3c4` — use só para testes rápidos.

**Configurar uma vez** (no seu computador): o servidor como apelido no `~/.ssh/config` e entrada por
chave, para não digitar senha a cada comando.

```
Host ufg
  HostName 200.137.197.131
  Port 55753
  User <seu usuário na VM>
```

```powershell
ssh-keygen -t ed25519
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh ufg "mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
```

Outro servidor ou pasta: `-Servidor <apelido>` e `-Pasta <nome na home>` (padrões `ufg` e `gda`).

## Pacote manual (sem SSH, ex.: entregar à SECTI)

### 1. Gerar o pacote (no computador do time)

```powershell
.\produtofinal\deploy\empacotar.ps1                               # do último commit
.\produtofinal\deploy\empacotar.ps1 -ArquivoEnv C:\caminho\ufg.env # já com o .env do servidor
```

Sai `gda-AAAAMMDD-<commit>.tar.gz`, com o compose de produção já como `docker-compose.yml` (o de
desenvolvimento e o do CKAN local ficam de fora) e o modelo de configuração como `.env.example`.
Copie para o servidor, por exemplo: `scp -P <porta> gda-*.tar.gz usuario@servidor:~`.

### 2. Subir (no servidor)

```bash
tar -xzf gda-AAAAMMDD-<commit>.tar.gz && cd gda
docker compose up -d
```

Só isso. A primeira subida demora (build das imagens e download de ~6 GB de modelos de IA) e prepara
tudo sozinha, sem perguntas:

| O quê | Como fica |
|---|---|
| Segredos | O serviço `segredos` gera chave JWT, chave de criptografia, sal da anonimização e senha do banco no volume `gda_segredos`, uma única vez. Nada disso fica em arquivo na pasta do código. |
| Banco | Migrações aplicadas pela API a cada subida. |
| Papéis | Só **Administrador** e **Gerência de Dados Abertos**. Os demais a GEDA cria na tela **Usuários e papéis**. |
| Usuário inicial | `admin@cge.go.gov.br`, papel Administrador, com **senha aleatória mostrada uma vez no log da API** (só se o banco não tiver nenhum usuário; ADR-0036). |
| CKAN lido | Perfil **Portal de Dados Abertos GO** (`https://dadosabertos.go.gov.br`) em uso, na tela **Configurações CKAN**. |
| IA local | Perfis do Ollama `qwen2.5:7b-instruct` (classificação) e `bge-m3` (embeddings), vinculados às tarefas da varredura LGPD. O serviço `ollama-modelos` baixa os modelos em segundo plano. |
| IA externa | O **Assistente** (modelo pago, com chave de API) fica sem perfil: configure na tela **Modelos de IA**. |
| Parâmetros | Valores padrão do catálogo, ajustáveis na tela **Parâmetros**. |
| Coleta | O worker faz a primeira coleta do CKAN assim que sobe; depois, todo dia às 03:00. |

> **Logo após subir, leia a senha do administrador no log da API** e troque-a no primeiro acesso
> (botão da chave, ao lado do nome do usuário, na barra lateral):
>
> ```bash
> docker compose logs api | grep "Senha gerada"
> ```
>
> A senha aparece só nessa primeira subida. Para escolher a senha ou o e-mail, defina
> `GDA_ADMIN_INICIAL_SENHA` / `GDA_ADMIN_INICIAL_EMAIL` no `.env` **antes** da primeira subida; a
> senha precisa de 8 caracteres ou mais, com letras e números (senha fraca é ignorada e a aleatória
> é usada no lugar). A documentação da API (`/api/v1/docs`) fica desligada no servidor; para ligá-la
> num ambiente de teste, `GDA_API_DOCS=true`.

Acompanhe com `docker compose ps` e `docker compose logs -f api worker ollama-modelos`. A varredura
LGPD que usa IA só funciona depois que o `ollama-modelos` terminar ("Modelos prontos.").

## Configuração (`.env`, opcional)

Sem `.env`, valem os padrões. Para mudar algo, copie `.env.example` para `.env`, descomente as linhas
e rode `docker compose up -d` de novo. O mais comum é a rede, quando há proxy reverso na frente.

**VM da UFG** (`https://gestao-dadosabertos.rsi.inf.ufg.br`; o proxy `10.100.70.207` repassa para a
porta 8080 da VM `10.100.70.201`):

```
GDA_PROXY_CONFIAVEL=10.100.70.207
GDA_IP_PUBLICACAO=10.100.70.201
GDA_PORTA_HTTP=8080
```

O `.env` não guarda segredos. Não defina nele `GDA_DATABASE_URL`, `GDA_SECRET_KEY`,
`GDA_ENCRYPTION_KEY` nem `GDA_LGPD_SAL_HASH` (variável definida prevalece sobre o volume `segredos`).

## HTTPS

| Situação | O que fazer |
|---|---|
| Há proxy reverso com HTTPS na frente (UFG; provavelmente a SECTI) | Deixe `deploy/certificados/` vazia e informe o IP do proxy em `GDA_PROXY_CONFIAVEL`. O proxy deve **sobrescrever** o `X-Forwarded-For` com `$remote_addr` e enviar o HSTS. Modelo: [`nginx-proxy.conf`](nginx-proxy.conf). |
| A própria aplicação faz o HTTPS | Coloque `fullchain.pem` e `privkey.pem` em `deploy/certificados/`, ajuste `GDA_PORTA_HTTP=80` e `GDA_PORTA_HTTPS=443` no `.env` e rode `docker compose up -d --force-recreate web`. |

## Segurança da rede (importante)

- Só o container `web` publica porta. Banco, API e Ollama ficam na rede interna do Docker.
- **Portas publicadas pelo Docker passam por cima do firewall do sistema (ufw/firewalld).** Atrás
  de proxy, publique só na interface interna pela qual o proxy chega: `GDA_IP_PUBLICACAO=<ip interno>`
  no `.env`. Para aceitar só o proxy, quem administra o servidor aplica na cadeia `DOCKER-USER`:
  ```bash
  sudo iptables -I DOCKER-USER -p tcp -m conntrack --ctorigdstport 8080 ! -s <IP_DO_PROXY> -j DROP
  ```
  (torne a regra persistente com `iptables-persistent` ou o equivalente da distribuição).
- O IP real do usuário no log de acesso só é aceito do proxy informado em `GDA_PROXY_CONFIAVEL`;
  a API, por sua vez, só aceita esse cabeçalho vindo do container `web`.

## Operação

```bash
docker compose ps                                  # estado dos serviços
docker compose logs -f api worker                  # logs (rotacionados: 5 × 20 MB por serviço)
docker compose logs -f ollama-modelos              # download dos modelos de IA
docker compose exec worker python -m app.cli coletar   # coleta manual, em primeiro plano
```

(No repositório, sem o pacote, acrescente `-f docker-compose.prod.yml` a cada comando.)

**Atualizar a versão:** use `deploy/publicar.ps1` (acima). À mão: extraia o pacote novo por cima (`tar -xzf ... `; o `.env`, `deploy/certificados/`
e os volumes ficam) e rode `docker compose up -d --build`. As migrações rodam sozinhas e nada do
que foi configurado nas telas é sobrescrito.

**Backups internos (automáticos, ADR-0034).** O `worker` gera sozinho uma cópia completa do banco
`gda` todo dia à 00:00 (guardada por 7 dias) e outra à 00:00 do dia 1 de cada mês, cobrindo o mês que
terminou (guardada por 1 ano). Ficam cifrados na tabela `backup_copia` do próprio banco, sem tela por
enquanto:

```bash
docker compose exec worker python -m app.cli backups                       # lista
docker compose exec worker python -m app.cli backup-agora diario           # gera uma agora
docker compose exec worker python -m app.cli exportar-backup 12 /tmp/gda.dump
docker compose exec worker python -m app.cli restaurar-backup 12 --banco gda_restaurado
```

Eles protegem de erro lógico (dado apagado, migração ruim), **não** da perda do volume `pgdata`:
a cópia mora no mesmo banco. Para isso serve o backup externo abaixo, que continua necessário. Para
abrir uma cópia é preciso a chave do volume `gda_segredos` (GDA_ENCRYPTION_KEY).

**Backup externo** (agende diariamente, guarde fora do servidor e com acesso restrito: contém dados
pessoais de usuários, o log de acesso e as chaves do sistema):

```bash
docker compose exec -T db pg_dump -U gda -Fc gda > gda-$(date +%F).dump
docker run --rm -v gda_lgpd_arquivos:/d -v "$PWD":/b alpine tar czf /b/lgpd-$(date +%F).tgz -C /d .
docker run --rm -v gda_segredos:/d -v "$PWD":/b alpine tar czf /b/segredos-$(date +%F).tgz -C /d .
```

Sem o backup do volume `gda_segredos`, um banco restaurado não abre as chaves de IA e de CKAN
salvas nas telas.

**Restaurar** (servidor novo): restaure primeiro os segredos, depois suba e restaure o banco:

```bash
docker volume create gda_segredos
docker run --rm -v gda_segredos:/d -v "$PWD":/b alpine tar xzf /b/segredos-AAAA-MM-DD.tgz -C /d
docker compose up -d
docker compose exec -T db pg_restore -U gda -d gda --clean --if-exists < gda-AAAA-MM-DD.dump
```

**Cuidado:** `docker compose down -v` apaga os volumes (banco, segredos, modelos). Para parar, use
`docker compose down` ou `docker compose stop`.

## Pendências que dependem da CGE-GO

- Prazo de retenção do log de acesso e das cópias da anonimização (ADR-0008, ADR-0016) — hoje não há
  expurgo automático.
- Política de backup (frequência, onde guardar, quem acessa).
- Aviso de privacidade aos usuários (LGPD art. 9º; Marco Civil art. 7º).
