# ADR-0012 — Executar a coleta diária num processo agendador próprio (APScheduler)

| | |
|---|---|
| **Status** | Aceita |
| **Tipo** | Técnica |
| **Data da decisão** | 30/09/2026 |
| **Data do registro** | 07/10/2026 (registro retroativo) |
| **Decisores** | Victor Hugo Benatti |
| **Consultados** | — |
| **Origem** | Sessão de 30/09 |
| **Afeta** | Módulo `inventario`; `docker-compose.yml`; US23 |

## Contexto
A coleta do CKAN roda todo dia (padrão 03:00) e também sob demanda pelo botão "Atualizar dados". Em
31/08 a SECTI citou que usa Airflow em seus fluxos.

## Critérios de decisão
1. Uma execução por vez (sem duplicar coletas).
2. Infraestrutura leve.
3. Agendamento declarado junto do código de cada módulo.

## Opções consideradas

### Cron do sistema operacional chamando a CLI
- **Prós:** nenhuma dependência.
- **Contras:** configuração fora do repositório; depende de acesso ao servidor.

### APScheduler dentro do processo da API
- **Prós:** um processo a menos.
- **Contras:** com vários workers web, cada um agenda a mesma coleta.

### APScheduler em processo próprio (`python -m app.worker`)
- **Prós:** uma execução garantida; jobs declarados por módulo (`JobSpec`); sem fila externa.
- **Contras:** um processo a mais para manter no ar.

### Celery + Redis
- **Prós:** filas, novas tentativas e escala.
- **Contras:** Redis e workers a mais; desproporcional para um job diário.

### Airflow (usado pela SECTI)
- **Prós:** padrão já conhecido pela SECTI.
- **Contras:** infraestrutura pesada; acoplaria a solução a um ambiente que o time não controla.

## Decisão
APScheduler em processo próprio, com `max_instances=1` e bloqueio de coleta simultânea no banco.

## Consequências
- **Positivas:** simples e previsível.
- **Negativas e riscos:** se a SECTI exigir Airflow na implantação, o job é uma função sem dependência
  do agendador e pode ser chamado por uma DAG.

## Validação
A confirmar na decisão de implantação (PBI-102).

## Revisões
| Data | Revisão | Autor |
|---|---|---|
