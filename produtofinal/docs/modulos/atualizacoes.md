# Módulo `atualizacoes` — Atualização real e periodicidade

| | |
|---|---|
| **Status** | Parcial: última atualização real (PBI-23 a PBI-25), situação por periodicidade do campo "Atualização" do CKAN sobre todas as bases publicadas (PBI-27/28, ADR-0037) e a tela Monitoramento de Atualizações (API + frontend, PBI-81, PBI-82) implementadas; faltam recurso parcial (PBI-78) e correções por anonimização (PBI-79) |
| **Responsável** | Humberto (Eixo 1) |
| **User stories** | US9 (PBI-23 a PBI-26, PBI-78, PBI-79, PBI-81), US10 (PBI-27 a PBI-30) |
| **Backend** | `backend/app/modules/atualizacoes/` |
| **Frontend** | `frontend/src/modules/atualizacoes/` |
| **Última atualização** | 13/11/2026 |

## Propósito
Indica se cada dataset está de fato sendo atualizado conforme a periodicidade declarada, usando a
data do recurso e não a do metadado — eliminando as "falsas atualizações".

## Telas
| Tela | Rota | Permissão para ver | Ações na tela (permissão) |
|---|---|---|---|
| Monitoramento de Atualizações | `/atualizacoes` | `atualizacoes.acessar` | Filtros por dataset (busca), órgão, tipo de base (Prevista no PDA × Espontânea, PBI-82), periodicidade e situação (PBI-81); ordenação por coluna e paginação com total no rodapé (ADR-0028); clicar na linha abre o detalhe do dataset (modal da tela Datasets); **Excel** e **PDF** da tabela como está na tela — filtros, ordem e todas as páginas (`relatorios.exportar`, ADR-0031) |

Referência visual: `#screen-updates` do Protótipo V1. O aviso do protótipo sobre `last_modified` saiu da tela (06/11, termo técnico para o usuário da GEDA); a regra continua a mesma. Os filtros **dataset**, **órgão** e **tipo de base** e a coluna **Tipo de base** são adicionais ao protótipo. A lista traz **todos os datasets ativos no portal** (previstos no PDA vigente ou espontâneos, ADR-0037); dataset fora do portal não aparece. A periodicidade vem só do campo "Atualização" do CKAN; quando ele está vazio ou inválido a linha mostra "Periodicidade não informada" com o texto do CKAN na dica. Cartões: Atualizados, Em atraso, Próximos do vencimento e Periodicidade não informada; abaixo deles, em texto, quantos declaram "sem atualização periódica", quantos estão sem data e o total previstas no PDA × espontâneas. Os cartões contam todas as linhas do escopo, sem os filtros.

## API
- `GET /api/v1/atualizacoes/datasets` (`atualizacoes.acessar`) — query `orgao` (id da organização ou `sem_orgao`), `tipo_base` ("Prevista no PDA" | "Espontânea"), `periodicidade`, `situacao`, `dataset` (trecho do título/name, sem acento nem caixa). Devolve `plano_nome` (PDA vigente que define o tipo de base), `hoje`, `total`, `resumo` (atualizados, atrasados, próximos do vencimento, sem atualização periódica, periodicidade não informada, sem data, previstas no PDA, espontâneas), `opcoes` e `datasets` (linhas: dataset, órgão, tipo de base, periodicidade declarada no CKAN e normalizada, última atualização, dias, prazo esperado, situação). Escopo de órgão do usuário aplicado na consulta do inventário.

## Serviços e métodos
Sem acesso ao banco próprio (não tem `dao.py`): `regras.py` é de funções puras e `listagem.py` lê os datasets ativos por `inventario.service.datasets_publicados` e o vínculo com o PDA vigente por `pda.service.datasets_vinculados_ao_vigente`.

`listagem.py` (fica fora de `service.py` e é importado de forma tardia pelo router porque o módulo pda importa `atualizacoes.service` — evita importação circular):
- `situacoes_dos_datasets(db, user, hoje=None) -> list[DatasetAtualizacao]` — cada dataset ativo no portal com tipo de base, periodicidade (declarada e normalizada), última atualização real, dias, vencimento e situação. **Fonte única** do indicador para a tela, o painel (Dashboard e Organizações) e os relatórios (ADR-0037).
- `listar(db, user, orgao, periodicidade, situacao, dataset, tipo_base) -> AtualizacoesOut` — tela.
`schemas.py` guarda o contrato JSON.

`regras.py` (funções puras, reaproveitáveis numa extensão CKAN):
- `ultima_atualizacao_real(recursos) -> UltimaAtualizacao` — PBI-23 a PBI-25.
  `UltimaAtualizacao(data: datetime | None, estimada: bool)` (NamedTuple). Considera só recursos
  com `eh_dicionario_dados` falso; `data` = maior `last_modified`; se nenhum recurso válido tem
  `last_modified`, usa o maior `created` com `estimada=True`; sem recurso válido → `(None, False)`.
  Aceita objetos ORM ou dicts; data ISO sem fuso é tratada como UTC. Nunca usa `metadata_modified`.
  Testes em `tests/test_atualizacoes_regras.py`.

`service.py` (ponto de uso pelos outros módulos):
- `ultima_atualizacao_real(recursos) -> UltimaAtualizacao` — delega para `regras`.
- `situacao_periodicidade(periodicidade, ultima, hoje) -> str` — PBI-27/28 (ADR-0037), delega
  para `regras.situacao_periodicidade`. `periodicidade` = campo "Atualização" do CKAN.

`regras.py` (funções puras), ADR-0037:
- `periodicidade_ckan(texto) -> str` — campo "Atualização" → valor do domínio (`PERIODICIDADES`):
  Diária, Semanal, Quinzenal, Mensal, Bimestral, Trimestral, Quadrimestral, Semestral, Anual,
  Bienal, Quadrienal, Quinquenal (sem diferenciar maiúsculas, acentos, espaços e pontuação);
  "Não possui atualização periódica" → **"Sem atualização periódica"** (válido); vazio, ausente ou
  qualquer outro texto → **"Periodicidade não informada"** (nunca chuta). Idempotente.
- `DIAS_POR_PERIODICIDADE` (Mensal 30, Anual 365…), `prazo_em_dias(periodicidade)`,
  `vencimento_atualizacao(periodicidade, ultima)`.
- `situacao_periodicidade(periodicidade, ultima, hoje)`, nesta precedência: "Sem atualização
  periódica"; "Periodicidade não informada" (mesmo com data); "Sem data de atualização"
  (periodicidade válida, sem recurso válido com data); senão, com `d` = dias desde a última
  atualização real, `d > prazo` → Atrasado, `d ≥ 80% do prazo` (`FRACAO_ALERTA`) → Próximo do
  vencimento, senão Atualizado. `SITUACOES_ATUALIZACAO` dá a ordem; `COM_PRAZO` são as que entram
  no % por órgão e no índice de atenção.
Testes em `tests/test_atualizacoes_periodicidade.py` e `tests/test_atualizacoes_api.py`.

## Modelo de dados
Sem tabelas próprias: lê `dataset` e `recurso` do inventário.

## Permissões
| Permissão | Papéis padrão |
|---|---|
| `atualizacoes.acessar` | Administrador, Gerência GEDA, Equipe GEDA |

## Interações com outros módulos
| Direção | Módulo | O quê |
|---|---|---|
| consome | inventario | `service.datasets_publicados` (datasets ativos com recursos, escopo do usuário), `service.recursos_atuais`, `service.organizacoes`, `regras.periodicidade_declarada` (campo "Atualização" dos extras) e `regras.tipo_de_base` |
| consome | lgpd | `CorrecaoPublicada` — correção por anonimização não conta como atualização (PBI-79) |
| consome | pda | `plano_vigente`, `datasets_vinculados_ao_vigente` (tipo de base: Prevista no PDA × Espontânea, PBI-82) e `hoje_local` |
| consome | inventario | `DatasetDetalheModal` e `TipoBaseBadge` (frontend) — detalhe do dataset ao clicar numa linha e selo do tipo de base |
| é consumido por | pda | `service.ultima_atualizacao_real` — coluna "Última atualização" e detalhe da base |
| é consumido por | inventario | `regras.ultima_atualizacao_real` — coluna "Última atualização" e detalhe da tela Datasets |
| é consumido por | relatorios | `listagem.situacoes_dos_datasets` — Relatório de Atualizações e seção "Atualização dos datasets" do relatório por órgão |
| é consumido por | assistente | `regras.ultima_atualizacao_real` (já); situação por periodicidade quando implementada |
| é consumido por | painel | `listagem.situacoes_dos_datasets` e `regras` — gráfico "Status das atualizações", cartões "Atualizações em atraso" e "Periodicidade não informada" e alertas do Dashboard; coluna "Atualização" e cartões da tela Organizações |
| consome | relatorios | `POST /relatorios/tabela/exportar` (pelo frontend, `ExportarTabela`) — Excel e PDF da tabela da tela (ADR-0031) |

## Jobs agendados
Nenhum.

## Regras de negócio e decisões
Decisões registradas: [ADR-0006](../adr/0006-regras-de-afericao-do-inventario.md).
- Situação por periodicidade: ver [ADR-0037](../adr/0037-indicador-de-atualizacao-sobre-todas-as-bases-publicadas.md) (substitui a [ADR-0023](../adr/0023-situacao-de-atualizacao-pela-periodicidade-do-pda.md)). Critérios da GEDA (13/11/2026): **todas** as bases publicadas entram, do PDA ou espontâneas — o vínculo com o PDA não é condição, só identifica o tipo de base; a periodicidade vem **só** do campo "Atualização" do CKAN; "Não possui atualização periódica" é declaração válida; campo vazio ou inválido é "Periodicidade não informada" (não conforme) e nunca se confunde com a anterior. Mensal = 30 dias, **sem tolerância**.
- "Sem atualização periódica" e "Periodicidade não informada" ficam fora do % de atualização por órgão e do índice de atenção ("por hora", GEDA 13/11/2026).

- `metadata_modified` **nunca** é indicador de atualização.
- Ressalva do recurso parcial (17/09): dataset anual atualizado no meio do ano (PBI-78).
- Dicionário de dados não conta. A data de criação (`created`) só é usada quando nenhum recurso
  válido tem `last_modified`, e a data sai marcada como estimada.

## Pendências
- Domínio do campo "Atualização" no portal: conferido na cópia de metadados (Mensal, Anual,
  Semestral, Bimestral, Trimestral, Quadrimestral, Bienal, Quadrienal e "Não possui atualização
  periódica"); se a SECTI acrescentar opções, incluí-las em `regras.periodicidade_ckan` (PBI-29).
- Situação por periodicidade ainda não considera recurso parcial (PBI-78) nem correções por
  anonimização (PBI-79).
- Confirmar com a GEDA se "Sem atualização periódica" continua fora do % por órgão.
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
| 05/11/2026 | Tela Monitoramento de Atualizações: ordenação por qualquer coluna (clique no título) e paginação no rodapé com o total de registros (50 por página, ajustável até 999; `shared/ui/tabela.tsx`, ADR-0028); contador movido para o rodapé. Sem mudança na API | Victor |
| 06/11/2026 | Tela: aviso sobre `last_modified`/`metadata_modified` retirado; botões **Excel** e **PDF** da tabela (`ExportarTabela`, ADR-0031) | Humberto |
| 13/11/2026 | Critérios da GEDA (ADR-0037, substitui a ADR-0023): indicador sobre **todos** os datasets publicados (do PDA ou espontâneos) com a periodicidade só do campo "Atualização" do CKAN; `regras.periodicidade_ckan`, situações "Sem atualização periódica", "Periodicidade não informada" e "Sem data de atualização" (saem "Sem informação", "Sem periodicidade definida" e "Múltipla"); `listagem.situacoes_dos_datasets` como fonte única para tela, painel e relatórios; API com `tipo_base` (filtro e coluna, PBI-82) e novo `resumo`; tela com cartão "Periodicidade não informada" e coluna "Tipo de base" | Victor |
