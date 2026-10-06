# ADR 0003 — Frontend modular sobre o CSS do Protótipo V1

**Status:** proposta · **Data:** 30/09/2026

## Contexto
O Protótipo V1 foi validado com a CGE-GO em 17/09 e é a referência oficial das telas (D5 do
Backlog v2). Reescrever o visual em outra biblioteca de componentes geraria divergência.

## Decisão
React + TypeScript + Vite. O CSS do protótipo é importado sem alteração; os componentes React
reproduzem a mesma marcação e classes. Cada tela é um módulo com manifesto (`index.ts`) e o
`registry.ts` gera menu, rotas e controle por permissão (ADR 0005). Fontes e ícones são servidos pelo próprio
build (sem CDN), o que funciona em redes do Estado com saída restrita.

## Consequências
A conferência final contra o protótipo (PBI-100) fica direta. Chart.js, já usado no protótipo,
continua disponível via `react-chartjs-2`.
