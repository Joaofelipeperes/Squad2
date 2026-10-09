# Módulo `inventario` — Coleta e inventário do CKAN

| | |
|---|---|
| **Status** | Implementado (coleta e API) · tela Datasets em esqueleto |
| **Responsável** | João (base comum) |
| **User stories** | US5 (PBI-07 a PBI-11), US23 (PBI-71, PBI-74), US19 (PBI-58) |
| **Backend** | `backend/app/modules/inventario/` · cliente em `backend/app/integrations/ckan/client.py` |
| **Frontend** | `frontend/src/modules/datasets/` · botão e data da coleta em `frontend/src/app/layout/Topbar.tsx` |
| **Última atualização** | 08/10/2026 |

## Propósito
Espelha diariamente o inventário do portal (organizações, datasets, recursos e metadados) num banco
local, para que nenhum indicador dependa de consulta ao CKAN em tempo de tela.

## Telas
| Tela | Rota | Permissão para ver | Ações na tela (permissão) |
|---|---|---|---|
| Datasets | `/datasets` | `inventario.acessar` | Detalhe do dataset e lista de recursos (PBI-83 — a implementar) |
| Topbar (todas as telas) | — | autenticado | "Última coleta" (todos); botão **Atualizar dados** (`inventario.coletar`) |

Referência visual: `#screen-datasets` do Protótipo V1.

## API
| Método | Rota (`/api/v1/inventario`) | Permissão | Descrição |
|---|---|---|---|
| GET | `/coletas/ultima` | autenticado | Data/hora e status da última coleta (topbar) |
| GET | `/coletas?limite=30` | `inventario.acessar` | Histórico de coletas |
| POST | `/coletas` | `inventario.coletar` | Força nova coleta em segundo plano; 409 se já houver uma em execução |

## Serviços e métodos
`service.py`:
- `iniciar(db, origem, solicitante=None) -> Coleta` — registra a coleta; `ColetaEmAndamento` se já houver uma.
- `executar(coleta_id, client=None)` — percorre `organization_list` e `package_search` paginado,
  faz upsert, grava `dataset_snapshot` e marca como inativos os datasets que sumiram. Abre sessão própria.
- `ultima_coleta(db)` · `coleta_em_andamento(db)` · `job_coleta_diaria()`.

`regras.py` (funções puras, reaproveitáveis numa extensão CKAN):
- `parse_ckan_datetime(str)` — ISO sem fuso do CKAN 2.9 → UTC.
- `eh_dicionario_de_dados(nome, descricao)` — heurística provisória (PBI-11) sobre texto normalizado
  (sem acento, minúsculo, `_`/`-`/`.` viram espaço): "dicionário (de) dados" no nome ou na descrição,
  ou nome que começa com "dicionário". No portal real marca 467 de 3.066 recursos (antes 140).
- `recurso_atual(recurso, dataset)` — recurso veio na mesma coleta que atualizou o dataset.

`service.py` (consultas para os outros módulos):
- `recursos_atuais(ds) -> list[Recurso]` e `condicao_recurso_atual()` (mesma regra em SQL): só os
  recursos ainda presentes no pacote do dataset. Recurso apagado do CKAN fica no banco (achados LGPD
  e correções apontam para ele), mas não conta para publicação nem atualização.
- `periodicidade_declarada(extras, pkg)` — periodicidade informada pelo órgão. Procura nos extras,
  sem diferenciar acento/maiúsculas/espaços, `periodicidade` e depois `Atualização` (chave usada
  no portal de Goiás); cai no campo `periodicidade` do pacote.
- `extras_como_dict(extras)` · `snapshot_payload(pkg)` · `hash_payload(payload)`.

`integrations/ckan/client.py`: `CkanClient.action`, `.organizations()`, `.iter_datasets()`,
`.dataset(id)`, `.resource(id)` — com retentativa exponencial em 5xx/429. `.organizations()`
pagina por `offset` de 25 em 25: o CKAN 2.9 limita `organization_list` com `all_fields=True` a 25
itens por chamada e o portal tem 51 órgãos.

## Modelo de dados
Diagrama e dicionário de dados completos: [MER](../banco/mer.md) · regras: [convenções do banco](../banco/convencoes.md).

| Tabela | Colunas relevantes |
|---|---|
| `coleta` | iniciada_em, finalizada_em, status (executando/ok/erro), origem (agendada/manual), solicitada_por, totais, erro |
| `organizacao` | **ckan_id** (PK), name, titulo, sigla |
| `dataset` | **ckan_id** (PK), name, titulo, organizacao_id, autor, autor_email, licenca, periodicidade_declarada, metadata_modified (só informativo), extras (JSON), ativo_no_portal |
| `recurso` | **ckan_id** (PK), dataset_id, formato, url, url_type (upload/link), created, **last_modified**, datastore_active, eh_dicionario_dados |
| `dataset_snapshot` | coleta_id, dataset_id, hash_conteudo, payload (recorte estável do dataset) |

## Permissões
| Permissão | Papéis padrão |
|---|---|
| `inventario.acessar` | Administrador, Gerência GEDA, Equipe GEDA |
| `inventario.coletar` | Administrador, Gerência GEDA |

## Interações com outros módulos
| Direção | Módulo | O quê |
|---|---|---|
| consome | CKAN (integração) | API pública de leitura |
| é consumido por | pda | `Dataset` (vínculo da base prevista pelo ID, `ativo_no_portal`), `Recurso` (recursos válidos e última atualização), `Organizacao` (órgão da base) |
| é consumido por | atualizacoes, metadados | `Dataset`, `Recurso` |
| é consumido por | lgpd | `Recurso` (varredura, url_type para anonimização) |
| é consumido por | rastreabilidade | `Coleta`, `DatasetSnapshot` (diff entre coletas) |
| é consumido por | painel, relatorios, assistente | contagens e última coleta |
| é consumido por | acesso, envio | `Organizacao` (escopo de órgão) |

## Jobs agendados
| Job | Cron | Função |
|---|---|---|
| `inventario.coleta_diaria` | `GDA_COLETA_CRON` (padrão `0 3 * * *`, America/Sao_Paulo) | `job_coleta_diaria` — roda no processo `app.worker` |

## Ambiente de testes com o CKAN local
O CKAN em Docker da raiz do repositório serve de portal de testes. Para a coleta enxergá-lo, suba
o produto final com `docker-compose.ckan-local.yml` (coloca `api` e `worker` na rede do CKAN e
define `GDA_CKAN_BASE_URL=http://ckansquad2-ckan-1:5000`). Os dados devem ser carregados com
`importar_ckan_goias.py`, que preserva os IDs e o `last_modified` dos recursos do portal.

## Regras de negócio e decisões
Decisões registradas: [ADR-0006](../adr/0006-regras-de-afericao-do-inventario.md) · [ADR-0012](../adr/0012-agendamento-em-worker-proprio.md) · [ADR-0013](../adr/0013-banco-de-dados-e-convencoes.md).

- Chave de tudo é o **ID do CKAN**; o `name` é editável pelos órgãos.
- Atualização real = `last_modified` do **recurso**; `metadata_modified` não é indicador.
- Dicionário de dados é marcado (`eh_dicionario_dados`) para ser excluído das contagens; a próxima
  coleta recalcula a marcação dos recursos já gravados.
- Recurso que some do pacote do dataset não é apagado, mas deixa de contar (`recursos_atuais`).
- Datasets que somem do `package_search` (excluídos ou privados) ficam `ativo_no_portal = false`.
- Coletas simultâneas são bloqueadas.

## Pendências
- Tela Datasets (PBI-83).
- Confirmar com a GEDA o critério de dicionário de dados (PBI-11), inclusive o novo "nome começa com
  dicionário" (ex.: "DICIONARIO CONVENIOS CONCEDIDOS DGPP"); "DICIONARI0" (com zero) não é detectado.
- `periodicidade_declarada` lida do extra `periodicidade`, mas no portal real a chave observada é
  `Atualização` (coleta de 07/10/2026) — hoje o campo fica vazio; ajustar a leitura (US9/US10).

## Histórico de alterações
| Data | Alteração | Autor |
|---|---|---|
| 30/09/2026 | Estrutura inicial: coleta, snapshots, API e job diário | Victor |
| 30/09/2026 | Rotas com permissões do catálogo central (`inventario.acessar`, `inventario.coletar`) | Victor |
| 07/10/2026 | Docstring nas tabelas sem descrição, para o MER gerado (ADR-0013); sem mudança de esquema | Victor |
| 07/10/2026 | Correção: coleta falhava no portal real (FK de organização) porque `organizations()` trazia só 25 dos 51 órgãos; agora pagina por `offset`; e `executar` faz `flush()` dos órgãos antes dos datasets (sem relationship, o SQLAlchemy não garantia a ordem dos INSERTs). Coleta real de 07/10: 51 órgãos, 447 datasets, 3.066 recursos | Humberto |
| 07/10/2026 | Interações: pda passa a consumir também `Recurso` e `Organizacao` | Humberto |
| 08/10/2026 | Dicionário de dados detectado em texto normalizado e por nome iniciado em "dicionário" (467 recursos no portal real, antes 140); `recursos_atuais`/`condicao_recurso_atual`: recurso apagado do CKAN deixa de contar (achados da revisão do pda) | Humberto |
| 08/10/2026 | Periodicidade lida também do extra `Atualização` do portal (`regras.periodicidade_declarada`); `docker-compose.ckan-local.yml` liga a coleta ao CKAN local | João |
