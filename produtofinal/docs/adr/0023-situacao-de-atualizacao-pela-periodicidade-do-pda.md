# ADR-0023 — Situação de atualização calculada pela periodicidade do PDA vigente, sem tolerância

| | |
|---|---|
| **Status** | Aceita |
| **Tipo** | Negócio |
| **Data da decisão** | 28/10/2026 |
| **Data do registro** | 28/10/2026 |
| **Decisores** | Humberto (responsável pelo módulo `atualizacoes`, Eixo 1) |
| **Consultados** | — (a validar com a GEDA na próxima reunião) |
| **Origem** | Sessão de trabalho de 28/10/2026, ao implementar o gráfico "Status das atualizações" do Dashboard |
| **Afeta** | Módulos `atualizacoes` e `painel`; US10 (PBI-27, PBI-28); US19 (PBI-56) |

## Contexto
O protótipo V1 mostra, no Dashboard, o "Status das atualizações" (Atualizado, Próximo do vencimento,
Atrasado, Sem informação) e o cartão "Atualizações em atraso". O contrato
`atualizacoes.situacao_periodicidade` (PBI-27/28) estava em esqueleto porque faltava a regra: prazo
de cada periodicidade, tolerância, de onde vem a periodicidade e o que fazer com valores sem prazo
(Eventual, Estática, Múltipla, sem informação). A última atualização real já era definida pela
ADR-0006 (maior `last_modified` dos recursos, sem dicionário de dados).

No PDA vigente em 28/10/2026 (409 bases): Mensal 209, Anual 134, Semestral 35, Eventual 10,
Trimestral 7, Estática 5, Bimestral 4, Quadrimestral, Bienal, Quadrienal, Múltipla e Sem informação
com 1 cada.

## Critérios de decisão
1. Regra simples de explicar à GEDA e aos órgãos.
2. Não acusar atraso sem base para isso.
3. Uma só fonte de periodicidade por base.

## Opções consideradas

### Opção A — Periodicidade do PDA vigente, sem tolerância, alerta a partir de 80% do prazo
- **Prós:** a periodicidade é o compromisso assumido pelo órgão no plano e é a mesma da tela do PDA;
  regra direta (Mensal = 30 dias); o alerta proporcional serve para qualquer periodicidade (Mensal:
  últimos 7 dias; Anual: últimos 74).
- **Contras:** só avalia bases vinculadas a um dataset; atraso de um dia já conta.

### Opção B — Periodicidade declarada no CKAN (`extras.Atualização`)
- **Prós:** cobre todos os datasets do portal, vinculados ou não.
- **Contras:** campo livre, nem sempre preenchido, e pode divergir do PDA — dois compromissos para a
  mesma base.

### Opção C — Tolerância (ex.: +10%) e janela fixa de alerta (ex.: 30 dias, como o prazo do PDA)
- **Prós:** absorve pequenas variações; um só número para o alerta.
- **Contras:** mais um número a justificar; com janela fixa, Mensal ficaria quase sempre "próximo" e
  Anual avisaria tarde.

## Decisão
- Periodicidade: a da base no **PDA vigente** (opção A). Bases sem vínculo ficam fora do cálculo
  ("Aguardando vínculo"); dataset fora do portal → "Sem informação".
- Prazo em dias: Diária 1, Semanal 7, Quinzenal 15, **Mensal 30**, Bimestral 60, Trimestral 90,
  Quadrimestral 120, Semestral 180, Anual 365, Bienal 730, Quadrienal 1.460, Quinquenal 1.825;
  **sem tolerância**.
- Com `d` = dias desde a última atualização real: `d > prazo` → **Atrasado**; `d ≥ 80% do prazo` →
  **Próximo do vencimento**; senão **Atualizado**.
- **Eventual** e **Estática** → "Sem periodicidade definida" (não contam como atrasadas nem como em
  dia). **Múltipla** → a menor periodicidade citada no texto da planilha (a mais exigente). **Sem
  informação**, ou base sem data de atualização → "Sem informação".

## Consequências
- **Positivas:** o Dashboard volta ao formato do protótipo e o cartão "Atualizações em atraso" passa a
  ter número; a regra é uma função pura (`atualizacoes/regras.py`), reaproveitável numa extensão CKAN.
- **Negativas e riscos:** sem tolerância, atrasos de poucos dias aparecem como "Atrasado"; se a GEDA
  pedir margem, basta alterar a regra (nova revisão). A periodicidade do CKAN não é usada. Ainda não
  considera recurso parcial (PBI-78) nem correções por anonimização (PBI-79).

## Validação
Apresentar à Paloma (GEDA) na próxima reunião; ajustes viram revisões desta ADR.

## Revisões
| Data | Revisão | Autor |
|---|---|---|
| 28/10/2026 | Renumerada de ADR-0020 para ADR-0023 no merge com a `desenvolvimento` (a ADR-0020 de lá é a do Claude Haiku no Assistente; 0021 e 0022 também já existiam) | Humberto |
