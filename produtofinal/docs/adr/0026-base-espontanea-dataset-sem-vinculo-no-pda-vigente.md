# ADR-0026 — Base espontânea é todo dataset ativo no portal sem vínculo pelo ID com o PDA vigente

| | |
|---|---|
| **Status** | Aceita |
| **Tipo** | Negócio |
| **Data da decisão** | 30/10/2026 |
| **Data do registro** | 30/10/2026 |
| **Decisores** | Humberto (responsável pelo módulo `pda`, Eixo 1) |
| **Consultados** | — (a validar com a GEDA; Paloma e Júnior pediram em 17/09 que as espontâneas também fossem monitoradas) |
| **Origem** | Sessão de trabalho de 30/10/2026, ao incluir as bases espontâneas no Dashboard |
| **Afeta** | Módulos `painel` e `pda`; US7 (PBI-16 a PBI-18, PBI-82); US19 |

## Contexto
A US7 pede separar as bases previstas no PDA das publicadas espontaneamente pelos órgãos, mas o
critério estava em aberto (`pda.md`, Pendências). A coluna `pda_base_prevista.classificacao`
(pda | espontanea) existe desde o início, mas é sempre "pda": uma base espontânea, por definição,
não está no plano, então não há linha do PDA para marcar. Com o vínculo pelo ID resolvido em lote
(ADR-0022 e "Importar IDs do CKAN"), o PDA vigente tem 333 de 409 bases vinculadas e o inventário
tem 446 datasets ativos.

## Critérios de decisão
1. Regra objetiva e verificável, sem depender do nome (ADR-0006: vínculo sempre pelo ID).
2. Funcionar já, sem nova tabela nem trabalho manual da GEDA.
3. Permitir a reclassificação manual depois (PBI-18), se a GEDA pedir.

## Opções consideradas

### Opção A — Calcular a partir do inventário: dataset ativo sem base do PDA vigente vinculada
- **Prós:** objetiva (pelo ID); acompanha automaticamente cada coleta e cada vínculo novo; nenhuma
  tabela nova.
- **Contras:** um dataset que deveria estar ligado a uma base, mas ainda não foi vinculado, aparece
  como espontâneo até alguém vincular; não há como marcar exceções.

### Opção B — Gravar a classificação (tabela de datasets espontâneos ou linhas "espontanea" em `pda_base_prevista`)
- **Prós:** permite reclassificar à mão e registrar exceções e histórico.
- **Contras:** exige migração, rotina para manter a lista em dia a cada coleta e decisão da GEDA
  sobre quem reclassifica; risco de a lista ficar desatualizada.

## Decisão
**Opção A.** Base espontânea = dataset **ativo** no portal (no escopo de órgão do usuário) que
**nenhuma base do PDA vigente** vincula pelo ID do CKAN. Sem PDA vigente, todos os datasets ativos
são espontâneos. Datasets fora do portal (excluídos ou privados) não contam.

## Consequências
- **Positivas:** o Dashboard mostra o total e os órgãos com mais espontâneas; cada vínculo novo
  reduz a contagem na hora.
- **Negativas e riscos:** enquanto houver bases do PDA sem vínculo, parte das "espontâneas" pode ser
  base prevista ainda não vinculada. A reclassificação manual (PBI-18) e o indicador separado de
  atualização PDA × espontânea (PBI-82) continuam pendentes; se vierem, a Opção B entra como nova ADR.

## Validação
Apresentar à Paloma (GEDA) junto com o Dashboard; ajustes viram revisões desta ADR.

## Revisões
| Data | Revisão | Autor |
|---|---|---|
