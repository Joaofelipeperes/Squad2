# Módulo `atualizacoes` — Atualização real e periodicidade

| | |
|---|---|
| **Status** | Esqueleto (contratos definidos) |
| **Responsável** | Humberto (Eixo 1) |
| **User stories** | US9 (PBI-23 a PBI-26, PBI-78, PBI-79, PBI-81), US10 (PBI-27 a PBI-30) |
| **Backend** | `backend/app/modules/atualizacoes/` |
| **Frontend** | `frontend/src/modules/atualizacoes/` |
| **Última atualização** | 30/09/2026 |

## Propósito
Indica se cada dataset está de fato sendo atualizado conforme a periodicidade declarada, usando a
data do recurso e não a do metadado — eliminando as "falsas atualizações".

## Telas
| Tela | Rota | Permissão para ver | Ações na tela (permissão) |
|---|---|---|---|
| Monitoramento de Atualizações | `/atualizacoes` | `atualizacoes.acessar` | Filtros por órgão, periodicidade e situação (PBI-81) |

Referência visual: `#screen-updates` do Protótipo V1, incluindo o aviso sobre `last_modified`.

## API
Nenhum endpoint ainda. Previsto: `GET /api/v1/atualizacoes/datasets` (`atualizacoes.acessar`).

## Serviços e métodos
Contratos em `service.py`:
- `ultima_atualizacao_real(recursos) -> datetime | None` — maior `last_modified`, excluindo
  dicionário de dados; sem `last_modified` usa `created` e sinaliza (PBI-23 a PBI-25).
- `situacao_periodicidade(periodicidade, ultima, hoje) -> str` — "Atualizado" | "Próximo do
  vencimento" | "Atrasado" | "Sem informação" (PBI-27/28).

Recomendação: implementar ambos em `regras.py` (funções puras), como em `inventario`.

## Modelo de dados
Sem tabelas próprias: lê `dataset` e `recurso` do inventário.

## Permissões
| Permissão | Papéis padrão |
|---|---|
| `atualizacoes.acessar` | Administrador, Gerência GEDA, Equipe GEDA |

## Interações com outros módulos
| Direção | Módulo | O quê |
|---|---|---|
| consome | inventario | `Recurso.last_modified`, `Recurso.eh_dicionario_dados`, `Dataset.periodicidade_declarada` |
| consome | lgpd | `CorrecaoPublicada` — correção por anonimização não conta como atualização (PBI-79) |
| consome | pda | indicador separado PDA × espontânea (PBI-82) |
| é consumido por | painel, relatorios, assistente | situação de atualização por dataset e órgão |

## Jobs agendados
Nenhum.

## Regras de negócio e decisões
Decisões registradas: [ADR-0006](../adr/0006-regras-de-afericao-do-inventario.md).

- `metadata_modified` **nunca** é indicador de atualização.
- Ressalva do recurso parcial (17/09): dataset anual atualizado no meio do ano (PBI-78).

## Pendências
- Domínio de valores de periodicidade praticado no portal (PBI-27, PBI-29).

## Histórico de alterações
| Data | Alteração | Autor |
|---|---|---|
| 30/09/2026 | Esqueleto: contratos e permissão | Claude / Victor |
