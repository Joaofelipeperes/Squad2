# Módulo `relatorios` — Relatórios e exportação

| | |
|---|---|
| **Status** | Implementado (6 relatórios do protótipo, prévia e exportação XLSX/CSV/PDF) |
| **Responsável** | João |
| **User stories** | US20 (PBI-60, PBI-61, PBI-77) |
| **Backend** | `backend/app/modules/relatorios/` |
| **Frontend** | `frontend/src/modules/relatorios/` |
| **Última atualização** | 05/11/2026 |

## Propósito
Substitui o controle manual em planilhas da GEDA por relatórios exportáveis com as mesmas colunas.

## Telas
| Tela | Rota | Permissão para ver | Ações na tela (permissão) |
|---|---|---|---|
| Relatórios | `/relatorios` | `relatorios.acessar` | Gerar relatório (prévia, `relatorios.acessar` + permissão do módulo de origem); **Relatório de um órgão** (escolher o órgão e os relatórios); exportar Excel/CSV/PDF (`relatorios.exportar`) |

Referência visual: `#screen-reports` (6 relatórios do protótipo, PBI-77). Cada cartão abre um modal
com a prévia (até 50 linhas, total de linhas e referência, ex.: o PDA vigente). A exportação leva o
relatório inteiro. Os cartões mostrados dependem do perfil: só aparecem os relatórios cujo módulo de
origem o usuário acessa.

**Relatório de um órgão** (`RelatorioOrgao.tsx`, painel acima dos cartões): o usuário escolhe o
órgão (lista do escopo de órgão dele) e marca quantos relatórios quiser ("Marcar todos"). Na
marcação, o "Relatório por Órgão" (o comparativo de todos os órgãos, que continua como cartão)
aparece como **Resumo do órgão** ("Indicador | Valor"): primeira opção, **já marcada**, que o
usuário pode desmarcar; quando marcado, abre o documento. É preciso marcar ao menos um item.
**Gerar relatório** abre um
modal com uma seção por item (prévia de 10 linhas de cada) e as exportações **PDF** (um documento
com seções), **Excel** (uma aba por seção) e **CSV** (as seções em sequência, cada uma com o
título). Com o órgão escolhido, cada relatório vem só com as linhas dele e sem as colunas
Sigla/Órgão (o órgão vai no título). Depois do resumo, as seções seguem a ordem do catálogo.

O mesmo fluxo existe no **detalhe do órgão em Organizações** (botão **Gerar relatório**, só com
`relatorios.acessar` e quando o órgão tem organização no portal): `GerarRelatorioOrgaoModal` já
vem com o órgão escolhido, mostra a mesma marcação e abre a mesma prévia/exportação.

| Relatório (`id`) | Módulo de origem (permissão exigida) | Conteúdo |
|---|---|---|
| Cumprimento do PDA (`pda`) | pda (`pda.acessar`) | Bases do PDA vigente: órgão, situação, prazo, periodicidade, vínculo, dataset, recursos válidos, formatos, publicação |
| Atualizações (`atualizacoes`) | atualizacoes (`atualizacoes.acessar`) | Bases vinculadas do PDA vigente com atualização **Atrasada** ou **Próxima do vencimento** (ADR-0023); atrasadas primeiro |
| Dados Pessoais (`lgpd`) | lgpd (`lgpd.acessar`) | Achados com status `revisar`, por prioridade e confiança; só localização e tipo, nunca o valor |
| Por Órgão (`orgaos`) | painel (`painel.acessar`) | Mesmos indicadores da tela Organizações, com Riscos LGPD e recursos varridos (só com `lgpd.acessar`) e o índice de atenção (faixa e valor, ADR-0030) |
| Datasets sem Recurso (`sem-recurso`) | inventario (`inventario.acessar`) | Datasets ativos sem recurso válido (PBI-51) |
| Formatos não Abertos (`formatos`) | inventario (`inventario.acessar`) | Recursos atuais fora do parâmetro `formatos_abertos` (PBI-53) |

## API
| Método | Rota | Permissão | Descrição |
|---|---|---|---|
| GET | `/api/v1/relatorios` | `relatorios.acessar` | Catálogo filtrado pela permissão do módulo de origem |
| GET | `/api/v1/relatorios/{id}/previa` | `relatorios.acessar` + origem | Colunas, primeiras 50 linhas como texto, total e referência |
| GET | `/api/v1/relatorios/{id}/exportar?formato=xlsx\|csv\|pdf` | `relatorios.acessar` + `relatorios.exportar` + origem | Arquivo `relatorio-<id>-<aaaa-mm-dd>.<formato>` |
| GET | `/api/v1/relatorios/por-orgao/orgaos` | `relatorios.acessar` | `OrgaoOpcaoOut[]` (`{id, nome}`): órgãos do escopo do usuário, por nome |
| GET | `/api/v1/relatorios/por-orgao/{orgao}/previa?relatorios=pda&relatorios=…` | `relatorios.acessar` + origem de cada relatório | `RelatorioOrgaoOut`: `orgao`, `hoje` e `secoes` — um `PreviaOut` por item escolhido, já filtrado; `orgaos` = resumo do órgão (título "Resumo do órgão", `painel.acessar`), sempre a primeira seção. **404** órgão fora do escopo ou relatório desconhecido; **403** sem a permissão de origem; **422** nada escolhido |
| GET | `/api/v1/relatorios/por-orgao/{orgao}/exportar?relatorios=…&formato=pdf\|xlsx\|csv` | `relatorios.acessar` + `relatorios.exportar` + origem | Arquivo `relatorio-<sigla ou nome do órgão>-<aaaa-mm-dd>.<formato>` |

Erros: relatório inexistente → 404; sem a permissão do módulo de origem → 403; formato inválido → 422.

## Serviços e métodos
- `catalogo(user) -> list[RelatorioOut]` — relatórios visíveis para o usuário.
- `montar(db, nome, user, orgao=None) -> (Definicao, Tabela)` — monta colunas e linhas no escopo
  de órgão; com `orgao` (id da organização), cada montador filtra as linhas daquele órgão e as
  colunas de órgão saem (`regras.sem_colunas_de_orgao`); o relatório por órgão vira
  `regras.transpor` ("Indicador | Valor").
- `orgaos_disponiveis(db, user)`, `previa_orgao(db, orgao, relatorios, user)` e
  `exportar_orgao(db, orgao, relatorios, formato, user)` — relatório de um órgão: valida o órgão
  (escopo) e os relatórios (sem repetição, ordem do catálogo, permissão de origem de cada um); o
  "Resumo do órgão" (`RESUMO` = relatório "orgaos", `_secao_do_orgao`) entra só quando pedido,
  sempre como 1ª seção.
- `previa(db, nome, user, limite=50) -> PreviaOut`.
- `exportar(db, nome, formato, user) -> (bytes, media_type, nome_arquivo)` — PBI-60/61; formato `xlsx`, `csv` ou `pdf`.
- `regras.gerar_xlsx` / `regras.gerar_csv` / `regras.gerar_pdf` (puras): XLSX com cabeçalho em
  negrito, congelado, filtro e datas formatadas (openpyxl, já nas dependências); CSV com BOM UTF-8
  e `;` para o Excel em pt-BR (mesmo padrão do log de acesso); PDF em A4 paisagem com reportlab
  (ADR-0027): título, referência, data de geração e total, cabeçalho da tabela repetido em cada
  página, texto quebrado nas células e paginação no rodapé.
- `regras.gerar_pdf_secoes` / `gerar_xlsx_secoes` / `gerar_csv_secoes` (puras): os mesmos formatos
  com várias tabelas (`Secao`) — PDF com título, data de geração e, por seção, título, referência e
  total; XLSX com uma aba por seção (nome sem "Relatório de", único, até 31 caracteres); CSV com
  título e uma linha em branco entre as seções. `regras.slug` monta o nome do arquivo.

## Modelo de dados
Sem tabelas próprias. `RelatoriosDao` só lê as organizações visíveis ao usuário.

## Permissões
| Permissão | Papéis padrão |
|---|---|
| `relatorios.acessar` | Administrador, Gerência GEDA, Equipe GEDA, Superintendência |
| `relatorios.exportar` | Administrador, Gerência GEDA, Equipe GEDA, Superintendência |

A Superintendência só tem `painel.acessar` entre as permissões de origem: vê apenas o relatório
por órgão.

## Interações com outros módulos
| Direção | Módulo | O quê |
|---|---|---|
| consome | pda | `plano_vigente(db)` + `bases_do_plano(db, plano.id, user)` e `hoje_local()`: bases previstas, situação e prazos, **sempre do PDA vigente** |
| consome | atualizacoes | `regras.vencimento_atualizacao` e situações (`ATRASADO`, `PROXIMO_DO_VENCIMENTO`) |
| consome | painel | `organizacoes(db, user)` (relatório por órgão) e `situacao_atualizacao(base, hoje)` |
| é consumido por | painel | tela Organizações usa `GerarRelatorioOrgaoModal` no detalhe do órgão |
| consome | lgpd | `listar_achados(db, user, status="revisar")` |
| consome | metadados | `datasets_sem_recurso(db)` e `recursos_formato_fechado(db, formatos_abertos)` |
| consome | parametros | `formatos_abertos` |
| consome | inventario | `Organizacao` (nome/sigla do órgão nas listas do inventário) |

## Jobs agendados
Nenhum.

## Regras de negócio e decisões
Decisões registradas: [ADR-0007](../adr/0007-prototipo-v1-referencia-das-telas.md),
[ADR-0027](../adr/0027-exportacao-pdf-com-reportlab.md) (PDF com reportlab).

- Colunas compatíveis com as planilhas atuais da GEDA (PBI-61) — a confirmar com os modelos.
- Escopo de órgão: os relatórios usam os services de origem com o usuário da requisição; nas
  listas do inventário (sem recurso, formatos) o filtro é feito pelas organizações visíveis.
- O relatório LGPD nunca contém valores de dados pessoais (o banco também não os guarda).

## Pendências
- Modelos das planilhas atuais da GEDA para conferir nomes e ordem das colunas (PBI-61).
- Filtro por período antes de exportar. O filtro por órgão existe no "Relatório de um órgão"; os
  cartões de cada relatório continuam saindo com todos os órgãos do escopo do usuário.
- Relatório de metadados não preenchidos por órgão (PBI-50) depende de `metadados.completude`.

## Histórico de alterações
| Data | Alteração | Autor |
|---|---|---|
| 30/09/2026 | Esqueleto: contrato e permissões | Victor |
| 07/10/2026 | Interações: consumo do pda via `plano_vigente`/`bases_do_plano` (sempre o PDA vigente) | Humberto |
| 30/10/2026 | Tela Relatórios (US20, PBI-60/61/77): 6 relatórios do protótipo com prévia e exportação XLSX/CSV; `GET /relatorios`, `/{id}/previa`, `/{id}/exportar`; catálogo filtrado pela permissão do módulo de origem | Victor |
| 30/10/2026 | Prévia rola dentro do modal (altura máxima de 60vh, cabeçalho fixo); `Modal` compartilhado não fecha mais ao clicar na barra de rolagem do fundo | Victor |
| 30/10/2026 | Exportação em PDF (ADR-0027, reportlab): `formato=pdf` na rota de exportação, `regras.gerar_pdf` em A4 paisagem com título, referência, data de geração, cabeçalho repetido por página e paginação; botão "Exportar PDF" no modal | Victor |
| 05/11/2026 | **Relatório de um órgão** (pedido da GEDA em 05/11): escolher o órgão e quantos relatórios quiser; seções filtradas pelo órgão, sem as colunas de órgão, resumo do órgão em "Indicador | Valor"; PDF com seções, XLSX com uma aba por relatório e CSV em sequência (`/por-orgao/orgaos`, `/por-orgao/{orgao}/previa`, `/por-orgao/{orgao}/exportar`; `RelatorioOrgao.tsx`) | Humberto |
| 05/11/2026 | Relatório de um órgão: o "Relatório por Órgão" sai da marcação (continua como cartão comparativo) e o **Resumo do órgão** abre sempre o documento; sem relatório marcado, sai só o resumo | Humberto |
| 05/11/2026 | `GerarRelatorioOrgaoModal`: relatório de um órgão já escolhido (marcação + prévia/exportação), usado no detalhe do órgão em Organizações; marcação extraída para `useEscolha`/`EscolhaRelatorios`, compartilhada com o painel da tela | Humberto |
| 05/11/2026 | Relatório de um órgão: o **Resumo do órgão** volta a ser uma opção da marcação (primeira, já marcada) e pode ser desmarcado; entra só quando pedido (`orgaos`), sempre como 1ª seção; nada escolhido = 422 | Humberto |
| 05/11/2026 | Relatório por Órgão: colunas Riscos LGPD (recursos) e Recursos varridos (só com `lgpd.acessar`), Índice de atenção e Índice de atenção (0-100) | Humberto |
