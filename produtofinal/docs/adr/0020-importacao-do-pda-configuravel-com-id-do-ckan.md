# ADR-0020 — Importar o PDA vinculando pelo ID do CKAN da planilha, com leitura configurável guardada no navegador

| | |
|---|---|
| **Status** | Aceita |
| **Tipo** | Técnica |
| **Data da decisão** | 23/10/2026 |
| **Data do registro** | 23/10/2026 |
| **Decisores** | Victor Hugo Benatti (coordenação) |
| **Consultados** | — |
| **Origem** | Sessão de trabalho de 23/10/2026 (importação da tabela fato do PDA com `ID_UNICO`) |
| **Afeta** | `pda` (leitura da planilha, importação, Atualizar vínculos, formulário de base, modal Importar PDA); `pda_base_prevista.dataset_id_ckan_planilha` (migração `b9d4e6f2a7c1`); `shared/ui/Modal.tsx` (variante larga); US6, PBI-12, PBI-13 |

## Contexto
O PDA passou a chegar como uma "tabela fato" (`SIGLA;ORGAO;NOME_PDA;NOME_DA_BASE_CKAN;ID_UNICO;
PERIODICIDADE;PREVISAO_DE_ABERTURA`) em que cada base já traz o **ID do dataset no CKAN**
(`ID_UNICO`) — ou "Não encontrado" quando a base ainda não foi publicada. Até aqui a importação só
vinculava pela coluna "Disponível no Portal" (link → name → ID) e reconhecia as colunas por uma
lista fixa de nomes; a planilha 2025-2027 da GEDA não tinha essa coluna e nenhuma base era vinculada.
O vínculo pelo ID é o que permite acompanhar cada base nos relatórios e painéis (ADR-0006, ADR-0018).

Os arquivos podem vir com outros nomes de coluna, título acima do cabeçalho ou outro separador, e a
coordenação pediu um modal de importação com uma aba de configuração (colunas da tabela, início da
leitura e delimitador, com "Salvar Config."), no modelo de outro sistema já usado pela equipe.

## Critérios de decisão
1. Vincular pelo ID do CKAN, nunca pelo nome (ADR-0006, PBI-13).
2. Aceitar variações do arquivo sem mudar código.
3. Continuar lendo as planilhas antigas da GEDA (sem quebrar importações existentes).
4. Simplicidade: entrega rápida, sem infraestrutura nova.

## Opções consideradas

### Vínculo

#### Opção A — Coluna de ID do CKAN com prioridade sobre o link, e ID pendente guardado na base
- **Prós:** vínculo direto e exato pelo ID; ID ainda não coletado fica pendente e é resolvido pelo
  mesmo ID depois da coleta ("Atualizar vínculos"); o link continua valendo para planilhas sem ID.
- **Contras:** nova coluna em `pda_base_prevista` (`dataset_id_ckan_planilha`) e migração.

#### Opção B — Usar o ID só quando o dataset já está no inventário (sem guardar o ID pendente)
- **Prós:** nenhuma mudança de tabela.
- **Contras:** ID ainda não coletado se perde; a base vira "sem vínculo" e precisa ser vinculada à
  mão ou reimportada depois da coleta.

### Onde guardar a configuração da leitura

#### Opção C — No navegador (`localStorage`) de quem importa
- **Prós:** nenhuma tabela, rota ou permissão nova; cada pessoa ajusta ao arquivo que recebe; a
  configuração vai junto com o arquivo no envio (campo `config`), então o backend continua sem estado.
- **Contras:** não é compartilhada pela equipe; some ao trocar de navegador ou limpar os dados do site.

#### Opção D — No banco, uma configuração para toda a equipe (tabela própria no módulo `pda`)
- **Prós:** uma configuração única para todos, auditada.
- **Contras:** tabela, migração, rotas e permissão novas para um ajuste que muda pouco.

#### Opção E — Na tabela `parametro`
- **Prós:** reaproveita a tabela de valores editáveis.
- **Contras:** mistura um ajuste técnico de leitura com os parâmetros de negócio da tela Parâmetros.

## Decisão
**A + C.** A coluna de ID do CKAN tem prioridade: ID → `Dataset.id_ckan` → grava `Dataset.id`
(resolvido); ID sem dataset → pendente, guardado em `dataset_id_ckan_planilha` e resolvido pelo ID;
sem ID, vale o link do portal como antes. Só UUID conta como ID ("Não encontrado" e vazio = sem ID;
outro texto = sem ID com aviso no resumo).

A leitura aceita uma configuração opcional (`ConfigLeitura`): nome da coluna de cada campo, linha do
cabeçalho ("Início da leitura"; os dados começam na linha seguinte) e delimitador do CSV. Campo a
campo, vale a coluna configurada e, se ela não estiver no arquivo, os nomes usuais — assim a
configuração padrão (tabela fato) ainda lê a planilha da GEDA. A configuração é editada na aba
Configuração do modal e guardada no navegador (opção escolhida pelo decisor); a importação envia a
que está na tela, salva ou não.

## Consequências
- **Positivas:** a tabela fato é importada já vinculada (no inventário local, 345 de 345 IDs
  resolvidos e todos os órgãos casados pela evidência do vínculo); planilhas com outros nomes de
  coluna, título acima do cabeçalho ou separador "|" são aceitas sem mudança de código; as
  importações sem configuração continuam idênticas.
- **Negativas e riscos:** a configuração não é compartilhada — quem importa em outra máquina parte
  do padrão (que já é o formato da tabela fato). Se a equipe precisar de uma configuração única,
  levar para o banco (opção D) em nova ADR. PDAs já importados sem ID não são revinculados: é preciso
  reimportar com a coluna.

## Validação
Confirmar com a GEDA (Paloma) que a tabela fato com `ID_UNICO` é o formato oficial de envio do PDA.

## Revisões
| Data | Revisão | Autor |
|---|---|---|
