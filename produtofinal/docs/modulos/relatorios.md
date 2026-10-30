# Módulo `relatorios` — Relatórios e exportação

| | |
|---|---|
| **Status** | Implementado (6 relatórios do protótipo, prévia e exportação XLSX/CSV) |
| **Responsável** | João |
| **User stories** | US20 (PBI-60, PBI-61, PBI-77) |
| **Backend** | `backend/app/modules/relatorios/` |
| **Frontend** | `frontend/src/modules/relatorios/` |
| **Última atualização** | 30/10/2026 |

## Propósito
Substitui o controle manual em planilhas da GEDA por relatórios exportáveis com as mesmas colunas.

## Telas
| Tela | Rota | Permissão para ver | Ações na tela (permissão) |
|---|---|---|---|
| Relatórios | `/relatorios` | `relatorios.acessar` | Gerar relatório (prévia, `relatorios.acessar` + permissão do módulo de origem); exportar Excel/CSV (`relatorios.exportar`) |

Referência visual: `#screen-reports` (6 relatórios do protótipo, PBI-77). Cada cartão abre um modal
com a prévia (até 50 linhas, total de linhas e referência, ex.: o PDA vigente). A exportação leva o
relatório inteiro. Os cartões mostrados dependem do perfil: só aparecem os relatórios cujo módulo de
origem o usuário acessa.

| Relatório (`id`) | Módulo de origem (permissão exigida) | Conteúdo |
|---|---|---|
| Cumprimento do PDA (`pda`) | pda (`pda.acessar`) | Bases do PDA vigente: órgão, situação, prazo, periodicidade, vínculo, dataset, recursos válidos, formatos, publicação |
| Atualizações (`atualizacoes`) | atualizacoes (`atualizacoes.acessar`) | Bases vinculadas do PDA vigente com atualização **Atrasada** ou **Próxima do vencimento** (ADR-0023); atrasadas primeiro |
| Dados Pessoais (`lgpd`) | lgpd (`lgpd.acessar`) | Achados com status `revisar`, por prioridade e confiança; só localização e tipo, nunca o valor |
| Por Órgão (`orgaos`) | painel (`painel.acessar`) | Mesmos indicadores da tela Organizações |
| Datasets sem Recurso (`sem-recurso`) | inventario (`inventario.acessar`) | Datasets ativos sem recurso válido (PBI-51) |
| Formatos não Abertos (`formatos`) | inventario (`inventario.acessar`) | Recursos atuais fora do parâmetro `formatos_abertos` (PBI-53) |

## API
| Método | Rota | Permissão | Descrição |
|---|---|---|---|
| GET | `/api/v1/relatorios` | `relatorios.acessar` | Catálogo filtrado pela permissão do módulo de origem |
| GET | `/api/v1/relatorios/{id}/previa` | `relatorios.acessar` + origem | Colunas, primeiras 50 linhas como texto, total e referência |
| GET | `/api/v1/relatorios/{id}/exportar?formato=xlsx\|csv` | `relatorios.acessar` + `relatorios.exportar` + origem | Arquivo `relatorio-<id>-<aaaa-mm-dd>.<formato>` |

Erros: relatório inexistente → 404; sem a permissão do módulo de origem → 403; formato inválido → 422.

## Serviços e métodos
- `catalogo(user) -> list[RelatorioOut]` — relatórios visíveis para o usuário.
- `montar(db, nome, user) -> (Definicao, Tabela)` — monta colunas e linhas no escopo de órgão.
- `previa(db, nome, user, limite=50) -> PreviaOut`.
- `exportar(db, nome, formato, user) -> (bytes, media_type, nome_arquivo)` — PBI-60/61.
- `regras.gerar_xlsx` / `regras.gerar_csv` (puras): XLSX com cabeçalho em negrito, congelado,
  filtro e datas formatadas (openpyxl, já nas dependências); CSV com BOM UTF-8 e `;` para o Excel
  em pt-BR (mesmo padrão do log de acesso).

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
| consome | lgpd | `listar_achados(db, user, status="revisar")` |
| consome | metadados | `datasets_sem_recurso(db)` e `recursos_formato_fechado(db, formatos_abertos)` |
| consome | parametros | `formatos_abertos` |
| consome | inventario | `Organizacao` (nome/sigla do órgão nas listas do inventário) |

## Jobs agendados
Nenhum.

## Regras de negócio e decisões
Decisões registradas: [ADR-0007](../adr/0007-prototipo-v1-referencia-das-telas.md).

- Colunas compatíveis com as planilhas atuais da GEDA (PBI-61) — a confirmar com os modelos.
- Escopo de órgão: os relatórios usam os services de origem com o usuário da requisição; nas
  listas do inventário (sem recurso, formatos) o filtro é feito pelas organizações visíveis.
- O relatório LGPD nunca contém valores de dados pessoais (o banco também não os guarda).

## Pendências
- Modelos das planilhas atuais da GEDA para conferir nomes e ordem das colunas (PBI-61).
- Filtros por órgão/período antes de exportar (hoje o relatório sai completo no escopo do usuário).
- Relatório de metadados não preenchidos por órgão (PBI-50) depende de `metadados.completude`.

## Histórico de alterações
| Data | Alteração | Autor |
|---|---|---|
| 30/09/2026 | Esqueleto: contrato e permissões | Victor |
| 07/10/2026 | Interações: consumo do pda via `plano_vigente`/`bases_do_plano` (sempre o PDA vigente) | Humberto |
| 30/10/2026 | Tela Relatórios (US20, PBI-60/61/77): 6 relatórios do protótipo com prévia e exportação XLSX/CSV; `GET /relatorios`, `/{id}/previa`, `/{id}/exportar`; catálogo filtrado pela permissão do módulo de origem | Victor |
| 30/10/2026 | Prévia rola dentro do modal (altura máxima de 60vh, cabeçalho fixo); `Modal` compartilhado não fecha mais ao clicar na barra de rolagem do fundo | Victor |
