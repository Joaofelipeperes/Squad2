# Módulo `pda` — Monitoramento do Plano de Dados Abertos

| | |
|---|---|
| **Status** | Parcial — US6 e US8 implementadas (importação, múltiplos PDAs, vigente, vínculo por ID, situação do prazo, tela); US7 (PDA × espontânea) pendente |
| **Responsável** | Humberto (Eixo 1) |
| **User stories** | US6 (PBI-12 a PBI-15), US7 (PBI-16 a PBI-18, PBI-82), US8 (PBI-19 a PBI-22, PBI-80) |
| **Backend** | `backend/app/modules/pda/` · migrações `b7e2c41d9a63_pda_planos_e_bases_previstas.py` e `c3f8a2d15e70_pda_nome_unico_sem_maiusculas.py` |
| **Frontend** | `frontend/src/modules/pda/` · upload multipart por `api.upload` em `frontend/src/shared/api/client.ts` |
| **Última atualização** | 22/10/2026 |

## Propósito
Importa a planilha do PDA (Plano de Dados Abertos), cruza cada base prevista com os datasets
publicados no CKAN (pelo ID) e mostra, por órgão, a situação do prazo de abertura. Vários PDAs
podem ficar cadastrados; o **vigente** rege a tela e os indicadores e relatórios de gestão.

## Telas
| Tela | Rota | Permissão para ver | Ações na tela (permissão) |
|---|---|---|---|
| Monitoramento do PDA | `/pda` | `pda.acessar` | Escolher o PDA exibido (padrão = vigente); filtros e "Limpar filtros"; detalhe da base (clique ou Enter na linha); **Importar PDA**, **Novo PDA** (criação manual), **Editar PDA**, **Incluir base** e, no detalhe, **Editar** e **Excluir base** (`pda.gerenciar_planos`); **Definir como vigente** só para PDA não vigente e **Excluir PDA** para não vigente ou vigente único, com confirmação em modal (`pda.gerenciar_planos`); **Atualizar vínculos (N pendentes)**, só se houver pendentes, e **Importar IDs do CKAN** (`pda.editar_vinculos`) |

- **Painel "PDA"** (acima dos filtros): select com os PDAs ("Nome (vigente)"), badge Vigente /
  Não vigente e a linha "N bases previstas · importado (ou criado manualmente) em dd/mm/aaaa por
  Fulano · vigência … · arquivo". Trocar o PDA limpa os filtros e fecha o detalhe.
- **Modal Novo PDA / Editar PDA** (`PlanoFormModal.tsx`): nome*, início e fim da vigência; na
  criação, "Definir como vigente" (marcado e travado quando é o primeiro PDA). O PDA criado nasce
  vazio e já fica selecionado. Editar não troca o vigente.
- **Modal Incluir / Editar base** (`BaseFormModal.tsx`): órgão (sigla)*, organização no portal
  (select; vazio = identificar pela sigla), base de dados*, descrição, unidade responsável,
  periodicidade (domínio), meta/prazo para abertura (data), conteúdo sigiloso (Sim / Não / Não
  informado), políticas públicas e "Disponível no portal" (link do dataset ou name). "Incluir
  base" fica acima da tabela; "Editar" e "Excluir base" (confirmação em modal), no rodapé do
  detalhe.
- **Filtros** (enviados ao backend): Órgão, Periodicidade e Ano (opções vindas de `opcoes` em
  `GET /bases`); Situação com os 6 rótulos fixos na ordem do protótipo (constante `SITUACOES` em
  `frontend/src/modules/pda/api.ts`, espelho de `regras.SITUACOES`); Prazo (Vencido / Próximos N
  dias, N = `janela_alerta_dias`).
- **Tabela**: Órgão | Base prevista (PDA) | Dataset CKAN | ID CKAN | Prazo | Periodicidade | Última
  atualização | Situação. Vínculo pendente mostra o name da planilha + badge "vínculo pendente";
  dataset inativo recebe badge "fora do portal"; ID abreviado (8 caracteres) com o completo no
  `title`; data estimada pela criação leva "(est.)". Contador "N base(s) encontrada(s) de M previstas".
- **Modal Importar PDA**, em etapas (`ImportarPdaModal.tsx`): (1) nome*, início e fim da vigência,
  arquivo .xlsx/.csv* (até 5 MB), "Definir como vigente" (marcado e travado quando é o primeiro PDA)
  → **Continuar**; (2) **mapeamento de colunas** (`MapeamentoColunas.tsx`): cada campo do sistema ao
  lado de um seletor com as colunas da planilha, pré-selecionado quando o nome é igual ou muito
  parecido (sem diferença de maiúsculas, acentos, espaços e "_"); obrigatórios sem coluna ficam em
  vermelho e bloqueiam **Importar**; coluna já usada em outro campo fica desabilitada; prévia das 5
  primeiras linhas já mapeadas; **Voltar** refaz a etapa 1. Após importar mostra o resumo (bases
  importadas, linhas ignoradas com motivo, vínculos resolvidos/pendentes, sem vínculo, órgãos sem
  correspondência), avisa quando falta a coluna "Prazo" (e lista as demais colunas opcionais
  ausentes) e seleciona o PDA novo.
- **Modal Importar IDs do CKAN** (`ImportarIdsModal.tsx`): arquivo CSV (ou .xlsx) com SIGLA,
  NOME_PDA, NOME_DATASET e ID_DATASET (ou ID_UNICO) → **Analisar arquivo** (nada é gravado) → resumo:
  bases sem ID que recebem, bases que já têm **outro** ID (lista atual → novo), já com o mesmo ID,
  linhas sem base correspondente, linhas com problema no ID (não é UUID, fora do inventário, mesma
  base com IDs diferentes) e linhas sem ID; caixa **Sobrescrever** (desmarcada) para as bases com
  outro ID → **Gravar N IDs** → resumo final e recarga da tabela.
- **Modal de detalhe** (`showDatasetDetails` do protótipo): nome, órgão, unidade, ID do dataset,
  dataset no portal, prazo, data de publicação (`metadata_created` do dataset vinculado e ativo;
  sem vínculo, "Não publicado"), periodicidade (+ original da planilha), última atualização real,
  recursos válidos, formatos dos recursos (sem repetição; formato é atributo do recurso), situação, conteúdo sigiloso, políticas públicas, PDA de origem e descrição;
  aviso se o dataset não está mais visível no portal; "Abrir no portal" (`/dataset/<ID>`). Usa os
  dados da própria linha (não chama `GET /bases/{id}`).
- **Filtro pela URL**: `/pda?orgao=<chave>` abre a tela já filtrada pelo órgão (botão "Ver bases
  no PDA" da tela Organizações).
- **Teclado**: os modais (`shared/ui/Modal.tsx`) recebem o foco ao abrir, prendem Tab/Shift+Tab
  e devolvem o foco ao fechar; as linhas da tabela abrem o detalhe com Enter ou Espaço.
- **Estado vazio** (nenhum PDA): orienta a importar ou criar; botões "Criar PDA manualmente" e
  "Importar PDA" ou, sem permissão, "Peça à Gerência de Dados Abertos para cadastrar o PDA."

Referência visual: `#screen-pda` do Protótipo V1 (`renderPDA`, `getFilteredPDA`,
`pdaSituacaoDeadlineFlag`, `showDatasetDetails`, `statusBadge`). Ressalva de 17/09: PDA trata do
**prazo de abertura**; atualização periódica tem tela própria (módulo `atualizacoes`).

## API
| Método | Rota (`/api/v1/pda`) | Permissão | Descrição |
|---|---|---|---|
| GET | `/planos` | `pda.acessar` | PDAs cadastrados (`PlanoOut[]`): vigente primeiro, depois `importado_em` desc. Totais e vínculos respeitam o escopo de órgão do usuário |
| POST | `/planilha/colunas` | `pda.gerenciar_planos` | multipart `arquivo` → `ColunasPlanilhaOut`: cabeçalho, coluna sugerida para cada campo e prévia (etapa de mapeamento; nada é gravado). **413**; **422** formato, arquivo ilegível ou sem linha de cabeçalho |
| POST | `/planos` | `pda.gerenciar_planos` | multipart: `nome`, `arquivo`, `vigencia_inicio`/`vigencia_fim` (aaaa-mm-dd, opcionais), `definir_vigente` (padrão false), `mapeamento` (JSON `MapeamentoIn`, opcional; sem ele as colunas são achadas pelo cabeçalho) → 201 `ImportacaoResumoOut` (PBI-12). **409** nome repetido (sem diferenciar maiúsculas); **413** arquivo > 5 MB; **422** nome vazio ou com mais de 200 caracteres, extensão diferente de .xlsx/.csv, .xlsx/.csv ilegível, .xlsx grande demais descompactado (> 50 MB), mais de 20 abas ou de 20.000 linhas, cabeçalho obrigatório ausente, prazo ilegível, planilha sem base, data inválida ou fim < início; com mapeamento: JSON inválido, obrigatório sem coluna, coluna repetida ou inexistente no arquivo |
| POST | `/planos/manual` | `pda.gerenciar_planos` | JSON `PlanoIn` (`nome`, `vigencia_inicio`, `vigencia_fim`, `definir_vigente`) → 201 `PlanoOut` de um PDA **vazio**, sem planilha (`arquivo_nome` nulo; `importado_por` = quem criou). **409** nome repetido; **422** nome vazio/longo ou fim < início |
| GET | `/planos/{id}` | `pda.acessar` | `PlanoOut` (totais no escopo de órgão); **404** |
| PUT | `/planos/{id}` | `pda.gerenciar_planos` | JSON `PlanoIn` → `PlanoOut`: edita nome e vigência (não troca o vigente; `definir_vigente` é ignorado). **409** nome de outro PDA; **422**; **404** |
| PUT | `/planos/{id}/vigente` | `pda.gerenciar_planos` | Define o PDA vigente → `PlanoOut`; **404** |
| DELETE | `/planos/{id}` | `pda.gerenciar_planos` | Exclui o PDA e suas bases → 204; **409** se for o vigente e houver outros PDAs; **404** |
| POST | `/planos/{id}/bases` | `pda.gerenciar_planos` | JSON `BaseIn` → 201 `BaseOut`: inclui uma base prevista. **422** sigla ou nome vazios, endereço do dataset não reconhecido, ID do dataset inexistente ou diferente do achado pelo endereço, organização inexistente ou diferente da do dataset; **403** órgão de outro escopo; **404** plano |
| PUT | `/bases/{id}` | `pda.gerenciar_planos` | JSON `BaseIn` → `BaseOut`: edita a base (inclusive o endereço do dataset). Mesmos erros; **404** |
| DELETE | `/bases/{id}` | `pda.gerenciar_planos` | Remove a base do PDA → 204 (atualiza `total_bases`); **403**; **404** |
| GET | `/datasets/{dataset_id}/bases` | `pda.acessar` | `BaseOut[]`: bases previstas vinculadas **pelo ID** a um dataset do portal, em todos os PDAs (vigente primeiro). Sem vínculo → `[]` (nunca casa pelo nome). Usado pelo detalhe da tela Datasets |
| GET | `/formulario` | `pda.gerenciar_planos` | `FormularioOut`: organizações do portal visíveis ao usuário (`{valor: ckan_id, rotulo}`) e o domínio de periodicidade |
| POST | `/planos/{id}/vincular` | `pda.editar_vinculos` | Tenta de novo os vínculos pendentes → `VinculosOut` (PBI-12/13); **404** |
| POST | `/planos/{id}/ids-ckan` | `pda.editar_vinculos` | multipart: `arquivo` (CSV SIGLA, NOME_PDA, NOME_DATASET, ID_DATASET), `aplicar` (padrão false = só analisa), `sobrescrever` (padrão false) → `IdsCkanOut`. **404** plano; **413**; **422** formato, sem cabeçalho ou sem linhas |
| GET | `/bases` | `pda.acessar` | `?plano_id=&orgao=&situacao=&periodicidade=&ano=&prazo=` → `BasesOut` (PBI-19 a 21). Sem `plano_id` usa o vigente; sem PDA → `plano=null` e listas vazias. **404** plano inexistente; **422** `ano` não numérico ou `prazo` diferente de `vencido`/`proximo` |
| GET | `/bases/{id}` | `pda.acessar` | `BaseOut`; **404** se não existe ou é de outro órgão para usuário restrito |

Conflito de gravação em paralelo (nome ou vigente) também devolve 409. Contrato JSON em
`schemas.py`, espelhado em `frontend/src/modules/pda/api.ts`; datas `aaaa-mm-dd`, datetimes ISO 8601 (UTC):
- `PlanoOut`: id, nome, vigencia_inicio, vigencia_fim, vigente, arquivo_nome, importado_por (nome
  do usuário), importado_em, total_bases, vinculos_resolvidos, vinculos_pendentes.
- `ImportacaoResumoOut`: plano, bases_importadas, linhas_ignoradas `[{linha, motivo}]`,
  vinculos_resolvidos, vinculos_pendentes, sem_vinculo, orgaos_sem_correspondencia,
  tem_coluna_prazo, tem_coluna_portal (sem "Disponível no Portal" nenhuma base é vinculada),
  colunas_opcionais_ausentes (rótulos).
- `VinculosOut`: vinculos_resolvidos (nesta execução), vinculos_pendentes (que continuam pendentes).
- `ColunasPlanilhaOut`: aba e linha do cabeçalho (0-based), colunas (títulos), campos
  `[{campo, rotulo, obrigatorio, sugestao}]` (sugestao = índice da coluna ou null), previa (até 5
  linhas). `MapeamentoIn`: aba, linha, colunas `{campo: índice}`.
- `IdsCkanOut`: aplicado, total_linhas, atualizadas (0 na análise), atualizar, substituir (com
  id_atual), iguais, sem_id, sem_base, invalidas — listas de `LinhaIdCkanOut` {linha, sigla,
  nome_pda, dataset_id, base_id, base_nome, id_atual, motivo}.
- `PlanoIn`: nome, vigencia_inicio, vigencia_fim, definir_vigente (só na criação).
- `BaseIn`: orgao_sigla*, organizacao_id (vazio = pela sigla), nome_previsto*, descricao,
  unidade_responsavel, periodicidade (valor do domínio ou texto livre, normalizado),
  prazo_abertura, politicas_publicas, possui_conteudo_sigiloso, dataset_link (link do portal ou name),
  dataset_id (ID do dataset no CKAN; tem prioridade sobre o link, precisa existir no inventário e,
  se o link achar outro dataset, dá 422).
- `FormularioOut`: organizacoes `[{valor, rotulo}]`, periodicidades.
- `BaseOut`: dados da planilha + `orgao_chave` (organizacao_id ou `sigla:<SIGLA>`), orgao_nome,
  `vinculo` (resolvido/pendente/sem_vinculo), dataset_id, dataset_name e dataset_titulo **atuais**
  do inventário, dataset_name_planilha, dataset_ativo, data_publicacao, recursos_validos,
  formatos, ultima_atualizacao,
  ultima_atualizacao_estimada, situacao, `flag_prazo` (vencido/proximo/""), classificacao.
- `BasesOut`: plano, hoje, janela_alerta_dias, total_previstas (visíveis ao usuário, sem filtros),
  opcoes `{orgaos: [{valor, rotulo}], periodicidades, anos}`, bases (por órgão e nome).

## Serviços e métodos
`regras.py` (funções puras, reaproveitáveis numa extensão CKAN — ADR 0004):
- `ler_cabecalho(conteudo, nome_arquivo) -> CabecalhoLido` — etapa de mapeamento: linha de
  cabeçalho mais provável (mais colunas reconhecidas nas 30 primeiras linhas de cada aba),
  `sugerir_colunas(cabecalho, sinonimos)` (nome igual → muito parecido, `SequenceMatcher` ≥ 0,85 →
  começa/termina com o esperado; cada coluna para um campo só; "sigla" antes de "orgao") e prévia.
  `validar_mapeamento(colunas, CAMPOS_PDA)`: campos conhecidos, obrigatórios e coluna única.
- `ler_ids_ckan(conteudo, nome_arquivo) -> list[LinhaIdCkan]` — CSV/.xlsx de IDs (UTF-8 ou
  Latin-1/Windows-1252, ";" ou ","); "Não encontrado" ou vazio = sem ID. `normalizar_uuid(valor)` e
  `chave_base(sigla, nome)` (comparação sem maiúsculas, acentos e espaços extras).
- `ler_planilha(conteudo: bytes, nome_arquivo: str, mapeamento: Mapeamento | None = None) -> PlanilhaLida` — PBI-12; `linhas:
  list[LinhaPda]`, `ignoradas: list[(linha, motivo)]`, `tem_coluna_prazo`, `tem_coluna_portal`,
  `colunas_opcionais_ausentes`. Leitura sob demanda e limitada (`TAMANHO_DESCOMPACTADO_MAXIMO` 50 MB,
  `ABAS_MAXIMO` 20, `LINHAS_MAXIMO` 20.000, `COLUNAS_MAXIMO` 60, fim da aba após 1.000 linhas vazias
  seguidas). Lança `PlanilhaInvalida`.
- `normalizar_periodicidade(texto) -> str` — valor do domínio `DOMINIO_PERIODICIDADE`;
  `periodicidade_informada(texto)` — no cadastro manual, valor do domínio fica como está
  ("Múltipla", "Sem informação"), texto livre é normalizado.
- `extrair_name_da_url(valor) -> str | None` — name de `.../dataset/<name>`, só para achar o ID (PBI-13);
  `name_do_link(valor)` — idem, aceitando também só o name (cadastro manual).
- `casar_orgao(sigla, orgaos: Iterable[(ckan_id, name, titulo, sigla)]) -> str | None`; de-para
  explícito em `SIGLAS_CONHECIDAS` (sigla compacta → name da organização).
- `interpretar_data(valor) -> date | None` e `fim_do_mes(ano, mes)` — prazo da planilha, inclusive
  mês/ano ("Março/2025" → 31/03/2025).
- `orgao_por_evidencia(pares: Iterable[(sigla, organizacao_id)]) -> {chave_sigla: organizacao_id}`
  e `chave_sigla(sigla)` — órgão herdado das bases da mesma sigla vinculadas por ID.
- `situacao_base(*, vinculada, dataset_ativo, recursos_validos, prazo, hoje, janela_dias) -> str` — PBI-15/19.
- `flag_prazo(prazo, hoje, janela_dias) -> "vencido" | "proximo" | ""` — PBI-20/22.
- Auxiliares: `interpretar_data`, `interpretar_sim_nao`, `extensao_valida`, `normalizar_texto`;
  constantes `TAMANHO_MAXIMO` (5 MB) e `SITUACOES`.

`service.py` (lança `NaoEncontrado` 404, `Conflito` 409 e `Invalido` 422; o router só converte em HTTP):
- `importar_plano(db, *, nome, vigencia_inicio, vigencia_fim, definir_vigente, arquivo_nome,
  conteudo, importado_por) -> ImportacaoResumoOut` — PBI-12/13, atômico.
- `resolver_vinculos_pendentes(db, plano_id) -> {"vinculos_resolvidos", "vinculos_pendentes"}` — PBI-12/13.
- `colunas_planilha(conteudo, arquivo_nome) -> ColunasPlanilhaOut` — etapa de mapeamento;
  `importar_plano(..., mapeamento=None)` usa as colunas escolhidas. O servidor não guarda o arquivo
  entre as etapas: o frontend o envia de novo na confirmação.
- `importar_ids_ckan(db, plano_id, conteudo, arquivo_nome, user, *, aplicar, sobrescrever) -> IdsCkanOut`
  — grava `dataset_id` (o vínculo, ADR-0006) nas bases casadas por SIGLA + nome (uma base só; mais
  de uma = ambígua, não aplica). ID precisa ser UUID e existir no inventário; base com outro ID só
  muda com `sobrescrever`; mesma base com IDs diferentes no arquivo não é aplicada; o órgão do
  dataset vinculado prevalece e depois roda `_completar_orgao_por_evidencia`. Usuário restrito a
  órgão só vê as próprias bases e só vincula datasets do próprio órgão.
- `listar_planos(db, user=None) -> list[PlanoOut]` · `obter_plano(db, plano_id, user=None)` ·
  `definir_vigente(db, plano_id) -> PlanoOut` · `excluir_plano(db, plano_id) -> None`.
- CRUD manual: `criar_plano(db, PlanoIn, criado_por) -> PlanoOut` (PDA vazio) ·
  `atualizar_plano(db, plano_id, PlanoIn) -> PlanoOut` · `criar_base(db, plano_id, BaseIn, user)` ·
  `atualizar_base(db, base_id, BaseIn, user)` (ambas `-> BaseCalculada`) ·
  `excluir_base(db, base_id, user)` · `opcoes_formulario(db, user) -> FormularioOut`. A validação do
  nome e da vigência (`_validar_plano`) é a mesma da importação.
- `listar_bases(db, user, *, plano_id, orgao, situacao, periodicidade, ano, prazo) -> BasesOut` — PBI-20/21.
- `obter_base(db, base_id, user) -> BaseCalculada` · `bases_do_dataset(db, dataset_id, user=None)
  -> list[BaseCalculada]` (vigente primeiro; tela Datasets).
- **Para outros módulos:** `plano_vigente(db) -> PlanoPda | None` e
  `bases_do_plano(db, plano_id, user=None, *, hoje=None, janela_dias=None) -> list[BaseCalculada]`
  — PBI-19; `BaseCalculada` é uma dataclass congelada com os campos de `BaseOut`; `user=None` =
  sem escopo de órgão (uso consolidado). 404 se o plano não existe.
- `hoje_local() -> date` (America/Sao_Paulo) · `janela_alerta_dias(db) -> int` (PBI-22) ·
  `calcular_base(base, plano_nome, hoje, janela_dias)` · `orgao_chave(organizacao_id, orgao_sigla)`.

Datasets, recursos e organizações são carregados com `selectinload`: 7 consultas para ~450 bases,
sem N+1. Testes: `tests/test_pda_regras.py`, `tests/test_pda_api.py`,
`tests/test_pda_revisao.py` (regressões da revisão de 08/10/2026), `tests/test_pda_formato_2025.py`
e `tests/test_pda_crud.py` (cadastro manual).

## Modelo de dados
Diagrama e dicionário de dados completos: [MER](../banco/mer.md) · regras: [convenções do banco](../banco/convencoes.md).

| Tabela | Colunas relevantes |
|---|---|
| `pda_plano` | id, **nome** (200, único; também único sem diferenciar maiúsculas pelo índice `uq_pda_plano_nome_ci` em `lower(nome)`), vigencia_inicio, vigencia_fim, **vigente**, arquivo_nome (300), importado_por (200), importado_em (tz), total_bases, created_at, updated_at. Índice único parcial `uq_pda_plano_vigente` (`vigente` WHERE `vigente`): no máximo um vigente |
| `pda_base_prevista` | id, **plano_id** → `pda_plano.id` (ON DELETE CASCADE, NOT NULL, indexado), orgao_sigla (100, como na planilha), organizacao_id → `organizacao.ckan_id` (indexado), nome_previsto (500), descricao (text), unidade_responsavel (500), prazo_abertura, periodicidade (40, normalizada, NOT NULL, padrão "Sem informação"), periodicidade_original (100), politicas_publicas (500), possui_conteudo_sigiloso, **dataset_id** → `dataset.ckan_id` (indexado), dataset_name_planilha (200: name extraído da URL da planilha; usado só para encontrar o ID — vínculo pendente / Atualizar vínculos — e para auditoria; nunca para recalcular vínculo resolvido), linha_planilha, classificacao (pda/espontanea, padrão "pda"), created_at, updated_at |

Migração `b7e2c41d9a63` (sobre `9da707016405`): cria `pda_plano` e acrescenta as colunas; apaga
linhas órfãs de `pda_base_prevista` antes do NOT NULL (a tabela estava vazia em todos os
ambientes); o downgrade apaga as bases previstas. `PlanoPda.bases` usa `cascade="all,
delete-orphan", passive_deletes=True`, e `excluir_plano` apaga as bases explicitamente porque o
SQLite só aplica ON DELETE CASCADE com `PRAGMA foreign_keys`. Migração `c3f8a2d15e70` (sobre
`b7e2c41d9a63`): índice único `uq_pda_plano_nome_ci` em `lower(nome)`; não altera dados.

## Permissões
| Permissão | Papéis padrão |
|---|---|
| `pda.acessar` | Administrador, Gerência GEDA, Equipe GEDA |
| `pda.editar_vinculos` | Administrador, Gerência GEDA — Atualizar vínculos (e a futura reclassificação PDA × espontânea) |
| `pda.gerenciar_planos` | Administrador, Gerência GEDA — importar ou criar PDA, editar e excluir PDA, incluir/editar/remover bases previstas e definir o vigente |

Em banco já existente, a Gerência GEDA não recebe `pda.gerenciar_planos` sozinha (ver Pendências).

## Interações com outros módulos
| Direção | Módulo | O quê |
|---|---|---|
| consome | inventario | `Dataset` (ID, name, título, órgão, `ativo_no_portal`, `metadata_created`), `Recurso` (`eh_dicionario_dados`, `formato`, `last_modified`, `created`) via `service.recursos_atuais(ds)` (só recursos ainda no pacote do dataset), `Organizacao` (casamento da sigla) |
| consome | parametros | `obter(db, "janela_alerta_prazo_dias")` (PBI-22) |
| consome | atualizacoes | `service.ultima_atualizacao_real(recursos)` → `UltimaAtualizacao(data, estimada)` (implementada em `atualizacoes/regras.py`) |
| consome | acesso | `filtrar_por_orgao(stmt, BasePrevista.organizacao_id, user)` nas consultas de bases |
| é consumido por | painel | `plano_vigente(db)` + `bases_do_plano(db, plano.id, user)` — bases previstas, vinculadas, publicadas e metas por órgão na tela Organizações (US19); sempre o PDA vigente |
| é consumido por | relatorios | idem — relatório de bases não publicadas e prazos; sempre o PDA vigente |
| é consumido por | assistente | idem, só agregados e com `user` para respeitar o escopo de órgão |
| é consumido por | atualizacoes | `classificacao` para o indicador PDA × espontânea (PBI-82, previsto) |
| é consumido por | inventario (tela Datasets) | `GET /datasets/{id}/bases` — prazo, periodicidade e situação PDA no detalhe do dataset |

## Jobs agendados
Nenhum. A situação é calculada na consulta, sobre o inventário da última coleta. Vínculos
pendentes só são refeitos pelo botão Atualizar vínculos (não automaticamente após a coleta).

## Regras de negócio e decisões
Decisões registradas: [ADR-0006](../adr/0006-regras-de-afericao-do-inventario.md).

- **Vários PDAs, um vigente** (decisão de 07/10/2026, Humberto/Eixo 1 — pendente de validação da
  GEDA). Nome obrigatório e único (espaços colapsados, sem diferenciar maiúsculas). O primeiro PDA
  cadastrado vira vigente mesmo sem `definir_vigente`. Garantia dupla: índice único parcial e
  transação (desmarca todos, marca o escolhido, flush). O vigente só pode ser excluído quando é o
  único PDA cadastrado (havendo outros, defina outro como vigente antes; 13/10/2026). Outros
  PDAs podem ser consultados na tela, mas indicadores e relatórios usam sempre o vigente.
- **Vínculo sempre pelo ID do dataset** (PBI-13). "Disponível no Portal" → `extrair_name_da_url`
  → `Dataset.name` do inventário → grava `Dataset.ckan_id`. Name com dataset = resolvido; name sem
  dataset = pendente; "Não"/vazio = sem vínculo. Dois datasets com o mesmo name: vale o ativo no
  portal; persistindo a ambiguidade, fica pendente. O name da planilha fica em
  `dataset_name_planilha` (usado só para achar o ID e para auditoria); **vínculo resolvido nunca
  é recalculado pelo nome**.
- **Órgão da base**, em ordem: a) base vinculada herda o órgão do dataset; b) sem vínculo, a
  organização das bases da MESMA sigla vinculadas por ID neste PDA, se todas apontarem para uma só
  (evidência do próprio vínculo, não chute; evita a mesma sigla partida em duas opções do filtro,
  como SEAD × "administracao"); c) `casar_orgao` (sem acento, minúsculo): 0) de-para explícito
  `SIGLAS_CONHECIDAS` para as siglas que nenhum critério deduz (SEAD, SEDF, SECOM, SECULT, SIC, CASA
  MLITAR, AGEHAB, AGR, SANEAGO, DETRAN, CBM, PGE, BrC-PREVCOM → name da organização; se o name mudar
  no portal, a entrada deixa de casar e segue a heurística); 1) `Organizacao.sigla`;
  2) sigla compacta igual ao name sem hífens ou ao título compactado (goiasfomento, goiastelecom);
  3) sigla de uma palavra como token do name ou do título (abc, dgpp, fapeg, juceg) e sigla de
  várias palavras como sequência contígua desses tokens (CASA CIVIL, GOIÁS PARCERIAS); 4) iniciais
  das palavras significativas do título (CGE → Controladoria Geral Estado). `Atualizar vínculos`
  também completa o órgão das bases sem organização pela regra b. O primeiro critério com resultado decide; empate ou nenhum → sem
  organização (**nunca chuta**), a sigla entra em `orgaos_sem_correspondencia` e o filtro usa
  `sigla:<SIGLA>`. Usuário restrito a órgão não vê bases sem organização.
- **Situação** quanto ao prazo de abertura (PBI-19; ressalva CGE-GO 17/09):

  | Situação | Condição | Badge |
  |---|---|---|
  | Publicado | vinculada, dataset ativo e ≥ 1 recurso válido | verde |
  | Sem recurso | vinculada, dataset ativo e 0 recurso válido (não conta como cumprida) | âmbar |
  | Em atraso | vinculada, dataset inativo no portal e prazo < hoje (atraso confirmado) | vermelho |
  | Prazo vencido | sem vínculo (ou vínculo pendente) e prazo < hoje: não há como saber se a base já foi publicada; dica "aguardando vínculo" | cinza |
  | Próximo do prazo | não publicada e hoje ≤ prazo ≤ hoje + janela | âmbar |
  | Em dia | não publicada e prazo > hoje + janela | verde |
  | Não publicado | não publicada e sem prazo | cinza |

  Não publicada = sem vínculo, vínculo pendente ou dataset inativo. `hoje` = data em
  America/Sao_Paulo; janela = `janela_alerta_prazo_dias` (PBI-22). `flag_prazo` olha só o prazo,
  como `pdaSituacaoDeadlineFlag`.
- **Recursos válidos** = recursos ainda presentes no pacote do dataset (`recursos_atuais`: recurso
  apagado do CKAN fica no banco, mas não conta) e que não são dicionário de dados
  (`eh_dicionario_dados`).
- **Dataset inativo** (`ativo_no_portal = false`: excluído ou privado, PBI-15): a base volta a não
  publicada e `dataset_ativo=false` a destaca na lista ("fora do portal") e no detalhe.
- **Última atualização** = `ultima_atualizacao_real` do módulo `atualizacoes` (maior `last_modified`
  dos recursos válidos; sem ele, maior `created` com `estimada=true`). Nunca `metadata_modified`.
- **Periodicidade** normalizada para Diária, Semanal, Quinzenal, Mensal, Bimestral, Trimestral,
  Quadrimestral, Semestral, Anual, Bienal, Quadrienal, Quinquenal, Eventual, Estática, Múltipla ou
  Sem informação. Erros de digitação só por lista explícita (Mnsal, Semstral); Sob Demanda e
  Quando houver → Eventual; "Não há mais atualização" → Estática; pontuação nas bordas é ignorada
  (".Semestral", "Mensal-"); com "/": duas ou mais periodicidades reconhecidas distintas →
  Múltipla, uma só → ela ("Mensal/N/A" → Mensal), alguma parte desconhecida → Sem informação;
  N/A, vazio ou desconhecido → Sem informação. O texto original é sempre guardado.
- **Importação** (PBI-12): .xlsx (openpyxl `read_only`/`data_only`, primeira aba com o cabeçalho)
  ou .csv (UTF-8 com ou sem BOM → Windows-1252 → Latin-1; separador ";" ou ","), até 5 MB. Colunas
  localizadas pelo cabeçalho normalizado (nas 30 primeiras linhas); obrigatórias "Órgão" e "Base
  de Dados"; aceita "Periodicidade" no lugar de "Atualização" e "Meta/Prazo para abertura" (formato
  da planilha do PDA 2025-2027 exportada pela GEDA), "Prazo para abertura", "Prazo de abertura" ou
  "Prazo" para o prazo. Linhas vazias e rodapés ("Total", "Nenhum filtro aplicado", "Filtros
  aplicados:Ano é 2025" — só na coluna Órgão) são pulados; cabeçalho repetido no meio da planilha e linha sem Órgão ou Base de Dados vão para
  `linhas_ignoradas` (número 1-based e motivo). Tetos contra planilha malformada ou "bomba" de
  compressão: ver `ler_planilha`.
- **Prazo** só da coluna opcional "Meta/Prazo para abertura" (ou sinônimos acima): **mês/ano**
  ("Março/2025", "Dezembro2025", "Setembro 2025", "mar/2025", "03/2025") = meta até o **último dia
  do mês** (decisão de 08/10/2026, pendente de validação da GEDA); data completa (date do xlsx,
  dd/mm/aaaa ou aaaa-mm-dd, com hora opcional ignorada, ou serial do Excel 2000–2099) vale o dia.
  No .xlsx, célula de data com formato só de mês e ano ("Março/2025" digitado no Excel em pt-BR vira
  01/03/2025 formatado `mmmm/aaaa`) também é lida como fim do mês. Sem a coluna → nulo; **nunca**
  derivado da vigência; valor presente e ilegível → 422 na importação inteira.
- **Sem "Disponível no Portal"** (caso da planilha 2025-2027) nenhuma base é vinculada na
  importação: todas ficam `sem_vinculo` e a situação vem só do prazo (com metas de 2025, "Em
  atraso"). O resumo avisa (`tem_coluna_portal=false`). Vínculo por nome do dataset não é feito
  (ADR-0006).
- Importação **atômica** (qualquer erro → rollback). O arquivo bruto não é gravado: só os dados
  extraídos e o nome do arquivo. Textos longos são cortados no tamanho da coluna.
- **Cadastro manual** (13/10/2026): um PDA pode ser criado vazio, sem planilha, e receber as bases
  uma a uma; qualquer PDA (importado ou manual) pode ter nome e vigência editados e bases
  incluídas, editadas ou removidas. `total_bases` é recalculado a cada inclusão/remoção. Base
  incluída à mão tem `linha_planilha` nula. As mesmas regras da importação valem para o formulário:
  - **órgão**: o do dataset vinculado; senão a organização escolhida no formulário; senão evidência
    do vínculo por ID e `casar_orgao`. Organização escolhida diferente da do dataset → 422;
  - **vínculo**: "Disponível no portal" (link ou name) → `name_do_link` → ID do dataset no
    inventário (resolvido) ou pendente; vazio → sem vínculo. Na edição, endereço igual ao atual
    mantém o vínculo resolvido (**nunca recalculado pelo nome**); endereço novo é resolvido de novo;
  - **periodicidade**: valor do domínio fica como está; na edição, manter a mesma periodicidade
    preserva o texto original da planilha (ex.: "Mnsal").
  Usuário restrito a órgão só altera bases do próprio órgão (`exigir_mesmo_orgao`), embora os papéis
  padrão de órgão não tenham `pda.gerenciar_planos`.
- Bases espontâneas também devem ser monitoradas (Paloma e Júnior, 17/09) — ainda não
  implementado: `classificacao` é sempre "pda".

## Pendências
- **Vínculo das bases da planilha 2025-2027**: o formato novo não tem "Disponível no Portal", então
  a importação não vincula nenhuma base. Agora o vínculo pode ser informado base a base em "Editar"
  (endereço do dataset → ID); para as ~450 bases, ainda vale pedir à GEDA a coluna ou uma planilha
  de vinculação por ID (ADR-0006) para vincular em lote.
- Validar com a GEDA que a meta em mês/ano vale até o último dia do mês.
- Validar com a GEDA a regra de vários PDAs com um vigente (decisão de 07/10/2026).
- "Bianual" mapeado para Bienal, mas é ambíguo (pode significar semestral) — validar com a GEDA.
- De-para de órgãos (`SIGLAS_CONHECIDAS`) fixo no código: validar as 13 entradas com a GEDA e, se
  surgirem siglas novas com frequência, levar o de-para para `parametros` (editável pela GEDA).
- Banco já existente: `sincronizar_papeis_padrao` não sobrescreve ajustes, então o papel Gerência
  GEDA **não** recebe `pda.gerenciar_planos` automaticamente — conceder pela tela Usuários e papéis
  (o Administrador recebe por `todas`).
- Fora deste escopo: critério das bases espontâneas e reclassificação PDA × espontânea (PBI-16 a
  PBI-18, PBI-82); escolha do dataset numa lista com busca (hoje o vínculo manual é pelo endereço
  digitado).
- Edição e remoção de bases não têm histórico de quem alterou o quê (entra com a `rastreabilidade`).
- Relatórios e exportação das bases do PDA (US20): consumir `bases_do_plano` no módulo `relatorios`.
- A última atualização usa `created` só quando nenhum recurso válido tem `last_modified`; o PBI-25
  pode pedir o fallback por recurso — validar.
- O órgão de uma base já vinculada não acompanha mudança de órgão do dataset após a importação.
- US7 (PBI-16 a PBI-18, PBI-82) e os PBI-14 e PBI-80 do Backlog v2 não foram atendidos nesta
  entrega: conferir no backlog o escopo de cada um (o vínculo manual base a base pelo endereço, de
  13/10/2026, é candidato a atender o PBI-14).
- Detalhe da base sem "Situação de atualização" (ressalva de 17/09: o PDA trata do prazo de
  abertura; a situação por periodicidade do `atualizacoes` ainda é esqueleto — validar com a GEDA
  se volta ao detalhe) e sem "Histórico recente" (entra quando a `rastreabilidade` existir).
- PDAs importados antes de 08/10/2026 (ex.: "PDA 2026 - 2027" no Docker) mantêm o órgão calculado
  na importação: SEAD continua partida e CASA CIVIL/GOIÁS PARCERIAS sem organização até reimportar
  o PDA (ou rodar Atualizar vínculos, que hoje só aparece com vínculo pendente).

## Histórico de alterações
| Data | Alteração | Autor |
|---|---|---|
| 30/09/2026 | Esqueleto: contratos, tabela `pda_base_prevista` e permissões | Victor |
| 07/10/2026 | Link para o MER e as convenções do banco | Victor |
| 07/10/2026 | Importação de planilhas, múltiplos PDAs com vigente, vínculo por ID, situação do prazo e tela de monitoramento (PBI-12, PBI-13, PBI-15, PBI-19 a PBI-22) | Humberto |
| 08/10/2026 | Revisão (27 achados confirmados): órgão por evidência do vínculo por ID e siglas de várias palavras; recursos apagados do CKAN deixam de contar; contagens de `PlanoOut`/`GET /planos` com escopo de órgão; nome único sem diferenciar maiúsculas no banco (migração `c3f8a2d15e70`) e conflitos concorrentes → 409; tetos na leitura de .xlsx; cabeçalho repetido, rodapé só na coluna Órgão, prazo com hora e pontuação na periodicidade; resumo avisa coluna Prazo ausente; detalhe com data de publicação e formatos; foco de teclado nos modais; descrição de `pda.editar_vinculos` ajustada no catálogo; status passa a Parcial | Humberto |
| 08/10/2026 | Formato da planilha do PDA 2025-2027: coluna "Meta/Prazo para abertura" com mês/ano (meta até o fim do mês, inclusive célula de data `mmmm/aaaa` no .xlsx), rodapé "Filtros aplicados", aviso `tem_coluna_portal` quando falta "Disponível no Portal" e de-para explícito de 13 siglas de órgão (`SIGLAS_CONHECIDAS`) | Humberto |
| 13/10/2026 | CRUD manual: criar PDA vazio (sem planilha), editar nome e vigência, excluir (o vigente quando é o único PDA) e incluir/editar/remover bases previstas, com vínculo pelo endereço do dataset (→ ID) e órgão escolhido ou pela sigla; rotas `POST /planos/manual`, `GET`/`PUT /planos/{id}`, `POST /planos/{id}/bases`, `PUT`/`DELETE /bases/{id}`, `GET /formulario`; modais `PlanoFormModal` e `BaseFormModal` | Humberto |
| 18/10/2026 | `GET /datasets/{dataset_id}/bases` e `bases_do_dataset`: bases vinculadas pelo ID a um dataset, para o detalhe da tela Datasets | Humberto |
| 18/10/2026 | Tela aceita `?orgao=<chave>` na URL (botão "Ver bases no PDA" da tela Organizações); Interações com o painel atualizadas | Humberto |
| 18/10/2026 | Situação "Prazo vencido" (`regras.PRAZO_VENCIDO`): base sem vínculo com prazo vencido deixa de aparecer como "Em atraso", que passa a exigir vínculo (dataset conferido e fora do portal); badge cinza com a dica "aguardando vínculo" e opção no filtro | Humberto |
| 21/10/2026 | Correções no cadastro manual: o modal de edição abria por trás do detalhe da base (modal compartilhado agora em portal, com pilha para Esc/Tab); novo campo "ID do dataset no CKAN" (`BaseIn.dataset_id`, `_vinculo_por_id`) para vincular quando o nome do PDA difere do name no portal | Humberto |
| 22/10/2026 | Importação do PDA com etapa de **mapeamento de colunas** (`POST /planilha/colunas`, `MapeamentoIn` em `POST /planos`, `regras.ler_cabecalho`/`sugerir_colunas`/`validar_mapeamento`, `MapeamentoColunas.tsx`) e **Importar IDs do CKAN** em lote por SIGLA + NOME_PDA com análise, confirmação para sobrescrever e resumo (`POST /planos/{id}/ids-ckan`, `regras.ler_ids_ckan`, `service.importar_ids_ckan`, `ImportarIdsModal.tsx`) | Humberto |
