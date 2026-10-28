# Módulo `rastreabilidade` — Linha do tempo de mudanças

| | |
|---|---|
| **Status** | Parcial (auditoria do CKAN para datasets; comparação entre coletas para órgãos; diff de datasets entre coletas pendente) |
| **Responsável** | João (US29, diff) · Humberto (tela) |
| **User stories** | US14 (PBI-43 a PBI-45, PBI-85), US29 (PBI-69, PBI-70) |
| **Backend** | `backend/app/modules/rastreabilidade/` |
| **Frontend** | `frontend/src/modules/rastreabilidade/` |
| **Última atualização** | 23/10/2026 |

## Propósito
Registra inclusões, alterações, privações e exclusões de datasets, recursos e do cadastro dos
órgãos — hoje uma exclusão no portal não deixa rastro para a GEDA. Fontes
([ADR-0009](../adr/0009-fonte-da-rastreabilidade.md)): para datasets, recursos e DataStore, a
auditoria gravada no próprio CKAN pela extensão `ckanext-dsaudit` (opção A); para o cadastro dos
órgãos, que a extensão não audita, a comparação entre coletas (opção C); para ações em dataset
que não passam pela edição auditada (Make public/Make private/Delete em lote na página da
organização, `package_patch`), as atividades nativas do CKAN sem registro da extensão.

## Telas
| Tela | Rota | Permissão para ver | Ações na tela (permissão) |
|---|---|---|---|
| Rastreabilidade | `/rastreabilidade` | `rastreabilidade.acessar` | Busca por dataset ou órgão; filtros por tipo de alteração, órgão e período (de/até); ordenação por data; "Ver detalhes" de cada evento; "Ver diff do arquivo" quando houver comparação linha a linha |

Referência visual: `#screen-traceability` do Protótipo V1 (linha do tempo em linguagem humana,
PBI-85). Cada cartão mostra tipo, data e hora (Brasília), órgão · dataset · recurso, uma frase com
o que mudou e o usuário do CKAN; "Ver detalhes" lista campo, valor anterior e novo. Acima do
painel, a situação da última leitura da auditoria (datasets lidos, eventos novos, datasets sem
permissão) ou o motivo de não ter sido concluída. A tela mostra até 300 eventos que atendem aos
filtros, dos mais recentes (padrão) ou dos mais antigos. A busca por dataset ignora acentos e
maiúsculas e procura no título e no nome atuais (inventário), no título da data do evento e no ID.
O período usa datas do horário de Brasília (dia inteiro, inclusive).

Eventos de ações fora da edição auditada mostram a etiqueta "Fora da auditoria".
Eventos do cadastro do órgão mostram a etiqueta "Cadastro do órgão" no lugar do dataset e, no
lugar do usuário, "Usuário: … · detectado na coleta" (autoria lida das atividades do CKAN) ou
"Detectado na coleta · usuário não identificado" (sem token ou sem acesso a elas).

"Ver diff do arquivo" aparece em trocas de arquivo comparadas e em atualizações do DataStore com
valores anteriores: abre uma tabela com linha (chave ou posição), situação (incluída, alterada,
removida), coluna, valor antes e depois, lida do CKAN no momento do clique (ver Privacidade).

## API
| Método | Rota (`/api/v1/rastreabilidade`) | Permissão | Descrição |
|---|---|---|---|
| GET | `/eventos?busca=&tipo=&orgao=&dataset=&desde=&ate=&ordem=recentes&limite=300` | `rastreabilidade.acessar` | Linha do tempo, opções dos filtros e última sincronização. `tipo` aceita o código ou o rótulo; `desde`/`ate` em ISO 8601; `ordem` = `recentes` ou `antigos`; `limite` até 2000. Escopo de órgão aplicado |
| GET | `/eventos/{id}/diff` | `rastreabilidade.acessar` | Diff linha a linha do evento, lido do CKAN na hora (não gravado). 404 = evento inexistente ou de outro órgão; 409 = evento sem diff, token não configurado ou falha ao ler o CKAN |

## Serviços e métodos
`service.py`:
- `sincronizar(client=None, orgaos=None) -> int` — (1) se `orgaos` vier da coleta, compara o
  cadastro de cada órgão com a última fotografia (`_comparar_orgaos`), sem depender de token;
  (2) para cada dataset do inventário (inclusive os que saíram do portal), lê `dsaudit_activity_list` da mais recente para a mais antiga e grava as atividades
  novas como `EventoRastreabilidade` (uma atividade pode gerar mais de um evento, numerados por
  `sequencia`); para na primeira atividade já conhecida (incremental). HTTP 403 e
  404 contam como "sem permissão" e "não encontrado" e não interrompem a leitura. Sem
  `GDA_CKAN_AUDITORIA_API_TOKEN` a sincronização fica "ignorada"; 403 em todos os datasets = "erro".
  Abre sessão própria; chamada ao fim de cada coleta concluída (`inventario.executar`).
- `listar_eventos(db, user, *, tipo, orgao, dataset, busca, desde, ate, ordem, limite) -> EventosOut`
  — tela; escopo de órgão por `filtrar_por_orgao`; a busca usa `inventario.regras.contem_texto`.
- `diff_evento(db, user, evento_id, client=None) -> DiffOut` — localiza a atividade no CKAN
  (`dsaudit_activity_list` filtrada pelo recurso e pelo tipo) e devolve as linhas diferentes;
  `EventoNaoEncontrado` (também para evento de outro órgão) e `DiffIndisponivel`.
- `ultima_sincronizacao(db)`.
- `_comparar_orgaos(db, orgaos, client=None, usuarios=None) -> int` — grava uma fotografia nova só
  quando o cadastro mudou ou o órgão sumiu da listagem, e o evento correspondente. Na primeira
  execução (sem fotografias) só registra a base, sem eventos. Com `client` (token), chama
  `_autoria_orgao`.
- `_autoria_orgao(client, org_id, desde, ate, usuarios)` — lê `organization_activity_list` (até 10
  páginas de 100) e devolve (data, usuário) das atividades "new/changed/deleted organization"
  entre a fotografia anterior e a atual; erro do CKAN → lista vazia (evento sem autor).
- `_ler_atividades_nativas(db, client, datasets, conhecidos, usuarios, inicio_sinc) -> int` — para
  os datasets cuja auditoria foi lida, lê `package_activity_list` desde a última marca
  (`atividades_nativas_ate`, menos 10 min; nunca antes do primeiro registro da extensão) e grava as
  atividades nativas **sem par** (nenhuma atividade da extensão do mesmo dataset a menos de 2 s).
- `_eventos_da_orfa(...)` — o que mudou numa órfã: compara a versão completa do dataset guardada
  pelo CKAN nessa atividade com a da atividade nativa anterior (`activity_data_show`); se houve
  edição auditada entre as duas, atribui à órfã só a visibilidade; sem acesso às versões, estima a
  visibilidade (`regras.resolver_visibilidade`). Nada mudou (salvar sem alterar) → sem evento.
  Ação em lote (`regras.versao_anterior_a_acao`): a versão guardada é a de **antes** da ação; o
  estado depois dela é o de antes da atividade seguinte (`_privado_antes_de`) ou o atual. A
  exclusão em lote é reconhecida pelo tipo da atividade ("deleted package").
- `diff_coletas(db, coleta_anterior_id, coleta_atual_id)` — contrato do PBI-43 (opção C da ADR-0009),
  complemento para quando a extensão não estiver instalada. Não implementado.

`regras.py` (funções puras, reaproveitáveis numa extensão CKAN):
- `classificar(activity_type, data) -> list[EventoClassificado]` — atividade da extensão → eventos
  (tipo, resumo em linguagem humana, detalhes e se há diff); lista vazia = tipo não monitorado:

| Atividade no CKAN | Tipo na tela |
|---|---|
| `changed metadata`, método `created` | Inclusão |
| `changed metadata`, método `deleted` | Exclusão |
| `changed metadata` com `private` → verdadeiro | Privação; se a mesma gravação mudou outros campos (título, autor, recursos...), eles viram um segundo evento de **Alteração**, na mesma data |
| demais `changed metadata` (campos do dataset, recursos incluídos, alterados ou removidos; tornar público) | Alteração |
| `changed resource file` (arquivo enviado ou substituído) e `created/changed/deleted datastore` | Recurso atualizado |

- `rotulo_campo(escopo, campo)` — nome do campo em português (ex.: `author` → autor,
  `created` do recurso → data de publicação, `extras.x` → campo extra "x").
- `parse_timestamp(str)` — `timestamp` da atividade (ISO, UTC) → datetime com fuso.
- `linhas_do_diff(changes) -> (linhas, total)` — `changes` da troca de arquivo ou do DataStore →
  linhas para a tela (até 500), só para exibição.
- `payload_orgao(org)` — cadastro do órgão achatado: campos do próprio órgão (título, nome,
  descrição, imagem e campos personalizados de primeiro nível) e cada campo extra como
  `extras.<chave>`; ignora contagens e campos derivados (`package_count`, `display_name`...).
- `hash_payload(payload)` · `comparar_orgao(antes, depois) -> EventoClassificado | None` —
  Alteração (campos que mudaram), Inclusão (`antes` vazio) ou Exclusão (`depois` vazio).
- `nativas_orfas(nativas, auditadas)` — atividades nativas "new/changed/deleted package" sem
  atividade da extensão do mesmo dataset a menos de `JANELA_PAR_SEGUNDOS` (2 s; na edição comum as
  duas ficam a centésimos de segundo).
- `mudancas_pacote(antes, depois)` — diferença entre duas versões completas do dataset, no mesmo
  formato de `changes` da extensão (mesmos campos ignorados) · `classificar_orfa(activity_type,
  antes, depois, mudancas=None) -> list[EventoClassificado]` — com `mudancas`, mesmo tratamento
  da extensão (privação vira evento próprio); sem elas, só a visibilidade.
- `versao_anterior_a_acao(versao, quando)` — a versão guardada na atividade é a de antes da ação?
  Nas ações em lote do CKAN 2.9 (`bulk_update_private/public/delete`) o banco é alterado por SQL
  direto, `metadata_modified` não muda e a versão vem do cache do Solr ainda não reindexado; por
  isso `metadata_modified` mais de 2 s antes da atividade identifica a ação em lote.
- `resolver_visibilidade(orfas, marcos, atual, base)` — estimativa da visibilidade antes/depois de
  cada órfã quando as versões do CKAN não podem ser lidas.
- `autoria_no_intervalo(atividades, desde, ate)` — filtra as atividades do próprio órgão no
  intervalo (ignora as dos datasets do órgão) · `texto_autoria(autoria)` — "ana em 22/10/2026
  20:00; bruno em …" (horário de Brasília).

Integração (`integrations/ckan/client.py`): `CkanClient(api_token=...)`, `auditoria_dataset(id,
limit, offset, resource_id=None, activity_type=None)`, `atividades_orgao(org_id, limit, offset)`
(`organization_activity_list`), `usuario(id)`; exceções `CkanAcessoNegado` (403) e `CkanNaoEncontrado` (404).

## Modelo de dados
| Tabela | Descrição |
|---|---|
| `rastreabilidade_evento` | Um evento da linha do tempo: `origem` (`auditoria_ckan` ou `comparacao_coletas`); na auditoria, atividade (`ckan_activity_id`) e parte dela (`sequencia`, únicos juntos); na comparação, a fotografia do órgão (`orgao_snapshot_id`, FK, único); data, tipo, `activity_type` do CKAN (`organization` na comparação), dataset (ID e título na data; vazio em evento de órgão), órgão, recurso, usuário do CKAN (vazio na comparação), resumo, `detalhes` (JSON) e `tem_diff`. Somente inserção; `dataset_id` e `organizacao_id` sem FK (referências lógicas) |
| `rastreabilidade_orgao_snapshot` | Fotografia do cadastro de um órgão (`payload` achatado, `hash_conteudo`, `ativo`), gravada só quando muda. Somente inserção; `organizacao_id` sem FK |
| `rastreabilidade_sincronizacao` | Cada leitura: status (`executando`, `ok`, `erro`, `ignorada`), órgãos comparados, datasets lidos, sem permissão, não encontrados, eventos novos, erro e `atividades_nativas_ate` (até quando as atividades nativas já foram lidas) |

Migrações `56cbf1b07f2c` (tabelas), `7a3d9e2b4c61` (`sequencia`, `tem_diff` e unicidade por
atividade + parte), `b8e4c1f07d25` (dados: apaga os eventos gravados com a regra antiga; a próxima
sincronização relê a auditoria inteira do CKAN) e `c2d7f4a8e913` (fotografia dos órgãos, `origem`,
`orgao_snapshot_id`, dataset opcional, `orgaos_consultados`; eventos existentes ficam com origem
`auditoria_ckan`) e `d5e1a9c3b742` (`atividades_nativas_ate`; eventos da origem
`atividade_nativa` usam as colunas existentes).

**Privacidade:** de arquivos e do DataStore são guardados só contagens de linhas e nomes de
colunas, nunca valores de linhas (que podem conter dado pessoal; continuam apenas no CKAN). O diff
com valores é lido do CKAN a cada clique em "Ver diff do arquivo", exibido e descartado: não vai para
o banco da solução. De metadados (campos de publicação) guardam-se valor anterior e novo, cortados
em 300 caracteres, até 60 itens por evento.

## Como os registros são gravados

O fluxo roda inteiro no backend, ao fim de cada coleta concluída (botão "Atualizar dados" ou coleta
diária). A tela só lê o que já está gravado no banco do produto final.

1. **Coleta** (`inventario.executar`): baixa órgãos (`organization_list`, com campos extras) e
   datasets (`package_search`), atualiza o inventário e chama `rastreabilidade.sincronizar`
   passando a lista de órgãos.
2. **Sincronização**: grava uma linha em `rastreabilidade_sincronizacao` (status `executando`).
3. **Cadastro dos órgãos** (`_comparar_orgaos`), sem token:
   - cada órgão vira um `payload` achatado (`payload_orgao`) e um `hash_conteudo` (SHA-256);
   - se o hash é igual ao da última fotografia do órgão, nada é gravado;
   - se mudou, grava uma fotografia nova em `rastreabilidade_orgao_snapshot` e um evento em
     `rastreabilidade_evento` com `origem = comparacao_coletas`, `orgao_snapshot_id` da fotografia,
     sem dataset, com o antes e depois de cada campo em `detalhes`;
   - com o token, completa o evento com a autoria: lê as atividades nativas do órgão no CKAN
     ("changed organization") entre a fotografia anterior e a atual e grava em `usuario` quem
     alterou (todos, se mais de um), em `ocorrido_em` a data da alteração mais recente e em
     `detalhes` um item "alterações registradas no CKAN no período" com cada usuário e horário;
   - órgão que sumiu da listagem ganha fotografia com `ativo = false` e evento de Exclusão.
4. **Auditoria do CKAN** (com `GDA_CKAN_AUDITORIA_API_TOKEN`): para cada dataset do inventário,
   lê `dsaudit_activity_list` e grava as atividades novas com `origem = auditoria_ckan`,
   `ckan_activity_id` e `sequencia`, usuário e data do CKAN. Sem token, esta etapa fica
   "ignorada" (a etapa 3 continua valendo).
4b. **Ações fora da auditoria** (com o token): para os mesmos datasets, lê as atividades nativas
   novas (`package_activity_list`). As que têm atividade da extensão do mesmo dataset a menos de
   2 s são a mesma edição e são ignoradas (não duplica). As **sem par** viram evento com
   `origem = atividade_nativa`, `ckan_activity_id` da atividade nativa, usuário e data do CKAN; o
   que mudou vem da comparação entre a versão do dataset guardada nessa atividade e a da
   atividade nativa anterior (`activity_data_show`). Salvar sem alterar nada não gera evento.
   Exceção: na ação em lote o CKAN guarda a versão de **antes** da ação (ver
   `versao_anterior_a_acao`); a visibilidade depois dela é lida na atividade seguinte.
5. **Fim**: a linha de `rastreabilidade_sincronizacao` recebe status, contagens e erro.

**Formato:** os três tipos de evento ficam na mesma tabela e na mesma linha do tempo, com o mesmo
formato de `detalhes` (`escopo`, `campo`, `anterior`, `novo`); o que muda é a `origem` e quais
colunas vêm preenchidas:

| Coluna | `auditoria_ckan` (dataset/recurso) | `atividade_nativa` (fora da auditoria) | `comparacao_coletas` (órgão) |
|---|---|---|---|
| `ckan_activity_id`, `sequencia` | ID da atividade da extensão e parte | ID da atividade nativa e parte | vazio, 0 |
| `orgao_snapshot_id` | vazio | vazio | fotografia em que a diferença foi detectada |
| `ocorrido_em` | data da alteração no CKAN | data da atividade nativa | data da última alteração do órgão no CKAN (atividade nativa); sem ela, data da coleta que detectou |
| `dataset_id`, `dataset_titulo` | preenchidos | preenchidos | vazios |
| `usuario` | usuário do CKAN | usuário do CKAN | usuário(s) das atividades nativas do órgão no período; vazio se não houver token ou acesso |
| `activity_type` | tipo da atividade da extensão | `new/changed/deleted package` | `organization` |
| `detalhes[].escopo` | `dataset`, `resource` ou vazio (arquivo/DataStore) | `dataset`/`resource` e uma observação | `orgao` |

Nada é alterado ou apagado depois de gravado (somente inserção); a releitura nunca duplica eventos
(unicidade por atividade + parte e por fotografia).

## Configuração
| Variável | Uso |
|---|---|
| `GDA_CKAN_AUDITORIA_API_TOKEN` | Token de API de um usuário **editor** das organizações monitoradas (a API da extensão exige permissão de edição no dataset; sysadmin não é necessário). Vazio = sem sincronização |

No ambiente local, `docker-compose.ckan-local.yml` preenche a variável com `CKAN_AUDITORIA_API_TOKEN`
ou, na falta dela, com o `CKAN_API_KEY` deixado pelo `subir_ambiente.ps1` (administrador do CKAN
local). Para testar com permissão mínima, gere o token de um editor e defina
`CKAN_AUDITORIA_API_TOKEN` antes de subir.

## Permissões
| Permissão | Papéis padrão |
|---|---|
| `rastreabilidade.acessar` | Administrador, Gerência GEDA, Equipe GEDA |

## Interações com outros módulos
| Direção | Módulo | O quê |
|---|---|---|
| consome | CKAN (integração) | `dsaudit_activity_list` (sincronização e diff sob demanda), `package_activity_list` e `activity_data_show` (ações fora da auditoria), `organization_activity_list` (autoria das mudanças em órgãos) e `user_show`, com token de editor |
| consome | inventario | `Dataset` (datasets lidos, título e órgão), `Recurso` (nome do recurso), `Organizacao` (nome do órgão); `Coleta`, `DatasetSnapshot` para o diff futuro |
| é acionado por | inventario | `sincronizar(orgaos=...)` ao fim de cada coleta concluída, com a lista de órgãos que a coleta acabou de baixar (`organization_list` com campos extras) |
| consome | pda | destacar mudança em base do PDA já cumprida (PBI-45) — pendente |
| é consumido por | relatorios | mudanças do período por órgão (PBI-44) — pendente |

## Jobs agendados
Sem job próprio: a sincronização roda ao fim de cada coleta (agendada pelo `inventario.coleta_diaria`
ou manual pelo botão "Atualizar dados").

## Regras de negócio e decisões
Decisões registradas: [ADR-0009](../adr/0009-fonte-da-rastreabilidade.md) (Aceita, opção A).

- Vínculo pelo ID do dataset; o título exibido é o da data do evento (gravado pela extensão).
- Privação é sempre um evento próprio: o que mais mudou na mesma gravação vira um evento de
  Alteração separado (mesma data e usuário).
- O órgão do evento é o do dataset no inventário no momento da sincronização.
- Cadastro do órgão: a extensão não o audita. O que mudou é detectado comparando com a coleta
  anterior (várias mudanças entre duas coletas aparecem juntas; mudanças desfeitas antes da coleta
  seguinte não aparecem). Quem alterou e quando vêm das atividades nativas do CKAN no intervalo:
  se mais de uma pessoa alterou, o evento lista todas, sem saber qual campo cada uma mudou;
  alterações do usuário interno do CKAN (cargas automáticas) ficam ocultas nessa listagem. Órgão que
  some da listagem gera Exclusão; órgão novo, Inclusão (exceto na primeira execução, que só
  registra a base).
- Ações fora da edição auditada: só datasets cuja auditoria o token consegue ler; atividades
  nativas anteriores ao primeiro registro da extensão não são consideradas (não há com o que
  parear). No CKAN 2.9, edição comum de dataset privado não gera atividade nativa — nesse caso só
  a extensão registra, sem conflito. Se as versões do CKAN não puderem ser lidas, só a
  visibilidade é estimada ("campos não identificados").
- Datasets que nunca apareceram numa coleta (privados desde a criação, ou criados e excluídos entre
  duas coletas) não são lidos.

## Pendências
- Diff de datasets entre coletas (PBI-43) como complemento quando a extensão não estiver instalada.
- Autoria campo a campo das mudanças em órgãos depende de a extensão passar a auditá-los (ADR-0009,
  opção A estendida; exige alterar a extensão e nova instalação pela SECTI).
- Destaque para base do PDA já cumprida (PBI-45) e relatório de mudanças por órgão (PBI-44).
- Instalação da extensão no portal oficial (SECTI).

## Histórico de alterações
| Data | Alteração | Autor |
|---|---|---|
| 30/09/2026 | Esqueleto: contrato `diff_coletas` e permissão | Victor |
| 21/10/2026 | Linha do tempo pela auditoria do CKAN (ADR-0009, opção A): tabelas `rastreabilidade_evento` e `rastreabilidade_sincronizacao` (migração `56cbf1b07f2c`), sincronização incremental ao fim da coleta com token de editor (`GDA_CKAN_AUDITORIA_API_TOKEN`), `GET /eventos` com filtros e escopo de órgão, tela conforme `#screen-traceability` | João |
| 22/10/2026 | Privação com outras mudanças na mesma gravação gera dois eventos (Privação e Alteração; coluna `sequencia`); busca por dataset, período e ordenação por data; diff linha a linha de arquivo/DataStore lido do CKAN sob demanda (`GET /eventos/{id}/diff`, coluna `tem_diff`), sem gravar valores; migrações `7a3d9e2b4c61` e `b8e4c1f07d25` | João |
| 23/10/2026 | Cadastro dos órgãos rastreado por comparação entre coletas (ADR-0009, revisão): tabela `rastreabilidade_orgao_snapshot`, eventos com `origem` e `orgao_snapshot_id`, dataset opcional, `orgaos_consultados` (migração `c2d7f4a8e913`); busca também por órgão; seção "Como os registros são gravados" | João |
| 23/10/2026 | Autoria das mudanças em órgãos: usuário e data lidos das atividades nativas do CKAN (`organization_activity_list`) entre a fotografia anterior e a atual, com o token de editor; sem schema novo | João |
| 23/10/2026 | Ações fora da edição auditada (Make public/Make private/Delete em lote na organização, package_patch): atividades nativas do CKAN sem par na extensão (±2 s) viram eventos `atividade_nativa`, com o que mudou pelas versões guardadas pelo CKAN (`activity_data_show`); marca `atividades_nativas_ate` (migração `d5e1a9c3b742`); etiqueta "Fora da auditoria" | João |
| 23/10/2026 | Correção: Make private em lote aparecia como "tornado público" (e vice-versa). Na ação em lote o CKAN 2.9 guarda a versão de antes da ação (cache do Solr); identificada por `metadata_modified` anterior à atividade (`regras.versao_anterior_a_acao`), o estado depois vem da atividade seguinte ou da visibilidade atual; exclusão em lote reconhecida pelo tipo da atividade. Sem schema novo | João |
