# ADR-0037 — Indicador de atualização sobre todas as bases publicadas, pela periodicidade do campo "Atualização" do CKAN

| | |
|---|---|
| **Status** | Aceita |
| **Tipo** | Negócio |
| **Data da decisão** | 13/11/2026 |
| **Data do registro** | 13/11/2026 |
| **Decisores** | Paloma Peixoto (Gerente de Dados Abertos, GEDA — dona do negócio) |
| **Consultados** | Victor (coordenação), que levou a regra ao código |
| **Origem** | Mensagem da Paloma ao Squad 2 em 13/11/2026 ("critérios para o funcionamento dos indicadores") |
| **Afeta** | Módulos `atualizacoes`, `painel`, `relatorios`, `inventario` (leitura do campo); US9, US10, US19, US7; PBI-27, PBI-28, PBI-82 |

## Contexto
A [ADR-0023](0023-situacao-de-atualizacao-pela-periodicidade-do-pda.md) calculava a situação de
atualização só das bases do **PDA vigente vinculadas** a um dataset, com a periodicidade da
**planilha do PDA**; a periodicidade declarada no CKAN (Opção B daquela ADR) foi descartada. Com isso
as bases espontâneas ficavam fora do indicador, as bases do PDA sem vínculo apareciam como
"Aguardando vínculo" e "Sem informação" juntava campo vazio, base sem data e dataset fora do portal.

Em 13/11/2026 a Paloma explicou que o vínculo com o PDA **não** pode ser condição para o indicador de
atualização e definiu quatro regras:
1. Base espontânea é a que não tem registro de vínculo na planilha de referência (a tabela do PDA com
   o ID único do CKAN — já é o critério da [ADR-0026](0026-base-espontanea-dataset-sem-vinculo-no-pda-vigente.md)).
2. A periodicidade vem **exclusivamente** do campo customizado "Atualização" do dataset no CKAN, seja
   a base do PDA ou espontânea.
3. "Não possui atualização periódica" é uma declaração **válida** do órgão.
4. Campo vazio ou com valor inválido é **"Periodicidade não informada"**: metadado obrigatório não
   conforme, que não pode ser confundido com o item 3.

Na cópia de metadados do portal do repositório (`metadados_ckan_goias.json`, 445 datasets), o campo
tem Mensal 203, Anual 178, Semestral 32, "Não possui atualização periódica" 17, Trimestral 6,
Bimestral 5, Quadrimestral, Bienal e Quadrienal 1 cada, e 1 dataset sem o campo; vários valores
têm espaço ou tabulação sobrando e uma chave aparece como "Atualização " (com espaço).

## Critérios de decisão
1. Seguir a regra de negócio definida pela dona do negócio.
2. O indicador refletir todas as bases publicadas no portal.
3. A ausência de informação nunca ser lida como ausência de periodicidade.
4. Uma só fonte de periodicidade por base.

## Opções consideradas

### Opção A — Manter a ADR-0023 (PDA vigente, só vinculadas)
- **Prós:** nenhuma mudança; a periodicidade é o compromisso do plano.
- **Contras:** contraria a regra da GEDA; deixa as espontâneas e as bases sem vínculo fora do
  indicador; mistura "sem informação" com "sem periodicidade".

### Opção B — Todas as bases publicadas, periodicidade só do campo "Atualização" do CKAN
- **Prós:** é a regra da GEDA; cobre todo o portal; não depende do vínculo; um valor por base, o que
  o próprio órgão declara no portal.
- **Contras:** o campo é preenchido pelo órgão e pode estar vazio ou fora do domínio — tratado como
  não conformidade explícita, não como dado faltante silencioso.

### Opção C — CKAN quando preenchido, PDA como reserva
- **Prós:** menos bases sem periodicidade.
- **Contras:** duas fontes para a mesma base; esconde a não conformidade do metadado, que a GEDA quer
  ver.

## Decisão
**Opção B.**
- **Universo:** todo dataset **ativo** no portal (publicado), no escopo de órgão do usuário. O vínculo
  com o PDA vigente só identifica o tipo de base ("Prevista no PDA" × "Espontânea", ADR-0026).
- **Periodicidade:** texto do extra "Atualização" (chave comparada sem acento, maiúsculas e espaços),
  sem fallback para outras chaves. Valor aceito sem diferenciar maiúsculas, acentos, espaços e
  pontuação: Diária, Semanal, Quinzenal, Mensal, Bimestral, Trimestral, Quadrimestral, Semestral,
  Anual, Bienal, Quadrienal, Quinquenal (prazos da ADR-0023, sem tolerância, alerta a partir de 80%).
- **Situações**, nesta ordem de precedência:
  1. "Sem atualização periódica" — o campo diz "Não possui atualização periódica". Válida, sem
     prazo: não é atraso nem não conformidade.
  2. "Periodicidade não informada" — campo vazio, ausente ou com outro valor (inclusive textos como
     "Eventual" ou "Mensal/Anual"). Não conforme, vale mesmo se a base tiver data de atualização.
  3. "Sem data de atualização" — periodicidade válida, mas nenhum recurso válido com data.
  4. "Atrasado" / "Próximo do vencimento" / "Atualizado" — como na ADR-0023.
- **Percentual por órgão e índice de atenção (ADR-0030):** só as situações com prazo (item 4).
  "Sem atualização periódica" fica fora "por hora" (Paloma, 13/11/2026); "Periodicidade não
  informada" também fica fora do percentual e aparece à parte.
- A periodicidade da planilha do PDA continua guardada e exibida na tela do PDA, mas não entra no
  indicador de atualização.

## Consequências
- **Positivas:** o Monitoramento de Atualizações, o Dashboard, Organizações e os relatórios passam a
  cobrir as ~445 bases publicadas; o órgão sem o campo preenchido aparece como não conforme (cartão
  e alerta próprios); deixa de existir "Aguardando vínculo" no indicador.
- **Negativas e riscos:** o resultado muda bastante em relação à ADR-0023 (outra fonte e outro
  universo) — avisar a GEDA ao publicar. Valores novos no domínio do CKAN (ex.: "Semanal" com outra
  grafia) caem em "Periodicidade não informada" até serem incluídos na regra
  (`atualizacoes.regras.periodicidade_ckan`). Ainda não considera recurso parcial (PBI-78) nem
  correções por anonimização (PBI-79).

## Validação
Regra definida pela própria Paloma (GEDA) em 13/11/2026; conferir os números com ela na próxima
reunião. A inclusão de "Sem atualização periódica" no percentual pode ser revista depois ("por hora").

## Revisões
| Data | Revisão | Autor |
|---|---|---|
