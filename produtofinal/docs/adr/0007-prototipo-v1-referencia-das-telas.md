# ADR-0007 — Adotar o Protótipo V1 como referência oficial das telas

| | |
|---|---|
| **Status** | Aceita |
| **Tipo** | Escopo |
| **Data da decisão** | 22/09/2026 (D5), após validação da CGE-GO em 17/09 |
| **Data do registro** | 07/10/2026 (registro retroativo; também consta no Backlog v2, aba Alterações v1→v2) |
| **Decisores** | Squad 2 (daily de 22/09) |
| **Consultados** | Paloma Peixoto e Júnior Costa (Reunião 3, 17/09) |
| **Apoio de IA** | O protótipo foi gerado com IA a partir de um prompt do time (Luiza/Humberto) |
| **Origem** | Reunião 3 (17/09); daily de 22/09 |
| **Afeta** | Todas as telas; ADR-0003; PBI-66, PBI-100 |

## Contexto
Na Reunião 3 o time apresentou um protótipo HTML com dados simulados. A CGE-GO aprovou e pediu
ajustes: mais gráficos de evolução no dashboard (Júnior), separar prazo de abertura de atualização,
filtros por órgão. Na daily de 22/09 o time decidiu seguir com ele.

## Critérios de decisão
1. Reduzir o risco de construir algo que o cliente não reconhece.
2. Ter um norte comum para os dois eixos.

## Opções consideradas

### Construir a partir dos requisitos, sem protótipo de referência
- **Prós:** liberdade de desenho.
- **Contras:** risco alto de retrabalho; cliente só vê o resultado tarde.

### Fazer um novo protótipo em ferramenta de design (Figma)
- **Prós:** mais refinado.
- **Contras:** tempo extra e nova rodada de validação.

### Adotar o Protótipo V1 validado, com as ressalvas como critérios de aceite
- **Prós:** já aprovado pelo cliente; ressalvas viram critérios objetivos.
- **Contras:** foi gerado como página única com dados simulados; precisa ser reestruturado.

## Decisão
Protótipo V1 como referência; ressalvas de 17/09 viram critérios de aceite no Backlog v2.

## Consequências
- **Positivas:** fundamentou a decisão de reaproveitar o CSS (ADR-0003).
- **Negativas e riscos:** dados simulados podem esconder casos reais difíceis; mitigado pela coleta real.

## Validação
CGE-GO em 17/09.

## Revisões
| Data | Revisão | Autor |
|---|---|---|
| 30/09/2026 | Protótipo versionado em `prototipos/prototipoV1.html` e reaproveitado no frontend | Victor / Claude |
