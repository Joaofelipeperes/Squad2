# Módulo `atualizacoes` — Atualização real e periodicidade

| | |
|---|---|
| **Status** | Parcial: última atualização real (PBI-23 a PBI-25), situação por periodicidade (PBI-27/28, ADR-0023) e a tela Monitoramento de Atualizações (API + frontend, PBI-81) implementadas; faltam recurso parcial (PBI-78) e correções por anonimização (PBI-79) |
| **Responsável** | Humberto (Eixo 1) |
| **User stories** | US9 (PBI-23 a PBI-26, PBI-78, PBI-79, PBI-81), US10 (PBI-27 a PBI-30) |
| **Backend** | `backend/app/modules/atualizacoes/` |
| **Frontend** | `frontend/src/modules/atualizacoes/` |
| **Última atualização** | 30/10/2026 |

## Propósito
Indica se cada dataset está de fato sendo atualizado conforme a periodicidade declarada, usando a
data do recurso e não a do metadado — eliminando as "falsas atualizações".

## Telas
| Tela | Rota | Permissão para ver | Ações na tela (permissão) |
|---|---|---|---|
| Monitoramento de Atualizações | `/atualizacoes` | `atualizacoes.acessar` | Filtros por dataset (busca), órgão, periodicidade e situação (PBI-81); clicar na linha abre o detalhe do dataset (modal da tela Datasets) |

Referência visual: `#screen-updates` do Protótipo V1, incluindo o aviso sobre `last_modified`. Os filtros **dataset** e **órgão** são adicionais ao protótipo. A lista traz os datasets vinculados às bases do **PDA vigente** (a periodicidade vem do PDA, ADR-0023); base sem vínculo não aparece. Os cartões contam todas as linhas do escopo, sem os filtros.

## API
- `GET /api/v1/atualizacoes/datasets` (`atualizacoes.acessar`) — query `orgao` (chave do órgão), `periodicidade`, `situacao`, `dataset` (trecho do título/name, sem acento nem caixa). Devolve `plano_nome`, `hoje`, `total`, `resumo` (cartões), `opcoes` e `datasets` (linhas: dataset, órgão, periodicidade, última atualização, dias, prazo esperado, situação). Escopo de órgão do usuário aplicado por `pda.bases_do_plano`.

## Serviços e métodos
Sem acesso ao banco próprio (não tem `dao.py`): `regras.py` é de funções puras e `listagem.py` lê as bases já calculadas por `pda.bases_do_plano`.

`listagem.py` — `listar(db, user, orgao, periodicidade, situacao, dataset) -> AtualizacoesOut` (tela). Fica fora de `service.py` e é importado de forma tardia pelo router porque o módulo pda importa `atualizacoes.service` (evita importação circular). Dataset fora do portal → "Sem informação", como no Dashboard. `schemas.py` guarda o contrato JSON.

`regras.py` (funções puras, reaproveitáveis numa extensão CKAN):
- `ultima_atualizacao_real(recursos) -> UltimaAtualizacao` — PBI-23 a PBI-25.
  `UltimaAtualizacao(data: datetime | None, estimada: bool)` (NamedTuple). Considera só recursos
  com `eh_dicionario_dados` falso; `data` = maior `last_modified`; se nenhum recurso válido tem
  `last_modified`, usa o maior `created` com `estimada=True`; sem recurso válido → `(None, False)`.
  Aceita objetos ORM ou dicts; data ISO sem fuso é tratada como UTC. Nunca usa `metadata_modified`.
  Testes em `tests/test_atualizacoes_regras.py`.

`service.py` (ponto de uso pelos outros módulos):
- `ultima_atualizacao_real(recursos) -> UltimaAtualizacao` — delega para `regras`.
- `situacao_periodicidade(periodicidade, ultima, hoje, original=None) -> str` — PBI-27/28
  (ADR-0023), delega para `regras.situacao_periodicidade`: "Atualizado" | "Próximo do vencimento" |
  "Atrasado" | "Sem informação" | "Sem periodicidade definida".

`regras.py` (funções puras): `DIAS_POR_PERIODICIDADE` (Mensal 30, Anual 365…), `prazo_em_dias(
periodicidade, original)` (Múltipla = menor periodicidade citada no texto original),
`vencimento_atualizacao(periodicidade, ultima, original)` e `situacao_periodicidade`: `d` = dias
desde a última atualização real; `d > prazo` → Atrasado; `d ≥ 80% do prazo` (`FRACAO_ALERTA`) →
Próximo do vencimento; senão Atualizado. Eventual/Estática → Sem periodicidade definida; sem prazo
ou sem data → Sem informação. Testes em `tests/test_atualizacoes_periodicidade.py`.

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
| consome | pda | `plano_vigente` + `bases_do_plano` — periodicidade, dataset vinculado e última atualização por base (tela Monitoramento de Atualizações); indicador separado PDA × espontânea (PBI-82, previsto) |
| consome | inventario | `DatasetDetalheModal` (frontend) — detalhe do dataset ao clicar numa linha |
| é consumido por | pda | `service.ultima_atualizacao_real` — coluna "Última atualização" e detalhe da base |
| é consumido por | inventario | `regras.ultima_atualizacao_real` — coluna "Última atualização" e detalhe da tela Datasets |
| é consumido por | painel, relatorios | situação de atualização por dataset e órgão |
| é consumido por | assistente | `regras.ultima_atualizacao_real` (já); situação por periodicidade quando implementada |
| é consumido por | painel | `regras.situacao_periodicidade` e `vencimento_atualizacao` — gráfico "Status das atualizações", cartão "Atualizações em atraso" e alertas do Dashboard; coluna "Atualização" e cartão "Atualizações atrasadas" da tela Organizações |

## Jobs agendados
Nenhum.

## Regras de negócio e decisões
Decisões registradas: [ADR-0006](../adr/0006-regras-de-afericao-do-inventario.md).
- Situação por periodicidade: ver [ADR-0023](../adr/0023-situacao-de-atualizacao-pela-periodicidade-do-pda.md). A periodicidade que vale é a da base no **PDA vigente**; Mensal = 30 dias, **sem tolerância**.

- `metadata_modified` **nunca** é indicador de atualização.
- Ressalva do recurso parcial (17/09): dataset anual atualizado no meio do ano (PBI-78).
- Dicionário de dados não conta. A data de criação (`created`) só é usada quando nenhum recurso
  válido tem `last_modified`, e a data sai marcada como estimada.

## Pendências
- Domínio de valores de periodicidade praticado no portal (PBI-27, PBI-29).
- Situação por periodicidade ainda não considera recurso parcial (PBI-78) nem correções por
  anonimização (PBI-79); validar a regra da ADR-0023 com a GEDA (tolerância).
- O PBI-25 pode pedir o fallback por recurso (`created` de cada recurso sem `last_modified`), não
  só quando nenhum tem — validar com a GEDA e o time.

## Histórico de alterações
| Data | Alteração | Autor |
|---|---|---|
| 30/09/2026 | Esqueleto: contratos e permissão | Victor |
| 07/10/2026 | `regras.ultima_atualizacao_real` implementada com `UltimaAtualizacao(data, estimada)` (PBI-23 a PBI-25); `service.py` delega e o módulo pda a consome | Humberto |
| 18/10/2026 | Interações: a tela Datasets (inventario) passa a consumir `regras.ultima_atualizacao_real`; sem mudança de código neste módulo | Humberto |
| 22/10/2026 | `ultima_atualizacao_real`: a estimativa usa a data de criação no CKAN — `created_ckan` nos objetos do banco (o `created` deles é a auditoria, ADR-0019) e `created` nos payloads/dicts do CKAN | Victor |
| 23/10/2026 | Interações: o que o Assistente consome deste módulo | Squad 2 |
| 28/10/2026 | Situação por periodicidade (PBI-27/28, ADR-0023): `regras.situacao_periodicidade`, `prazo_em_dias`, `vencimento_atualizacao`; contrato `service.situacao_periodicidade` implementado; usado pelo Dashboard | Humberto |
| 30/10/2026 | Tela Monitoramento de Atualizações (US9/US10, PBI-81): `GET /atualizacoes/datasets`, `listagem.py`, `schemas.py`, `AtualizacoesPage` com cartões e filtros dataset, órgão, periodicidade e situação; teste `test_atualizacoes_api.py` | Squad 2 |
