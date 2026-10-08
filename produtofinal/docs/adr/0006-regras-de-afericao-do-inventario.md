# ADR-0006 — Aferir atualização pelo recurso, vincular pelo ID do dataset e excluir o dicionário de dados

| | |
|---|---|
| **Status** | Aceita |
| **Tipo** | Negócio / Técnica |
| **Data da decisão** | 20/08/2026, refinada em 27/08 e 17/09 |
| **Data do registro** | 07/10/2026 (registro retroativo) |
| **Decisores** | Paloma Peixoto (regra de negócio) e Squad 2 |
| **Consultados** | Júnior Costa |
| **Origem** | Reunião 1 (20/08), Reunião 2 (27/08), Reunião 3 (17/09) |
| **Afeta** | Módulos `inventario`, `pda`, `atualizacoes`; US6, US9 |

## Contexto
Na Reunião 1 a GEDA mostrou o problema das **falsas atualizações**: a "última atualização" exibida
pelo CKAN muda quando qualquer metadado é editado, e não quando um recurso novo é publicado. O Júnior
explicou que o controle manual da GEDA já era feito pelo **ID** do registro. Na Reunião 2 a Paloma
confirmou que essa data é o `metadata_modified` do dataset e que os recursos têm datas próprias. Na
Reunião 3 ela propôs medir pela data do último recurso, **excetuando o dicionário de dados**, e
apontou a ressalva do recurso com período incompleto.

## Critérios de decisão
1. Refletir atualização real do conteúdo, não edição cadastral.
2. Vínculo estável mesmo quando o órgão edita o dataset.

## Opções consideradas — indicador de atualização

### `metadata_modified` do dataset (o que o portal mostra)
- **Prós:** um campo só, disponível na listagem.
- **Contras:** é a causa das falsas atualizações.

### `created` do recurso mais recente (proposta da Paloma em 17/09)
- **Prós:** capta a publicação de recurso novo.
- **Contras:** ignora a substituição do arquivo de um recurso existente.

### `last_modified` do recurso mais recente, com `created` como reserva
- **Prós:** capta recurso novo e substituição de arquivo.
- **Contras:** alguns recursos não têm `last_modified` (sinalizar — PBI-25).

### Hash do conteúdo do arquivo
- **Prós:** detecta mudança real de conteúdo.
- **Contras:** baixar ~2.900 arquivos a cada coleta; desproporcional.

## Opções consideradas — chave de vínculo PDA × CKAN
- **`name` ou título:** legível, mas editável pelo órgão; quebra o vínculo.
- **Similaridade de nome:** automática, mas gera falsos vínculos.
- **ID do dataset:** estável e já usado pela GEDA. Contra: exige uma planilha de vinculação inicial.

## Decisão
- Atualização = maior `last_modified` entre os recursos do dataset, com `created` como reserva
  sinalizada; `metadata_modified` nunca é indicador.
- Dicionário de dados fora da contagem.
- Vínculo e chave primária sempre pelo **ID do CKAN**.
- Recurso de período parcial não conta como atualização (PBI-78), e correção por anonimização feita
  pela própria solução também não (PBI-79, decisão de 22/09).

## Consequências
- **Positivas:** elimina o problema relatado pela GEDA.
- **Negativas e riscos:** o critério de identificação do dicionário de dados ainda é heurístico
  (PBI-11), aguardando confirmação da GEDA.

## Validação
Regras vindas da própria GEDA nas reuniões citadas; incorporadas ao Backlog v2 (US9).

## Revisões
| Data | Revisão | Autor |
|---|---|---|
| 22/09/2026 | Correções por anonimização excluídas do cálculo de atualização (PBI-79) | Squad 2 |
| 30/09/2026 | Regras implementadas em `inventario/regras.py`; ID do CKAN como PK das tabelas espelhadas | Victor |
