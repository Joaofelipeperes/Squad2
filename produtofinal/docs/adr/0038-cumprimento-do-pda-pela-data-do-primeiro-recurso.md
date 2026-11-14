# ADR-0038 — Cumprimento do PDA compara a data do primeiro recurso publicado com o prazo do plano

| | |
|---|---|
| **Status** | Aceita |
| **Tipo** | Negócio |
| **Data da decisão** | 13/11/2026 |
| **Data do registro** | 13/11/2026 |
| **Decisores** | Paloma Peixoto (Gerente de Dados Abertos, GEDA — dona do negócio) |
| **Consultados** | Victor (coordenação), que levou a regra ao código |
| **Origem** | Mensagem da Paloma ao Squad 2 em 13/11/2026 e respostas às perguntas do time no mesmo dia |
| **Afeta** | Módulos `pda`, `painel`, `relatorios`, `assistente`; US6, US19; PBI-19 |

## Contexto
A situação da base prevista (PBI-19) usava o prazo do plano só para as bases **ainda não**
publicadas ("Em atraso", "Prazo vencido", "Próximo do prazo", "Em dia"). Base vinculada, ativa e com
recurso válido virava "Publicado", sem comparar a data de publicação com o prazo — e a "data de
publicação" mostrada era o `metadata_created` do dataset.

Em 13/11/2026 a Paloma definiu que, no indicador de cumprimento do PDA, o prazo do plano é o critério
para saber se a base foi publicada **dentro do prazo**. Perguntada pelo time, respondeu que:
- a publicação conta pelo **primeiro recurso**: só criar o dataset não significa nada;
- a base que já existia antes do plano e foi vinculada a um registro dele também é avaliada pelo
  prazo (publicada antes do prazo = no prazo).

## Critérios de decisão
1. Seguir a regra de negócio definida pela dona do negócio.
2. Data objetiva, vinda do CKAN, sem trabalho manual.
3. Não acusar atraso sem base para isso.

## Opções consideradas

### Opção A — `metadata_created` do dataset
- **Prós:** já era usado e está sempre preenchido.
- **Contras:** dataset criado sem recurso não é publicação (regra da GEDA); o órgão pode criar o
  dataset antes do prazo e só publicar o arquivo depois.

### Opção B — Criação no CKAN do primeiro recurso válido do dataset
- **Prós:** é a regra da GEDA; coerente com "Publicado" exigir recurso válido; usa o `created` do
  recurso que o inventário já coleta (`created_ckan`).
- **Contras:** o banco só conhece os recursos vistos desde a primeira coleta: se o órgão trocou o
  arquivo antes disso, a data fica mais recente que a real.

## Decisão
**Opção B.** `data_publicacao` = menor `created` (no CKAN) entre os recursos do dataset vinculado e
ativo que não são dicionário de dados — **inclusive os que já saíram do pacote** e continuam no
banco, porque trocar o arquivo depois não muda a data em que a base foi publicada (recurso excluído
logicamente não conta). Só vale para base com ao menos um recurso válido no pacote (senão é "Sem
recurso"). A situação "Publicado" se divide
em duas, comparando o dia dessa data (fuso de Brasília) com o prazo de abertura, inclusive:
- **"Publicado no prazo"** — até o prazo; também quando o plano não tem prazo ou o recurso não tem
  data (não há atraso a apontar);
- **"Publicado fora do prazo"** — depois do prazo.

Vale igual para base que já existia antes do plano. As demais situações (Sem recurso, Em atraso,
Prazo vencido, Próximo do prazo, Em dia, Não publicado) não mudam. "Bases publicadas" nos cartões
soma as duas; "Publicadas fora do prazo" aparece à parte no Dashboard, em Organizações e no
relatório por órgão.

## Consequências
- **Positivas:** o cumprimento do PDA passa a mostrar quem publicou com atraso, não só quem ainda
  não publicou; a data de publicação deixa de depender da criação do dataset.
- **Negativas e riscos:** o rótulo "Publicado" deixou de existir (filtros, links e relatórios usam os
  dois novos); bases importadas antes desta mudança não precisam de migração (a situação é calculada
  a cada consulta).

## Validação
Regra definida pela Paloma (GEDA) em 13/11/2026; conferir com ela os primeiros casos de "Publicado
fora do prazo" no PDA vigente.

## Revisões
| Data | Revisão | Autor |
|---|---|---|
