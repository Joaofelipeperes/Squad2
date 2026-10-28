# Módulo `inventario` — Coleta e inventário do CKAN

| | |
|---|---|
| **Status** | Implementado (coleta, API e tela Datasets) |
| **Responsável** | João (base comum) |
| **User stories** | US5 (PBI-07 a PBI-11), US23 (PBI-71, PBI-74), US19 (PBI-58) |
| **Backend** | `backend/app/modules/inventario/` · cliente em `backend/app/integrations/ckan/client.py` |
| **Frontend** | `frontend/src/modules/datasets/` · botão e data da coleta em `frontend/src/app/layout/Topbar.tsx` |
| **Última atualização** | 28/10/2026 |

## Propósito
Espelha diariamente o inventário do portal (organizações, datasets, recursos e metadados) num banco
local, para que nenhum indicador dependa de consulta ao CKAN em tempo de tela.

## Telas
| Tela | Rota | Permissão para ver | Ações na tela (permissão) |
|---|---|---|---|
| Datasets | `/datasets` | `inventario.acessar` | Busca e filtros (Órgão, Formato, Status), "Limpar filtros"; detalhe do dataset com a lista de recursos (clique ou Enter na linha); prazo, periodicidade e situação do PDA no detalhe só com `pda.acessar` (PBI-83) |
| Topbar (todas as telas) | — | autenticado | "Última coleta" (todos); botão **Atualizar dados** (`inventario.coletar`) |

Referência visual: `#screen-datasets` do Protótipo V1.

- **Tabela**: Dataset (título; name no `title`) | Órgão | ID CKAN (abreviado; completo no `title`) |
  Qtd. recursos (válidos) | Última atualização (maior `last_modified` dos recursos válidos; "(est.)"
  quando veio da criação) | Formato (badges dos formatos dos recursos válidos) | Status (situação no
  **portal**: Publicado / Sem recurso / Fora do portal). Contador "N encontrado(s) de M no inventário".
- **Filtros** (no backend): busca por título ou name (sem acento, com espera de 300 ms), Órgão,
  Formato e Status — opções vindas da própria lista.
- **Detalhe** (`DatasetDetalheModal.tsx`, `showDatasetDetails` do protótipo): nome, órgão, ID, name,
  data de publicação (`metadata_created`), periodicidade, última atualização real, **última alteração
  de metadados** (`metadata_modified`, com o aviso de que não indica atualização dos dados), formatos,
  recursos válidos, status no portal, licença, descrição (`notes`) e a tabela dos recursos atuais
  (nome, formato, `last_modified` ou criação "(est.)", dicionário marcado, link). Com `pda.acessar`:
  prazo previsto, periodicidade e situação PDA da base vinculada **pelo ID** (PDA vigente primeiro;
  sem vínculo, "Nenhuma base do PDA vinculada"). "Situação de atualização" e "Histórico recente"
  aparecem como pendentes (módulos `atualizacoes` e `rastreabilidade`).

## API
| Método | Rota (`/api/v1/inventario`) | Permissão | Descrição |
|---|---|---|---|
| GET | `/coletas/ultima` | autenticado | Data/hora e status da última coleta (topbar) |
| GET | `/coletas?limite=30` | `inventario.acessar` | Histórico de coletas |
| POST | `/coletas` | `inventario.coletar` | Força nova coleta em segundo plano; 409 se já houver uma em execução |
| GET | `/datasets?busca=&orgao=&formato=&situacao=` | `inventario.acessar` | `DatasetsOut`: total (sem filtros), opções dos filtros e as linhas (`DatasetOut`: `id`, `id_ckan`, `organizacao_id`…) por título; `orgao` = `id` da organização; escopo de órgão |
| GET | `/datasets/{id}` | `inventario.acessar` | `DatasetDetalheOut`: linha + descrição, `metadata_created`, `periodicidade_declarada`, licença, recursos atuais (`RecursoOut`) e `recursos_removidos`; **404** se não existe ou é de outro órgão |

## Serviços e métodos
`dao.py` — `InventarioDao(Dao)` (ADR-0019) concentra todo acesso ao banco: coletas (`coleta_em_andamento`, `ultima_coleta`, `historico_coletas`, `criar_coleta`), espelho do CKAN (`organizacoes_por_id_ckan`, `dataset_por_id_ckan`, `recursos_por_id_ckan`, `salvar_recurso`, `marcar_fora_do_portal`, `gravar_fotografia`) e tela Datasets (`datasets_visiveis`, `dataset_visivel`, `organizacoes`). Registros excluídos (`deleted`) nunca aparecem; a coleta casa pelo `id_ckan` entre os ativos e grava pela auditoria do DAO (sistema: sem usuário; coleta manual: `created_id` = quem pediu).

`service.py`:
- `iniciar(db, origem, solicitante=None, usuario_id=None) -> Coleta` — registra a coleta; `ColetaEmAndamento` se já houver uma.
- `executar(coleta_id, client=None)` — percorre `organization_list` e `package_search` paginado,
  faz upsert casando organização, dataset e recurso pelo `id_ckan` (a PK `id` é própria — ADR-0018), grava `dataset_snapshot` e marca como inativos os datasets que sumiram. Abre sessão própria.
- `ultima_coleta(db)` · `coleta_em_andamento(db)` · `job_coleta_diaria()`.
- `listar_datasets(db, user, *, busca, orgao, formato, situacao) -> DatasetsOut` e
  `obter_dataset(db, dataset_id, user) -> DatasetDetalheOut` (`DatasetNaoEncontrado`) — tela Datasets
  (PBI-83); recursos em lote (`selectinload`), escopo de órgão por `filtrar_por_orgao`.

`regras.py` (funções puras, reaproveitáveis numa extensão CKAN):
- `parse_ckan_datetime(str)` — ISO sem fuso do CKAN 2.9 → UTC.
- `eh_dicionario_de_dados(nome, descricao)` — heurística provisória (PBI-11) sobre texto normalizado
  (sem acento, minúsculo, `_`/`-`/`.` viram espaço): "dicionário (de) dados" no nome ou na descrição,
  ou nome que começa com "dicionário". No portal real marca 467 de 3.066 recursos (antes 140).
- `recurso_atual(recurso, dataset)` — recurso veio na mesma coleta que atualizou o dataset.
- `situacao_no_portal(ativo_no_portal, recursos_validos)` — "Publicado" / "Sem recurso" / "Fora do
  portal" (`SITUACOES_NO_PORTAL`); `contem_texto(busca, *campos)` e `chave_texto(texto)` — busca e
  ordenação sem acento.

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
| `organizacao` | **id** (PK própria), **id_ckan** (ID do CKAN, único, opcional), name, titulo, sigla |
| `dataset` | **id** (PK própria), **id_ckan** (único, opcional), name, titulo, descricao (`notes` do CKAN; migração `e5b2c7a9d1f4`), organizacao_id → `organizacao.id`, autor, autor_email, licenca, periodicidade_declarada, metadata_modified (só informativo), extras (JSON), ativo_no_portal |
| `recurso` | **id** (PK própria), **id_ckan** (único, opcional), dataset_id → `dataset.id`, formato, url, url_type (upload/link), created_ckan (`created` do CKAN; o `created` da tabela é a auditoria), **last_modified**, datastore_active, eh_dicionario_dados |
| `dataset_snapshot` | coleta_id, dataset_id (`dataset.id`, referência lógica sem FK), hash_conteudo, payload (recorte estável do dataset) |

## Permissões
| Permissão | Papéis padrão |
|---|---|
| `inventario.acessar` | Administrador, Gerência GEDA, Equipe GEDA |
| `inventario.coletar` | Administrador, Gerência GEDA |

## Interações com outros módulos
| Direção | Módulo | O quê |
|---|---|---|
| consome | CKAN (integração) | API pública de leitura |
| consome | atualizacoes | `regras.ultima_atualizacao_real(recursos)` — coluna "Última atualização" da tela Datasets |
| consome | pda | `GET /pda/datasets/{id}/bases` (pelo frontend) — prazo, periodicidade e situação PDA no detalhe |
| é consumido por | pda | `Dataset` (vínculo da base prevista pelo ID, `ativo_no_portal`), `Recurso` (recursos válidos e última atualização), `Organizacao` (órgão da base) |
| é consumido por | atualizacoes, metadados | `Dataset`, `Recurso` |
| é consumido por | lgpd | `Recurso` (varredura, url_type para anonimização) |
| é consumido por | rastreabilidade | `Coleta`, `DatasetSnapshot` (diff entre coletas) |
| é consumido por | painel | `Organizacao`, `Dataset`, `Recurso` e `condicao_recurso_atual()` — telas Organizações e Dashboard; `ultima_coleta(db)` — data da coleta no Dashboard (PBI-58) |
| é consumido por | metadados | `Dataset`, `Recurso` e `condicao_recurso_atual()` — `recursos_formato_fechado` (PBI-53) |
| é consumido por | relatorios | contagens e última coleta |
| é consumido por | assistente | `ultima_coleta`, `recursos_atuais`, `regras.situacao_no_portal`; `Dataset` (sem `autor`/`autor_email`), `Recurso`, `Organizacao` — ficha do dataset citado na pergunta |
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
Decisões registradas: [ADR-0006](../adr/0006-regras-de-afericao-do-inventario.md) · [ADR-0012](../adr/0012-agendamento-em-worker-proprio.md) · [ADR-0013](../adr/0013-banco-de-dados-e-convencoes.md) · [ADR-0018](../adr/0018-chave-primaria-propria-e-id-ckan.md).

- Chave primária própria (`id`); o vínculo com o portal é sempre pelo **ID do CKAN** (`id_ckan`), nunca
  pelo `name`, que é editável pelos órgãos (ADR-0018).
- Atualização real = `last_modified` do **recurso**; `metadata_modified` não é indicador.
- Dicionário de dados é marcado (`eh_dicionario_dados`) para ser excluído das contagens; a próxima
  coleta recalcula a marcação dos recursos já gravados.
- Recurso que some do pacote do dataset não é apagado, mas deixa de contar (`recursos_atuais`).
- Datasets que somem do `package_search` (excluídos ou privados) ficam `ativo_no_portal = false`.
- **Status na tela Datasets** = situação no portal, não a do PDA (que depende do vínculo base ×
  dataset): fora do `package_search` → Fora do portal; ativo sem recurso válido → Sem recurso; senão
  Publicado. A situação do PDA aparece no detalhe quando há base vinculada pelo ID.
- Coletas simultâneas são bloqueadas.

## Pendências
- Tela Datasets: "Situação de atualização" depende da regra por periodicidade do módulo
  `atualizacoes` (PBI-27/28) e "Histórico recente" da `rastreabilidade` (US14/US29). Descrição e
  periodicidade declarada só aparecem depois de uma coleta nova (a de 08/10/2026 é anterior).
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
| 18/10/2026 | Tela Datasets (PBI-83): `GET /datasets` e `GET /datasets/{id}`, busca e filtros, Status = situação no portal, detalhe com recursos atuais, data de metadado separada da última atualização real e dados do PDA da base vinculada pelo ID; coluna `dataset.descricao` (`notes`, migração `e5b2c7a9d1f4`) | Humberto |
| 18/10/2026 | Interações: painel (tela Organizações) e metadados (formato fechado) passam a consumir `condicao_recurso_atual()` | Humberto |
| 21/10/2026 | Chave primária própria (ADR-0018): `organizacao`, `dataset` e `recurso` ganham `id` inteiro e o ID do CKAN vai para `id_ckan` (único, opcional); FKs e `dataset_snapshot.dataset_id` apontam para o `id` (migração `f6c3a8d2b1e7`, dados preservados); coleta casa pelo `id_ckan`; `GET /datasets/{id}` e `?orgao=<id>`; saídas com `id` e `id_ckan` | Victor |
| 22/10/2026 | Banco só pelo `InventarioDao` (ADR-0019): service e router sem acesso direto à sessão; coleta grava com auditoria (`iniciar(..., usuario_id=)` registra quem pediu a coleta manual); excluídos somem da tela Datasets; data de criação do recurso no CKAN em `recurso.created_ckan` (JSON `created` mantido) | Victor |
| 23/10/2026 | Interações: o que o Assistente consome deste módulo | Squad 2 |
| 28/10/2026 | Interações: o Dashboard (painel) usa as contagens do inventário e `ultima_coleta`; sem mudança de código neste módulo | Humberto |
