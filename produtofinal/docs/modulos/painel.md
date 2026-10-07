# Módulo `painel` — Visão geral e organizações

| | |
|---|---|
| **Status** | Esqueleto (contratos definidos) |
| **Responsável** | João (Dashboard) · Humberto (Organizações, PBI-84) |
| **User stories** | US19 (PBI-56 a PBI-59, PBI-75, PBI-76, PBI-84), US27 (exibição do ranking) |
| **Backend** | `backend/app/modules/painel/` |
| **Frontend** | `frontend/src/modules/dashboard/` · `frontend/src/modules/organizacoes/` |
| **Última atualização** | 30/09/2026 |

## Propósito
Consolida os indicadores dos eixos numa visão gerencial por órgão, usada pela GEDA e pela
Superintendência (inclusive para o Prêmio de Transparência).

## Telas
| Tela | Rota | Permissão para ver | Ações na tela (permissão) |
|---|---|---|---|
| Dashboard (Visão Geral) | `/` | `painel.acessar` | KPIs, gráficos, alertas prioritários; "Atualizar dados" (`inventario.coletar`) |
| Organizações | `/organizacoes` | `painel.acessar` | Índice de atenção, detalhe do órgão; ir para PDA (`pda.acessar`) |

Referência visual: `#screen-dashboard` e `#screen-organizations`. Ressalvas de 17/09: gráficos de
evolução temporal abaixo dos cards (PBI-75).

## API
Nenhum endpoint ainda. Previstos: `GET /api/v1/painel/kpis`, `/organizacoes`, `/alertas`
(`painel.acessar`).

## Serviços e métodos
- `kpis(db) -> dict` — PBI-56.
- `indice_atencao_por_orgao(db)` — PBI-76/84, critério documentado e auditável (PBI-59).

## Modelo de dados
Sem tabelas próprias. Séries temporais podem exigir uma tabela de indicadores por coleta (a decidir).

## Permissões
| Permissão | Papéis padrão |
|---|---|
| `painel.acessar` | Administrador, Gerência GEDA, Equipe GEDA, Superintendência |

## Interações com outros módulos
| Direção | Módulo | O quê |
|---|---|---|
| consome | inventario | contagens e última coleta |
| consome | pda | bases previstas × publicadas, prazos |
| consome | atualizacoes | desatualizados por órgão |
| consome | lgpd | indicador de risco e ranking de exposição (US27) |
| consome | metadados | completude média |

## Jobs agendados
Nenhum.

## Regras de negócio e decisões
Decisões registradas: [ADR-0007](../adr/0007-prototipo-v1-referencia-das-telas.md).

- Indicadores calculados somente a partir da última coleta, com data visível (PBI-58).
- Bloco de alertas LGPD só aparece se o usuário também tiver `lgpd.acessar` (usar `<Pode>`).

## Pendências
- Fórmula do índice de atenção (validar com a GEDA).

## Histórico de alterações
| Data | Alteração | Autor |
|---|---|---|
| 30/09/2026 | Esqueleto: contratos, duas telas e permissão | Victor |
