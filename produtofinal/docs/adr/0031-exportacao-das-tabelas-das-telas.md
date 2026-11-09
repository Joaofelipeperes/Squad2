# ADR-0031 — Tabelas das telas exportadas para PDF e Excel pelo backend, a partir das linhas que a tela mostra

| | |
|---|---|
| **Status** | Proposta |
| **Tipo** | Técnica |
| **Data da decisão** | 06/11/2026 |
| **Data do registro** | 06/11/2026 |
| **Decisores** | Humberto (proposta; a confirmar) |
| **Consultados** | Victor (coordenação), que lembrou o pedido da Paloma na reunião de 05/11/2026 |
| **Origem** | Pedido da GEDA (Paloma) na apresentação de 29/10/2026; reunião do Squad 2 de 05/11/2026 |
| **Afeta** | `relatorios` (rota nova), telas Monitoramento do PDA (`pda`), Monitoramento de Atualizações (`atualizacoes`), Organizações (`painel`) e Datasets (`inventario`); `shared/ui/ExportarTabela.tsx`, `shared/api/client.ts`, `shared/ui/tabela.tsx`; US20 |

## Contexto
A Paloma pediu exportação para PDF e Excel "em cada tabela do sistema", para não ter de copiar os
dados para a planilha dela à mão. A tela Relatórios já gera PDF (reportlab, ADR-0027) e Excel
(openpyxl) no backend, mas só para os relatórios do catálogo. As tabelas das telas têm filtros e
ordenação próprios; parte dos filtros é aplicada no backend (Datasets, PDA, Atualizações) e parte no
navegador (Organizações), e a ordenação e a paginação são sempre no navegador (ADR-0028). O arquivo
precisa refletir o que a pessoa está vendo: mesmos filtros, mesma ordem, todas as páginas.

## Critérios de decisão
1. O arquivo bate com a tela (filtros, ordem, colunas e textos).
2. Sem dependência nova (PGP: ferramentas gratuitas, infraestrutura leve) e mesmo visual dos
   relatórios.
3. Pouco código por tela, para estender a outras tabelas depois.
4. Não ampliar acesso: nada sai no arquivo que o usuário não veja na tela.

## Opções consideradas

### Opção A — Gerar no navegador (SheetJS + jsPDF)
- **Prós:** sem ida ao servidor; o arquivo sai exatamente das linhas da tela.
- **Contras:** duas dependências novas no frontend (peso do bundle, licença e manutenção a avaliar);
  o PDF ficaria com visual diferente do dos relatórios (cabeçalho, paginação, quebra de texto).

### Opção B — Uma rota de exportação por tela, refazendo a consulta no backend
- **Prós:** o servidor garante o conteúdo (não depende do que o navegador envia).
- **Contras:** repetir no backend os filtros que hoje são do navegador (Organizações) e a ordenação
  de cada tabela; quatro rotas e quatro conjuntos de colunas a manter em sincronia com as telas.

### Opção C — Rota genérica que recebe as linhas que a tela mostra e só gera o arquivo
- **Prós:** reaproveita o gerador dos relatórios (mesmo PDF e Excel, sem dependência nova); o
  arquivo é exatamente a tela, com os filtros ativos no cabeçalho do PDF; cada tela só declara as
  colunas; o backend não consulta o banco, então não há como sair dado que a tela não mostrou.
- **Contras:** o conteúdo vem do navegador — quem quiser pode montar um arquivo com dados
  inventados (como já pode num Excel qualquer); o tráfego dobra (a lista vai e volta), com limite de
  linhas na rota.

## Decisão
**Opção C** (proposta). `POST /api/v1/relatorios/tabela/exportar` recebe `{titulo, filtros,
colunas, linhas, formato: pdf|xlsx}` e devolve o arquivo `<titulo>-<aaaa-mm-dd>.<formato>`; exige
`relatorios.exportar`; até 30 colunas e 20 mil linhas, toda linha com o mesmo número de colunas do
cabeçalho (senão 422). No frontend, `<ExportarTabela>` (botões **Excel** e **PDF**, ao lado de
"Limpar filtros") monta as linhas com os valores formatados como na tela, a partir de
`useTabela().todas` (todas as páginas, na ordem da tela), e descreve os filtros ativos.

## Consequências
- **Positivas:** as quatro telas pedidas exportam com uma linha de código cada; outras tabelas
  (LGPD, Rastreabilidade, Usuários) podem usar o mesmo componente.
- **Negativas e riscos:** o arquivo não é "oficial" no sentido de conferido pelo servidor — para isso
  continuam os relatórios do catálogo. O PDF em paisagem fica apertado em tabelas com muitas colunas.

## Validação
Confirmar a abordagem com o time (Victor, João — dono da base comum e dos relatórios) e mostrar à
Paloma no próximo checkpoint, com uma exportação de cada tela.

## Revisões
| Data | Revisão | Autor |
|---|---|---|
