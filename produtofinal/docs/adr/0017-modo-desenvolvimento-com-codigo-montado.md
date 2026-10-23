# ADR-0017 — Desenvolver no Docker com o código montado do computador e recarga automática

| | |
|---|---|
| **Status** | Aceita |
| **Tipo** | Técnica |
| **Data da decisão** | 21/10/2026 |
| **Data do registro** | 21/10/2026 |
| **Decisores** | Victor Hugo Benatti (coordenação) |
| **Consultados** | — |
| **Origem** | Sessão de trabalho de 21/10/2026 |
| **Afeta** | `docker-compose.dev.yml` (novo); `frontend/vite.config.ts`; `README.md` |

## Contexto
O `docker-compose.yml` sobe o frontend como build estático no nginx e a API com o código copiado
para a imagem (`COPY . .`). Qualquer alteração só aparece depois de `docker compose up -d --build`,
o que atrapalha o desenvolvimento: em 21/10 uma tela alterada não aparecia porque o container ainda
servia o build anterior. Nem todas as máquinas do time têm Node ou Python instalados; o Docker é o
ambiente comum. As máquinas são Windows, onde a pasta montada no container não gera eventos de
alteração de arquivo.

## Critérios de decisão
1. Alteração salva no computador vale no container sem rebuild (frontend, API e worker).
2. Não mudar o ambiente de homologação/produção (`docker compose up -d` continua igual).
3. Sem dependência nova e sem exigir Node/Python instalados na máquina.
4. Mesma URL de sempre (http://localhost:8080).

## Opções consideradas

### Opção A — Arquivo de override `docker-compose.dev.yml` com bind mounts e servidores de desenvolvimento
- **Prós:** `./frontend` e `./backend` montados nos containers; Vite (HMR) no lugar do nginx e
  `uvicorn --reload` / `watchfiles` no worker; opcional (só vale com `-f docker-compose.dev.yml`);
  combina com o `docker-compose.ckan-local.yml`; reaproveita o estágio `build` do Dockerfile do
  frontend (Node e `node_modules` já instalados), sem dependência nova.
- **Contras:** no Windows precisa de polling (um pouco de CPU); `node_modules` fica num volume do
  container e precisa ser renovado (`--build -V`) quando o `package.json` muda; o servidor do Vite
  não reproduz exatamente o nginx (limite de upload, timeout).

### Opção B — `docker compose watch` (seção `develop.watch` no `docker-compose.yml`)
- **Prós:** recurso nativo do Compose; sincroniza arquivos ou refaz a imagem conforme a regra.
- **Contras:** o frontend continua sendo build estático, então cada alteração de tela refaz o build
  (segundos, sem HMR); exige mexer no `docker-compose.yml` principal; o comando fica preso no
  terminal.

### Opção C — Manter o rebuild a cada alteração, ou rodar `npm run dev` / `uvicorn` fora do Docker
- **Prós:** nada a configurar; fora do Docker a recarga é nativa.
- **Contras:** o rebuild é lento e esquecido com frequência (o problema de 21/10); fora do Docker
  exige Node e Python instalados em cada máquina.

## Decisão
Opção A. Atende aos quatro critérios: recarga imediata nos três serviços, o compose principal não
muda, nenhuma dependência nova e a mesma porta 8080 (o Vite escuta na porta 80 do container e o
HMR do navegador usa a 8080 publicada).

## Consequências
- **Positivas:** tela atualiza no navegador ao salvar; API e worker reiniciam sozinhos ao salvar um
  `.py`; o modo normal (nginx com build) continua sendo o de homologação.
- **Negativas e riscos:** dependências novas (`package.json`, `pyproject.toml`) exigem
  `up -d --build -V`; antes de entregar, conferir no modo normal (`npm run build` roda só nele);
  o polling usa CPU enquanto o ambiente de desenvolvimento estiver no ar.

## Validação
Testado em 21/10/2026 (Windows + Docker Desktop): HMR da tela de login pela porta 8080, recarga da
API e do worker ao alterar um `.py`. Validar com o time no próximo checkpoint.

## Revisões
| Data | Revisão | Autor |
|---|---|---|
