# Módulo `atualizacoes` — Atualização real e periodicidade

| | |
|---|---|
| **Status** | Parcial: última atualização real implementada (PBI-23 a PBI-25); tela, API e situação por periodicidade em esqueleto |
| **Responsável** | Humberto (Eixo 1) |
| **User stories** | US9 (PBI-23 a PBI-26, PBI-78, PBI-79, PBI-81), US10 (PBI-27 a PBI-30) |
| **Backend** | `backend/app/modules/atualizacoes/` |
| **Frontend** | `frontend/src/modules/atualizacoes/` |
| **Última atualização** | 07/10/2026 |

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
`regras.py` (funções puras, reaproveitáveis numa extensão CKAN):
- `ultima_atualizacao_real(recursos) -> UltimaAtualizacao` — PBI-23 a PBI-25.
  `UltimaAtualizacao(data: datetime | None, estimada: bool)` (NamedTuple). Considera só recursos
  com `eh_dicionario_dados` falso; `data` = maior `last_modified`; se nenhum recurso válido tem
  `last_modified`, usa o maior `created` com `estimada=True`; sem recurso válido → `(None, False)`.
  Aceita objetos ORM ou dicts; data ISO sem fuso é tratada como UTC. Nunca usa `metadata_modified`.
  Testes em `tests/test_atualizacoes_regras.py`.

`service.py` (ponto de uso pelos outros módulos):
- `ultima_atualizacao_real(recursos) -> UltimaAtualizacao` — delega para `regras`.
- `situacao_periodicidade(periodicidade, ultima, hoje) -> str` — contrato (`NotImplementedError`):
  "Atualizado" | "Próximo do vencimento" | "Atrasado" | "Sem informação" (PBI-27/28).

Recomendação: implementar `situacao_periodicidade` também em `regras.py`.

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
| é consumido por | pda | `service.ultima_atualizacao_real` — coluna "Última atualização" e detalhe da base |
| é consumido por | painel, relatorios, assistente | situação de atualização por dataset e órgão |

## Jobs agendados
Nenhum.

## Regras de negócio e decisões
Decisões registradas: [ADR-0006](../adr/0006-regras-de-afericao-do-inventario.md).

- `metadata_modified` **nunca** é indicador de atualização.
- Ressalva do recurso parcial (17/09): dataset anual atualizado no meio do ano (PBI-78).
- Dicionário de dados não conta. A data de criação (`created`) só é usada quando nenhum recurso
  válido tem `last_modified`, e a data sai marcada como estimada.

## Pendências
- Domínio de valores de periodicidade praticado no portal (PBI-27, PBI-29).
- O PBI-25 pode pedir o fallback por recurso (`created` de cada recurso sem `last_modified`), não
  só quando nenhum tem — validar com a GEDA e o time.

## Histórico de alterações
| Data | Alteração | Autor |
|---|---|---|
| 30/09/2026 | Esqueleto: contratos e permissão | Victor |
| 07/10/2026 | `regras.ultima_atualizacao_real` implementada com `UltimaAtualizacao(data, estimada)` (PBI-23 a PBI-25); `service.py` delega e o módulo pda a consome | Humberto |
