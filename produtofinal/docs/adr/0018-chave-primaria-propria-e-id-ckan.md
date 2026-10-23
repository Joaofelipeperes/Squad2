# ADR-0018 — Usar chave primária própria nas tabelas espelhadas do CKAN, com o ID do CKAN em `id_ckan`

| | |
|---|---|
| **Status** | Aceita |
| **Tipo** | Técnica |
| **Data da decisão** | 21/10/2026 |
| **Data do registro** | 21/10/2026 |
| **Decisores** | Victor Hugo Benatti (coordenação) |
| **Consultados** | — |
| **Origem** | Sessão de trabalho de 21/10/2026 (vínculo PDA → dataset → organização) |
| **Afeta** | `inventario` (`organizacao`, `dataset`, `recurso`, `dataset_snapshot`, coleta e tela Datasets); chaves estrangeiras em `acesso` (`usuario.orgao_id`), `pda` (`pda_base_prevista`), `lgpd` (`lgpd_achado`, `lgpd_correcao`); `painel`, `assistente`, `metadados`; telas Datasets, PDA, Organizações e Usuários; `docs/banco/convencoes.md` §2; migração `f6c3a8d2b1e7` |

## Contexto
As tabelas espelhadas do CKAN (`organizacao`, `dataset`, `recurso`) usavam o ID do CKAN como chave
primária (`ckan_id varchar(64)`), conforme `docs/banco/convencoes.md` §2. Toda chave estrangeira
para essas tabelas (`pda_base_prevista.dataset_id`, `dataset.organizacao_id`, `usuario.orgao_id`…)
guardava, portanto, um identificador controlado pelo CKAN.

Ao trabalhar o vínculo entre base do PDA, dataset e organização, a coordenação decidiu que as
tabelas da solução precisam de identidade própria: um registro deve poder existir e ser referenciado
sem depender de um valor gerado pelo CKAN (por exemplo, organização ou dataset cadastrado antes de
existir no portal) e as relações internas não devem mudar se o CKAN trocar ou recriar um registro.
A regra de negócio do vínculo continua valendo: o casamento com o portal é sempre pelo **ID do
CKAN**, nunca pelo `name` (ADR-0006, PBI-13).

## Critérios de decisão
1. Identidade dos registros independente do CKAN.
2. Manter o vínculo com o portal pelo ID do CKAN (nunca pelo `name`).
3. Preservar os dados já coletados e os vínculos já feitos (PDA, usuários de órgão, achados LGPD).
4. Funcionar em PostgreSQL e SQLite (ADR-0013).

## Opções consideradas

### Opção A — Manter o ID do CKAN como chave primária (situação anterior)
- **Prós:** nenhuma migração; chave natural, legível nos logs e na API.
- **Contras:** a identidade do registro depende do CKAN; não comporta registros sem ID do CKAN;
  toda FK guarda um valor externo.

### Opção B — Chave primária inteira própria (`id`) e ID do CKAN em `id_ckan` (único, opcional)
- **Prós:** identidade e relações internas sob controle da solução; registros sem CKAN possíveis
  (`id_ckan` nulo); FKs inteiras, menores e uniformes com as tabelas próprias; mesma convenção
  (`id` inteiro) em todas as tabelas.
- **Contras:** migração com tradução de todas as referências; a coleta passa a casar pelo
  `id_ckan` (consulta) em vez de `merge` pela PK; a API passa a expor o `id` interno, e os links
  para o portal usam o `id_ckan`.

### Opção C — UUID gerado pela solução como chave primária
- **Prós:** identidade própria e geração fora do banco.
- **Contras:** destoa das demais tabelas (inteiro); chaves maiores e menos legíveis, sem ganho
  para uma aplicação com um único banco.

## Decisão
Opção B. Em `organizacao`, `dataset` e `recurso`: `id` inteiro autoincremento como chave primária e
`id_ckan varchar(64)` único e opcional com o ID do CKAN. Todas as chaves estrangeiras passam a
apontar para o `id` (`dataset.organizacao_id`, `recurso.dataset_id`, `usuario.orgao_id`,
`pda_base_prevista.organizacao_id` e `.dataset_id`, `lgpd_achado.recurso_id`,
`lgpd_correcao.recurso_id`); a referência lógica `dataset_snapshot.dataset_id` também.
A coleta casa organização, dataset e recurso pelo `id_ckan`; o vínculo das bases do PDA continua
resolvido pelo ID do CKAN (o `name` serve só para encontrá-lo) e gravado como o `id` do dataset.
A API e as telas usam o `id`; o ID do CKAN aparece como `id_ckan` (e `dataset_id_ckan` nas bases)
e é o que compõe os links para o portal.

## Consequências
- **Positivas:** relações internas estáveis e independentes do CKAN; convenção única de chave.
- **Negativas e riscos:** migração `f6c3a8d2b1e7` reescreve as três tabelas e as referências —
  testada em SQLite, PostgreSQL e numa cópia do banco de desenvolvimento (dados e vínculos
  preservados); o downgrade é recusado se existir registro sem `id_ckan`. URLs e contratos JSON
  mudaram (`ckan_id` → `id`/`id_ckan`); o frontend foi ajustado no mesmo commit. A CLI
  `criar-usuario --orgao` passa a aceitar o `id_ckan` ou o `name` da organização.

## Validação
Revisão do time (João e Humberto, donos de `inventario` e `pda`) na próxima sincronização.

## Revisões

| Data | Revisão | Autor |
|---|---|---|
