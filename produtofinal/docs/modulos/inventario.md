# Módulo `inventario` — Coleta e inventário do CKAN

| | |
|---|---|
| **Status** | Implementado (coleta e API) · tela Datasets em esqueleto |
| **Responsável** | João (base comum) |
| **User stories** | US5 (PBI-07 a PBI-11), US23 (PBI-71, PBI-74), US19 (PBI-58) |
| **Backend** | `backend/app/modules/inventario/` · cliente em `backend/app/integrations/ckan/client.py` |
| **Frontend** | `frontend/src/modules/datasets/` · botão e data da coleta em `frontend/src/app/layout/Topbar.tsx` |
| **Última atualização** | 30/09/2026 |

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
- `eh_dicionario_de_dados(nome, descricao)` — heurística provisória (PBI-11).
- `extras_como_dict(extras)` · `snapshot_payload(pkg)` · `hash_payload(payload)`.

`integrations/ckan/client.py`: `CkanClient.action`, `.organizations()`, `.iter_datasets()`,
`.dataset(id)`, `.resource(id)` — com retentativa exponencial em 5xx/429.

## Modelo de dados
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
| é consumido por | pda | `Dataset` (vínculo da base prevista pelo ID) |
| é consumido por | atualizacoes, metadados | `Dataset`, `Recurso` |
| é consumido por | lgpd | `Recurso` (varredura, url_type para anonimização) |
| é consumido por | rastreabilidade | `Coleta`, `DatasetSnapshot` (diff entre coletas) |
| é consumido por | painel, relatorios, assistente | contagens e última coleta |
| é consumido por | acesso, envio | `Organizacao` (escopo de órgão) |

## Jobs agendados
| Job | Cron | Função |
|---|---|---|
| `inventario.coleta_diaria` | `GDA_COLETA_CRON` (padrão `0 3 * * *`, America/Sao_Paulo) | `job_coleta_diaria` — roda no processo `app.worker` |

## Regras de negócio e decisões
- Chave de tudo é o **ID do CKAN**; o `name` é editável pelos órgãos.
- Atualização real = `last_modified` do **recurso**; `metadata_modified` não é indicador.
- Dicionário de dados é marcado (`eh_dicionario_dados`) para ser excluído das contagens.
- Datasets que somem do `package_search` (excluídos ou privados) ficam `ativo_no_portal = false`.
- Coletas simultâneas são bloqueadas.

## Pendências
- Tela Datasets (PBI-83).
- Confirmar com a GEDA o critério de dicionário de dados (PBI-11).
- `periodicidade_declarada` lida do extra `periodicidade` — confirmar a chave real no portal.

## Histórico de alterações
| Data | Alteração | Autor |
|---|---|---|
| 30/09/2026 | Estrutura inicial: coleta, snapshots, API e job diário | Claude / Victor |
| 30/09/2026 | Rotas com permissões do catálogo central (`inventario.acessar`, `inventario.coletar`) | Claude / Victor |
