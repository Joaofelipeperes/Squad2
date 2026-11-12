# ADR-0028 — Ordenar e paginar as tabelas no navegador, e no banco só onde a lista cresce sem limite

| | |
|---|---|
| **Status** | Proposta |
| **Tipo** | Técnica |
| **Data da decisão** | 05/11/2026 (proposta; aguarda o aceite da coordenação) |
| **Data do registro** | 05/11/2026 |
| **Decisores** | Victor Hugo Benatti (coordenação) — a confirmar |
| **Consultados** | — (repassar ao João, responsável pela base comum, e à Luiza, tela LGPD) |
| **Origem** | Sessão de 05/11: pedido de paginação em todas as telas (50 por página, até 999, total junto da paginação) e ordenação por todas as colunas (card ClickUp 86e3xcapz) |
| **Afeta** | `frontend/src/shared/ui/tabela.tsx`; telas Datasets, Monitoramento do PDA, Atualizações, Organizações, Riscos de Dados Pessoais, Rastreabilidade, Log de acesso, Usuários e papéis; rotas `GET /rastreabilidade/eventos` e `GET /acesso/logs` |

## Contexto
As tabelas mostravam a lista inteira, sem ordenar por coluna, com um contador acima da tabela.
O pedido: paginação em todas as telas com o total de registros no rodapé, junto da paginação;
50 itens por página por padrão, com o usuário podendo mudar até 999; ordenar por qualquer coluna.

Tamanho das listas: o inventário tem ~446 datasets e ~48 órgãos; o PDA, algumas centenas de bases;
os achados LGPD, algumas centenas de arquivos. As APIs dessas telas já devolvem a lista inteira, e
os filtros e opções (ex.: órgãos presentes) são calculados sobre ela. Já a linha do tempo da
rastreabilidade e o log de acesso crescem sem limite (o log ganha uma linha por requisição), e a API
cortava em 300/2.000 e 200/5.000 linhas.

## Critérios de decisão
1. Atender ao pedido em todas as telas com o mesmo comportamento e a mesma aparência.
2. Não ler do banco milhares de linhas que não serão exibidas.
3. Pouca mudança nas APIs já usadas por outros módulos (relatórios, assistente, painel).
4. Manutenção simples pelo time da CGE-GO depois da Residência.

## Opções consideradas

### Opção A — Tudo no navegador
- **Prós:** nenhuma mudança nas APIs; ordenação instantânea; um único componente.
- **Contras:** rastreabilidade e log de acesso continuariam cortados por limite fixo (o total e as
  últimas páginas ficariam errados) ou trariam a tabela inteira a cada consulta.

### Opção B — Tudo no banco (`pagina`, `por_pagina`, `ordenar` em todas as rotas)
- **Prós:** uniforme; escala para qualquer tamanho.
- **Contras:** reescrever as consultas das telas cujas colunas são calculadas em Python (situação do
  PDA, última atualização real, situação por periodicidade, agrupamento de achados por arquivo); os
  filtros e opções hoje calculados sobre a lista inteira teriam de virar consultas próprias; mais
  risco de quebrar relatórios e painel que reutilizam esses serviços.

### Opção C — Híbrida: navegador onde a API já devolve a lista inteira; banco onde a lista cresce sem limite
- **Prós:** o pedido é atendido em todas as telas com o mesmo kit; só duas rotas mudam; nenhuma
  regra de negócio é reescrita; o total é sempre exato.
- **Contras:** dois modos de paginação para manter; se o inventário crescer muito (dezenas de
  milhares de datasets), as telas da opção navegador terão de migrar para o banco.

## Decisão
**Opção C.** Kit único em `frontend/src/shared/ui/tabela.tsx`:
- `useTabela(linhas, ordenadores, ordemInicial)` ordena e pagina no navegador (Datasets, PDA,
  Atualizações, Organizações, LGPD, Usuários e papéis). Texto sem diferenciar acento e maiúscula,
  números e datas pelo valor, vazios sempre no fim; a página volta para 1 quando muda filtro, ordem
  ou tamanho da página.
- `<ColunaOrdenavel>`: clique no título ordena; o segundo clique inverte (`aria-sort` para leitor de
  tela). Datas e quantidades começam pela maior.
- `<Paginacao>`: rodapé com o total, a faixa exibida, "Itens por página" (50; de 1 a 999) e
  primeira/anterior/próxima/última.
- Rastreabilidade: `GET /eventos` troca `limite` por `pagina` e `por_pagina` (1 a 999) com
  `offset/limit` no banco; a ordem continua a da linha do tempo (data, recentes ou antigos).
- Log de acesso: `GET /logs` passa a devolver `{total, pagina, por_pagina, ate_id, registros}`, com
  `ordenar` (qualquer coluna) e `direcao` no banco; `ate_id` fixa o fim da lista para que as
  requisições novas — inclusive as da própria navegação, que também entram no log — não desloquem
  as páginas seguintes. A exportação CSV pede até 5.000 linhas de uma vez.
- Tela Datasets: ordem padrão pela criação no CKAN (`metadata_created`), mais recente primeiro.

## Consequências
- **Positivas:** comportamento igual em todas as tabelas; total exato no rodapé; rastreabilidade e
  log sem corte silencioso; nenhuma mudança nas regras de negócio.
- **Negativas e riscos:** quem consumia `limite` em `/rastreabilidade/eventos` ou a lista em
  `/acesso/logs` precisa usar o novo formato (só o frontend usava); se o inventário crescer muito,
  migrar a tela correspondente para o modo banco (o componente `<Paginacao>` já serve aos dois).
  Tabelas de configuração pequenas (parâmetros, perfis de IA e do CKAN) e os painéis de resumo do
  Dashboard ficaram fora — não são listas de registros.

## Validação
Coordenação (Victor) aceita ou ajusta esta proposta; repassar ao João e à Luiza. Verificar com a
GEDA se 50 por página é um bom padrão no uso diário.

## Revisões
Melhorias e fatos novos que **não** mudam a decisão entram aqui. Se a decisão mudar, crie uma nova
ADR e marque esta como "Substituída por ADR-XXXX".

| Data | Revisão | Autor |
|---|---|---|
