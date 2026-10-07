# Módulo `pda` — Monitoramento do Plano de Dados Abertos

| | |
|---|---|
| **Status** | Esqueleto (contratos e tabela definidos) |
| **Responsável** | Humberto (Eixo 1) |
| **User stories** | US6 (PBI-12 a PBI-15), US7 (PBI-16 a PBI-18, PBI-82), US8 (PBI-19 a PBI-22, PBI-80) |
| **Backend** | `backend/app/modules/pda/` |
| **Frontend** | `frontend/src/modules/pda/` |
| **Última atualização** | 07/10/2026 |

## Propósito
Cruza as bases previstas no PDA 2025/2027 com os datasets publicados no CKAN e mostra prazos de
abertura vencidos ou próximos, por órgão.

## Telas
| Tela | Rota | Permissão para ver | Ações na tela (permissão) |
|---|---|---|---|
| Monitoramento do PDA | `/pda` | `pda.acessar` | Filtros (órgão, situação, periodicidade, ano, prazo); importar planilha de vinculação e reclassificar PDA × espontânea (`pda.editar_vinculos`) |

Referência visual: `#screen-pda` do Protótipo V1. Ressalva de 17/09: PDA trata do **prazo de
abertura**; atualização tem tela própria (módulo `atualizacoes`).

## API
Nenhum endpoint ainda. Previstos:

| Método | Rota (`/api/v1/pda`) | Permissão | Descrição |
|---|---|---|---|
| GET | `/bases` | `pda.acessar` | Bases previstas com situação e filtros |
| POST | `/vinculos/importar` | `pda.editar_vinculos` | Importa a planilha GEDA (PBI-12) |
| PUT | `/bases/{id}/classificacao` | `pda.editar_vinculos` | PDA × espontânea (PBI-17) |

## Serviços e métodos
Contratos em `service.py` (lançam `NotImplementedError`):
- `importar_planilha_vinculacao(db, arquivo) -> int` — PBI-12.
- `situacao_prazo(base, hoje, janela_dias) -> str` — "Publicado" | "Vencido" | "Próximo do prazo" | "No prazo" | "Sem vínculo" (PBI-19).
- `listar_bases(db, *, orgao, situacao, periodicidade, ano, prazo)` — PBI-20/21.

## Modelo de dados
Diagrama e dicionário de dados completos: [MER](../banco/mer.md) · regras: [convenções do banco](../banco/convencoes.md).

| Tabela | Colunas relevantes |
|---|---|
| `pda_base_prevista` | orgao_sigla, nome_previsto, prazo_abertura, periodicidade, `dataset_id` → `dataset.ckan_id`, classificacao (pda/espontanea) |

## Permissões
| Permissão | Papéis padrão |
|---|---|
| `pda.acessar` | Administrador, Gerência GEDA, Equipe GEDA |
| `pda.editar_vinculos` | Administrador, Gerência GEDA |

## Interações com outros módulos
| Direção | Módulo | O quê |
|---|---|---|
| consome | inventario | `Dataset` (existência e órgão do dataset vinculado) |
| consome | parametros | `janela_alerta_prazo_dias` (PBI-22) |
| é consumido por | painel | bases previstas × publicadas por órgão (US19) |
| é consumido por | relatorios | relatório de bases não publicadas |
| é consumido por | assistente | situação de prazos no contexto |

## Jobs agendados
Nenhum — a situação é calculada sobre o inventário da última coleta.

## Regras de negócio e decisões
Decisões registradas: [ADR-0006](../adr/0006-regras-de-afericao-do-inventario.md).

- Vínculo **sempre pelo ID do dataset** (PBI-13); nunca por similaridade de nome.
- Base vinculada cujo dataset some do portal gera alerta (PBI-15).
- Bases espontâneas também são monitoradas (Paloma e Júnior, 17/09).

## Pendências
- Planilha de vinculação e PDA 2025/2027 (insumos da GEDA).
- Critério de identificação das bases espontâneas (GEDA).

## Histórico de alterações
| Data | Alteração | Autor |
|---|---|---|
| 30/09/2026 | Esqueleto: contratos, tabela `pda_base_prevista` e permissões | Victor |
| 07/10/2026 | Link para o MER e as convenções do banco | Victor |
