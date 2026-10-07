# Módulo `relatorios` — Relatórios e exportação

| | |
|---|---|
| **Status** | Esqueleto (contrato definido) |
| **Responsável** | João |
| **User stories** | US20 (PBI-60, PBI-61, PBI-77) |
| **Backend** | `backend/app/modules/relatorios/` |
| **Frontend** | `frontend/src/modules/relatorios/` |
| **Última atualização** | 30/09/2026 |

## Propósito
Substitui o controle manual em planilhas da GEDA por relatórios exportáveis com as mesmas colunas.

## Telas
| Tela | Rota | Permissão para ver | Ações na tela (permissão) |
|---|---|---|---|
| Relatórios | `/relatorios` | `relatorios.acessar` | Prévia; exportar XLSX/CSV (`relatorios.exportar`) |

Referência visual: `#screen-reports` (6 relatórios do protótipo, PBI-77). Cada relatório deve
exigir também a permissão de acesso do módulo de origem (ex.: relatório LGPD exige `lgpd.acessar`).

## API
Nenhum endpoint ainda. Previstos: `GET /api/v1/relatorios` (`relatorios.acessar`) e
`GET /api/v1/relatorios/{nome}/exportar?formato=xlsx|csv` (`relatorios.exportar` + permissão do
módulo de origem).

## Serviços e métodos
- `exportar(nome_relatorio, formato, filtros) -> bytes` — PBI-60/61 (dependência `openpyxl`).

## Modelo de dados
Sem tabelas próprias.

## Permissões
| Permissão | Papéis padrão |
|---|---|
| `relatorios.acessar` | Administrador, Gerência GEDA, Equipe GEDA, Superintendência |
| `relatorios.exportar` | Administrador, Gerência GEDA, Equipe GEDA, Superintendência |

## Interações com outros módulos
| Direção | Módulo | O quê |
|---|---|---|
| consome | pda, atualizacoes, lgpd, metadados, rastreabilidade, painel | dados de cada relatório |

## Jobs agendados
Nenhum.

## Regras de negócio e decisões
Decisões registradas: [ADR-0007](../adr/0007-prototipo-v1-referencia-das-telas.md).

- Colunas compatíveis com as planilhas atuais da GEDA (PBI-61).

## Pendências
- Modelos das planilhas atuais da GEDA.

## Histórico de alterações
| Data | Alteração | Autor |
|---|---|---|
| 30/09/2026 | Esqueleto: contrato e permissões | Claude / Victor |
