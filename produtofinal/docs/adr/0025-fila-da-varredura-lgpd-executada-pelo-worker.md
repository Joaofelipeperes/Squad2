# ADR-0025 — Executar a fila da varredura LGPD no worker e espaçar os downloads do portal

| | |
|---|---|
| **Status** | Aceita |
| **Tipo** | Técnica |
| **Data da decisão** | 29/10/2026 |
| **Data do registro** | 29/10/2026 |
| **Decisores** | Victor Hugo Benatti (coordenação) |
| **Consultados** | — (validar com a Luiza, responsável pelo módulo `lgpd`) |
| **Origem** | Sessão de 29/10: 156 varreduras pedidas pela tela ficaram paradas na fila |
| **Afeta** | Módulo `lgpd` (fila e job), `integrations/ckan/client.py` (download), worker; revisa um desdobramento da ADR-0021; US11/US12, PBI-32, PBI-34 |

## Contexto
A ADR-0021 colocou a varredura "em segundo plano na API": o `POST /lgpd/varreduras` gravava as
varreduras como `pendente` e entregava a lista de IDs a uma `BackgroundTask` do FastAPI, que vive
na memória do processo da API. Em 28/10 foram pedidas 156 varreduras; o processo da API deixou de
existir no meio da terceira (o container foi recriado) e:

- as 155 `pendente` ficaram órfãs para sempre: nada as executa de novo, e elas ainda bloqueiam
  novos pedidos dos mesmos recursos ("já estava na fila");
- a que estava em `executando` só seria liberada 12 h depois, e só quando alguém pedisse outra
  varredura (`_liberar_presas`).

Qualquer reinício derruba a fila: deploy, `docker compose up --build`, reinício do Docker ou do
computador e, no modo desenvolvimento (ADR-0017), cada arquivo `.py` salvo (`--reload`). Com o
modelo local, um único CSV com texto livre leva mais de 20 min, então uma fila de centenas de
recursos dura horas e quase sempre atravessa um reinício.

No mesmo dia, um lote do portal inteiro (1.763 recursos com link para `dadosabertos.go.gov.br`)
recebeu **HTTP 429** em 1.583 downloads: o portal oficial bloqueia rajadas. Com um download a cada
3 s, o mesmo lote rodou sem nenhum 429.

## Critérios de decisão
1. A fila não pode se perder em reinício da API nem do worker.
2. Uma varredura nunca é executada por dois processos ao mesmo tempo.
3. Sem infraestrutura nova (PGP: infraestrutura leve; ADR-0012: sem fila externa).
4. Respeitar o portal oficial do Estado (sem provocar bloqueio) mesmo que o lote demore mais.

## Opções consideradas

### Executor da fila

#### Opção A — Worker como único executor, fila no banco
A API só grava as `pendente`; um job do worker, a cada minuto, executa as pendentes, a mais antiga
primeiro, até a fila esvaziar.
- **Prós:** sobrevive a reinício da API e do worker (o estado está no banco); um só executor
  (`max_instances=1` do APScheduler), então não há execução dupla nem precisa de trava no banco;
  varredura longa não ocupa a API; segue a ADR-0012.
- **Contras:** a varredura começa em até 1 min, não na hora; sem o worker no ar nada roda (no
  desenvolvimento fora do Docker é preciso subir `python -m app.worker`); enquanto um ciclo longo
  roda, o APScheduler registra a cada minuto que pulou a execução seguinte.

#### Opção B — Manter a tarefa em segundo plano da API e recuperar as órfãs
Recuperação das pendentes ao subir a API e pelo worker.
- **Prós:** começa na hora; mudança menor.
- **Contras:** o lote continua preso à vida da API (o `--reload` derruba a cada arquivo salvo);
  API e worker podem executar a mesma varredura ao mesmo tempo, o que exigiria trava no banco
  (`SELECT … FOR UPDATE SKIP LOCKED`), que o SQLite usado em dev e nos testes não tem.

#### Opção C — Fila externa (Celery ou RQ com Redis)
- **Prós:** novas tentativas, prioridade e escala prontas.
- **Contras:** Redis e workers a mais; contraria a ADR-0012 e o PGP; desproporcional para o volume
  do portal (cerca de 1.800 recursos varríveis).

### Downloads do portal oficial

#### Opção 1 — Intervalo mínimo por host + espera no HTTP 429
- **Prós:** não provoca o bloqueio; quando ele vem, espera em vez de registrar erro.
- **Contras:** um lote do portal inteiro leva cerca de 1 h a mais (2 s × 1.800 downloads).

#### Opção 2 — Só esperar quando vier o 429
- **Prós:** mais rápido enquanto o portal não bloqueia.
- **Contras:** provoca bloqueios repetidos no portal do Estado.

#### Opção 3 — Manter (registrar erro e deixar o job diário tentar de novo)
- **Contras:** 1.583 erros num lote; o recurso só é varrido dias depois.

## Decisão
**Opção A** para o executor e **Opção 1** para os downloads.

- `POST /lgpd/varreduras` só enfileira (continua respondendo 202). O job
  `lgpd.fila_varredura` do worker (`GDA_LGPD_FILA_CRON`, padrão `* * * * *`) executa as
  pendentes até a fila esvaziar; pedidos feitos durante o ciclo entram no mesmo ciclo.
- Como o worker é o único executor e um ciclo nunca roda junto de outro, varredura em
  `executando` no início do ciclo é de um processo que caiu: vira `erro` ("Varredura interrompida:
  o worker foi reiniciado…") e o recurso volta à fila **uma vez**. Se o mesmo recurso já tinha sido
  interrompido antes (um arquivo que derruba o processo, por exemplo), fica só o erro, sem laço.
  Isso substitui a liberação após 12 h.
- O job incremental diário (PBI-34) só enfileira; quem executa é o job da fila.
- `CkanClient.baixar` espera `GDA_CKAN_DOWNLOAD_INTERVALO_S` (padrão 2 s) entre downloads do mesmo
  host e, no 429, espera o `Retry-After` ou 60 s, 2 min, 4 min… (máximo 15 min por espera) e tenta
  de novo até `GDA_CKAN_DOWNLOAD_ESPERAS_429` vezes (padrão 5). Vale para a varredura e para a
  prévia da anonimização.

## Consequências
- **Positivas:** reiniciar a API ou o worker não perde mais a fila; a tela pode pedir o portal
  inteiro (em pedidos de até `GDA_LGPD_VARREDURA_MAX_RECURSOS`) e o worker vai executando; o
  portal oficial não bloqueia mais os downloads.
- **Negativas e riscos:**
  - Início em até 1 min. A tela já mostra a varredura como "na fila" e atualiza sozinha.
  - Worker parado = fila parada. O painel mostra quantas estão em andamento; o worker sobe junto
    no `docker compose`.
  - Log do worker com o aviso de execução pulada a cada minuto durante ciclos longos (é o
    `max_instances=1` funcionando).
  - A prévia da anonimização (US26) continua em segundo plano na API e tem o mesmo risco de se
    perder num reinício. Fica como pendência do módulo `lgpd`; a mesma solução pode ser aplicada.
  - Um modelo local travado ainda pode prender um ciclo por horas (em 29/10 uma varredura levou
    5,2 h até o Ollama desistir). Tempo máximo por varredura é melhoria a decidir.

## Validação
Luiza (responsável pelo módulo): conferir o fluxo pedido → fila → worker na tela Riscos de Dados
Pessoais. Testes automatizados em `tests/test_lgpd.py` (retomada da interrompida, intervalo por
host e espera no 429).

## Revisões
| Data | Revisão | Autor |
|---|---|---|
