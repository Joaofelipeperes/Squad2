# Módulo `pda` — Monitoramento do Plano de Dados Abertos

| | |
|---|---|
| **Status** | Parcial — US6 e US8 implementadas (importação, múltiplos PDAs, vigente, vínculo por ID, situação do prazo, tela); US7 (PDA × espontânea) pendente |
| **Responsável** | Humberto (Eixo 1) |
| **User stories** | US6 (PBI-12 a PBI-15), US7 (PBI-16 a PBI-18, PBI-82), US8 (PBI-19 a PBI-22, PBI-80) |
| **Backend** | `backend/app/modules/pda/` · migrações `b7e2c41d9a63_pda_planos_e_bases_previstas.py` e `c3f8a2d15e70_pda_nome_unico_sem_maiusculas.py` |
| **Frontend** | `frontend/src/modules/pda/` · upload multipart por `api.upload` em `frontend/src/shared/api/client.ts` |
| **Última atualização** | 23/10/2026 |

## Propósito
Importa a planilha do PDA (Plano de Dados Abertos), cruza cada base prevista com os datasets
publicados no CKAN (pelo ID) e mostra, por órgão, a situação do prazo de abertura. Vários PDAs
podem ficar cadastrados; o **vigente** rege a tela e os indicadores e relatórios de gestão.

## Telas
| Tela | Rota | Permissão para ver | Ações na tela (permissão) |
|---|---|---|---|
| Monitoramento do PDA | `/pda` | `pda.acessar` | Escolher o PDA exibido (padrão = vigente); filtros e "Limpar filtros"; detalhe da base (clique ou Enter na linha); **Importar PDA**, **Novo PDA** (criação manual), **Editar PDA**, **Incluir base** e, no detalhe, **Editar** e **Excluir base** (`pda.gerenciar_planos`); **Definir como vigente** só para PDA não vigente e **Excluir PDA** para não vigente ou vigente único, com confirmação em modal (`pda.gerenciar_planos`); **Atualizar vínculos (N pendentes)**, só se houver pendentes (`pda.editar_vinculos`) |

- **Painel "PDA"** (acima dos filtros): select com os PDAs ("Nome (vigente)"), badge Vigente /
  Não vigente e a linha "N bases previstas · importado (ou criado manualmente) em dd/mm/aaaa por
  Fulano · vigência … · arquivo". Trocar o PDA limpa os filtros e fecha o detalhe.
- **Modal Novo PDA / Editar PDA** (`PlanoFormModal.tsx`): nome*, início e fim da vigência; na
  criação, "Definir como vigente" (marcado e travado quando é o primeiro PDA). O PDA criado nasce
  vazio e já fica selecionado. Editar não troca o vigente.
- **Modal Incluir / Editar base** (`BaseFormModal.tsx`): órgão (sigla)*, organização no portal
  (select; vazio = identificar pela sigla), base de dados*, descrição, unidade responsável,
  periodicidade (domínio), meta/prazo para abertura (data), conteúdo sigiloso (Sim / Não / Não
  informado), políticas públicas e "Dataset no portal": busca (`DatasetBusca.tsx`, combobox) nos
  datasets do inventário por título, name, ID ou link; escolher um dataset grava o ID e ajusta a
  organização para a dele; vínculo pendente da planilha aparece como aviso e é mantido até ser
  descartado ou substituído. "Incluir
  base" fica acima da tabela; "Editar" e "Excluir base" (confirmação em modal), no rodapé do
  detalhe.
- **Filtros** (enviados ao backend): Órgão, Periodicidade e Ano (opções vindas de `opcoes` em
  `GET /bases`); Situação com os 6 rótulos fixos na ordem do protótipo (constante `SITUACOES` em
  `frontend/src/modules/pda/api.ts`, espelho de `regras.SITUACOES`); Prazo (Vencido / Próximos N
  dias, N = `janela_alerta_dias`).
- **Tabela**: Órgão | Base prevista (PDA) | Dataset CKAN | ID CKAN | Prazo | Periodicidade | Última
  atualização | Situação. Vínculo pendente mostra o name da planilha (ou o ID do CKAN abreviado) + badge "vínculo pendente";
  dataset inativo recebe badge "fora do portal"; ID abreviado (8 caracteres) com o completo no
  `title`; data estimada pela criação leva "(est.)". Contador "N base(s) encontrada(s) de M previstas".
- **Modal Importar PDA** (ADR-0020), em duas abas:
  - **Carregar**: nome*, início e fim da vigência, arquivo .xlsx/.csv* (até 5 MB), "Definir como
    vigente" (marcado e travado quando é o primeiro PDA);
  - **Configuração** (`ConfigImportacao.tsx`, modal largo): "Colunas da Tabela" — nome de cada
    coluna no arquivo (*Órgão (sigla), *Nome da base no PDA, ID do dataset no CKAN, Nome do órgão,
    Periodicidade, Prazo de abertura, Descrição, Unidade responsável, Políticas públicas, Possui
    conteúdo sigiloso, Link no portal), botão "?" com ajuda, "Restaurar padrão" e **Salvar Config.**;
    "Leitura" — início da leitura (linha do cabeçalho) e delimitador (só .csv). Padrão = tabela fato
    do PDA (`SIGLA;ORGAO;NOME_PDA;NOME_DA_BASE_CKAN;ID_UNICO;PERIODICIDADE;PREVISAO_DE_ABERTURA`,
    linha 1, ";"). "Salvar Config." guarda no `localStorage` do navegador (chave
    `pda.importacao.config`); a importação envia a configuração que está na tela, salva ou não.
  Após o envio mostra o resumo (bases importadas, linhas ignoradas com motivo, avisos — ex.: ID do
  CKAN não reconhecido —, vínculos resolvidos/pendentes, sem vínculo, órgãos sem correspondência),
  avisa quando falta a coluna "Prazo" ou quando não há nem coluna de ID do CKAN nem "Disponível no
  Portal" (e lista as demais colunas opcionais ausentes) e seleciona o PDA novo.
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
| POST | `/planos` | `pda.gerenciar_planos` | multipart: `nome`, `arquivo`, `vigencia_inicio`/`vigencia_fim` (aaaa-mm-dd, opcionais), `definir_vigente` (padrão false), `config` (opcional, JSON de `ConfigImportacaoIn`) → 201 `ImportacaoResumoOut` (PBI-12). **409** nome repetido (sem diferenciar maiúsculas); **413** arquivo > 5 MB; **422** nome vazio ou com mais de 200 caracteres, extensão diferente de .xlsx/.csv, .xlsx/.csv ilegível, .xlsx grande demais descompactado (> 50 MB), mais de 20 abas ou de 20.000 linhas, cabeçalho obrigatório ausente (na linha configurada, se houver), prazo ilegível, planilha sem base, data inválida, fim < início ou `config` inválida (JSON, campo desconhecido, linha < 1, delimitador fora de `;` `,` `\|` `\t`) |
| POST | `/planos/manual` | `pda.gerenciar_planos` | JSON `PlanoIn` (`nome`, `vigencia_inicio`, `vigencia_fim`, `definir_vigente`) → 201 `PlanoOut` de um PDA **vazio**, sem planilha (`arquivo_nome` nulo; `importado_por` = quem criou). **409** nome repetido; **422** nome vazio/longo ou fim < início |
| GET | `/planos/{id}` | `pda.acessar` | `PlanoOut` (totais no escopo de órgão); **404** |
| PUT | `/planos/{id}` | `pda.gerenciar_planos` | JSON `PlanoIn` → `PlanoOut`: edita nome e vigência (não troca o vigente; `definir_vigente` é ignorado). **409** nome de outro PDA; **422**; **404** |
| PUT | `/planos/{id}/vigente` | `pda.gerenciar_planos` | Define o PDA vigente → `PlanoOut`; **404** |
| DELETE | `/planos/{id}` | `pda.gerenciar_planos` | Exclui (exclusão lógica) o PDA e suas bases → 204; o nome fica livre para outro PDA; **409** se for o vigente e houver outros PDAs; **404** |
| POST | `/planos/{id}/bases` | `pda.gerenciar_planos` | JSON `BaseIn` → 201 `BaseOut`: inclui uma base prevista. **422** sigla ou nome vazios, endereço do dataset não reconhecido, organização inexistente ou diferente da do dataset; **403** órgão de outro escopo; **404** plano | Vínculo: `dataset_id` (busca) > `dataset_id_ckan` (ID do CKAN digitado: **422** se não existir no inventário ou divergir do dataset achado pelo endereço) > `dataset_link`.
| PUT | `/bases/{id}` | `pda.gerenciar_planos` | JSON `BaseIn` → `BaseOut`: edita a base (inclusive o endereço do dataset). Mesmos erros; **404** |
| DELETE | `/bases/{id}` | `pda.gerenciar_planos` | Remove (exclusão lógica) a base do PDA → 204 (atualiza `total_bases` com as bases ativas); **403**; **404** |
| GET | `/datasets/{dataset_id}/bases` | `pda.acessar` | `BaseOut[]`: bases previstas vinculadas **pelo ID** a um dataset do portal, em todos os PDAs (vigente primeiro). Sem vínculo → `[]` (nunca casa pelo nome). Usado pelo detalhe da tela Datasets |
| GET | `/formulario` | `pda.gerenciar_planos` | `FormularioOut`: organizações do portal visíveis ao usuário (`{valor: id, rotulo}`) e o domínio de periodicidade |
| GET | `/formulario/datasets` | `pda.gerenciar_planos` | `?busca=` → `DatasetOpcaoOut[]` (até 20, ativos no portal primeiro): datasets do inventário por título ou name (contém, sem diferenciar maiúsculas), ID exato ou link do portal (name exato), no escopo de órgão do usuário. Menos de 2 caracteres → `[]` |
| POST | `/planos/{id}/vincular` | `pda.editar_vinculos` | Tenta de novo os vínculos pendentes → `VinculosOut` (PBI-12/13); **404** |
| GET | `/bases` | `pda.acessar` | `?plano_id=&orgao=&situacao=&periodicidade=&ano=&prazo=` → `BasesOut` (PBI-19 a 21). Sem `plano_id` usa o vigente; sem PDA → `plano=null` e listas vazias. **404** plano inexistente; **422** `ano` não numérico ou `prazo` diferente de `vencido`/`proximo` |
| GET | `/bases/{id}` | `pda.acessar` | `BaseOut`; **404** se não existe ou é de outro órgão para usuário restrito |

Conflito de gravação em paralelo (nome ou vigente) também devolve 409. Contrato JSON em
`schemas.py`, espelhado em `frontend/src/modules/pda/api.ts`; datas `aaaa-mm-dd`, datetimes ISO 8601 (UTC):
- `PlanoOut`: id, nome, vigencia_inicio, vigencia_fim, vigente, arquivo_nome, importado_por (nome
  do usuário), importado_em, total_bases, vinculos_resolvidos, vinculos_pendentes.
- `ImportacaoResumoOut`: plano, bases_importadas, linhas_ignoradas `[{linha, motivo}]`,
  vinculos_resolvidos, vinculos_pendentes, sem_vinculo, orgaos_sem_correspondencia,
  tem_coluna_prazo, tem_coluna_portal, tem_coluna_id_ckan (sem esta e sem "Disponível no Portal"
  nenhuma base é vinculada), avisos `[{linha, motivo}]` (bases importadas com ressalva),
  colunas_opcionais_ausentes (rótulos).
- `ConfigImportacaoIn`: colunas `{campo: nome da coluna}` (campos orgao, base, orgao_nome, id_ckan,
  descricao, unidade, periodicidade, prazo, politicas, sigiloso, portal; vazio = nomes usuais),
  linha_cabecalho (linha dos nomes das colunas; nulo = procurar nas 30 primeiras), delimitador
  (vazio = detectar).
- `VinculosOut`: vinculos_resolvidos (nesta execução), vinculos_pendentes (que continuam pendentes).
- `PlanoIn`: nome, vigencia_inicio, vigencia_fim, definir_vigente (só na criação).
- `BaseIn`: orgao_sigla*, organizacao_id (vazio = pela sigla), nome_previsto*, descricao,
  unidade_responsavel, periodicidade (valor do domínio ou texto livre, normalizado),
  prazo_abertura, politicas_publicas, possui_conteudo_sigiloso, dataset_id (`dataset.id` escolhido na
  busca; tem prioridade; inexistente → 422), dataset_id_ckan (ID do dataset no CKAN digitado — ADR-0006;
  precisa existir no inventário e, se o link achar outro dataset, dá 422), dataset_link (link do portal
  ou name; só acha o ID).
- `FormularioOut`: organizacoes `[{valor, rotulo}]`, periodicidades.
- `DatasetOpcaoOut`: id, id_ckan, name, titulo, organizacao_id, orgao_nome, ativo_no_portal.
- `BaseOut`: dados da planilha + `orgao_chave` (`id` da organização em texto ou `sigla:<SIGLA>`), orgao_nome,
  `vinculo` (resolvido/pendente/sem_vinculo), dataset_id (`dataset.id`), dataset_id_ckan (link do portal), dataset_name e dataset_titulo **atuais**
  do inventário, dataset_name_planilha, dataset_id_ckan_planilha (ID do CKAN informado; sem
  dataset = vínculo pendente pelo ID), dataset_ativo, data_publicacao, recursos_validos,
  formatos, ultima_atualizacao,
  ultima_atualizacao_estimada, situacao, `flag_prazo` (vencido/proximo/""), classificacao.
- `BasesOut`: plano, hoje, janela_alerta_dias, total_previstas (visíveis ao usuário, sem filtros),
  opcoes `{orgaos: [{valor, rotulo}], periodicidades, anos}`, bases (por órgão e nome).

## Serviços e métodos
`dao.py` — `PdaDao(Dao)` (ADR-0019): ÚNICO ponto de acesso ao banco do módulo (planos, bases e as
leituras de `Dataset`/`Organizacao` que o PDA usa). Consultas: `plano`, `plano_vigente`, `planos`,
`total_de_planos`, `nomes_de_planos`, `contagens`, `bases_do_plano`, `bases_do_dataset`,
`base_visivel`, `bases_pendentes`, `bases_sem_organizacao`, `siglas_vinculadas`, `dataset`,
`organizacao`, `organizacao_do_dataset`, `organizacoes`, `datasets_por_id_ckan`, `datasets_por_name`,
`buscar_datasets`;
gravações: `desmarcar_vigentes`, `atualizar_total`, `excluir_plano` (exclusão lógica do plano e
de todas as bases). As funções genéricas do `Dao` ignoram registros excluídos e gravam
`created_id`/`changed_id` com o usuário que agiu (`PdaDao.de(db, user)`).

`regras.py` (funções puras, reaproveitáveis numa extensão CKAN — ADR 0004):
- `ler_planilha(conteudo: bytes, nome_arquivo: str, config: ConfigLeitura = SEM_CONFIG) ->
  PlanilhaLida` — PBI-12; `linhas: list[LinhaPda]` (com `dataset_id_ckan` e `orgao_nome`),
  `ignoradas` e `avisos: list[(linha, motivo)]`, `tem_coluna_prazo`, `tem_coluna_portal`,
  `tem_coluna_id_ckan`, `colunas_opcionais_ausentes`. Leitura sob demanda e limitada
  (`TAMANHO_DESCOMPACTADO_MAXIMO` 50 MB, `ABAS_MAXIMO` 20, `LINHAS_MAXIMO` 20.000, `COLUNAS_MAXIMO`
  60, fim da aba após 1.000 linhas vazias seguidas). Lança `PlanilhaInvalida`.
- `config_leitura(colunas, linha_cabecalho, delimitador) -> ConfigLeitura` — valida a configuração
  do modal (campos de `CAMPOS`, linha 1–1.000, delimitador de `DELIMITADORES`).
- `id_ckan_da_celula(valor) -> (id | None, reconhecido)` — UUID → ID minúsculo; vazio ou "Não
  encontrado" → sem ID; outro texto → sem ID e aviso. `chave_cabecalho(valor)` — nome de coluna
  comparável (sem acento, minúsculo, "_" como espaço).
- `normalizar_periodicidade(texto) -> str` — valor do domínio `DOMINIO_PERIODICIDADE`;
  `periodicidade_informada(texto)` — no cadastro manual, valor do domínio fica como está
  ("Múltipla", "Sem informação"), texto livre é normalizado.
- `extrair_name_da_url(valor) -> str | None` — name de `.../dataset/<name>`, só para achar o ID (PBI-13);
  `name_do_link(valor)` — idem, aceitando também só o name (cadastro manual).
- `casar_orgao(sigla, orgaos: Iterable[(id, name, titulo, sigla)]) -> int | None`; de-para
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
  conteudo, importado_por, user=None, config=SEM_CONFIG) -> ImportacaoResumoOut` — PBI-12/13,
  atômico; vincula pelo ID do CKAN da planilha (`_datasets_por_id_ckan`) e, sem ID, pelo name.
- `resolver_vinculos_pendentes(db, plano_id, user=None) -> {"vinculos_resolvidos", "vinculos_pendentes"}`
  — PBI-12/13; pendente com ID é resolvido pelo ID, sem ID pelo name.
- `listar_planos(db, user=None) -> list[PlanoOut]` · `obter_plano(db, plano_id, user=None)` ·
  `definir_vigente(db, plano_id, user=None) -> PlanoOut` · `excluir_plano(db, plano_id, user=None) -> None`
  (exclusão lógica do plano e das bases). As gravações recebem o `user` que agiu (auditoria).
- CRUD manual: `criar_plano(db, PlanoIn, criado_por, user=None) -> PlanoOut` (PDA vazio) ·
  `atualizar_plano(db, plano_id, PlanoIn, user=None) -> PlanoOut` · `criar_base(db, plano_id, BaseIn, user)` ·
  `atualizar_base(db, base_id, BaseIn, user)` (ambas `-> BaseCalculada`) ·
  `excluir_base(db, base_id, user)` (exclusão lógica) · `opcoes_formulario(db, user) -> FormularioOut` ·
  `buscar_datasets(db, user, busca) -> list[DatasetOpcaoOut]`. A validação do
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
`tests/test_pda_revisao.py` (regressões da revisão de 08/10/2026), `tests/test_pda_formato_2025.py`,
`tests/test_pda_crud.py` (cadastro manual) e `tests/test_pda_id_ckan.py` (ID do CKAN na planilha e
configuração da leitura).

## Modelo de dados
Diagrama e dicionário de dados completos: [MER](../banco/mer.md) · regras: [convenções do banco](../banco/convencoes.md).

| Tabela | Colunas relevantes |
|---|---|
| `pda_plano` | id, **nome** (200, único entre os ativos — `uq_pda_plano_nome` — e também sem diferenciar maiúsculas — `uq_pda_plano_nome_ci` em `lower(nome)`; ambos `WHERE NOT deleted`), vigencia_inicio, vigencia_fim, **vigente**, arquivo_nome (300), importado_por (200), importado_em (tz), total_bases (bases ativas), deleted, created/created_id, changed/changed_id. Índice único parcial `uq_pda_plano_vigente` (`vigente` WHERE `vigente AND NOT deleted`): no máximo um vigente entre os ativos |
| `pda_base_prevista` | id, **plano_id** → `pda_plano.id` (NOT NULL, indexado; excluir o plano marca as bases como excluídas), orgao_sigla (100, como na planilha), organizacao_id → `organizacao.id` (indexado), nome_previsto (500), descricao (text), unidade_responsavel (500), prazo_abertura, periodicidade (40, normalizada, NOT NULL, padrão "Sem informação"), periodicidade_original (100), politicas_publicas (500), possui_conteudo_sigiloso, **dataset_id** → `dataset.id` (indexado; o dataset guarda o ID do CKAN em `id_ckan`), dataset_name_planilha (200: name extraído da URL da planilha; usado só para encontrar o ID — vínculo pendente / Atualizar vínculos — e para auditoria; nunca para recalcular vínculo resolvido), dataset_id_ckan_planilha (64: ID do dataset no CKAN informado na planilha — "ID_UNICO" — ou no formulário; com `dataset_id` nulo = vínculo pendente, resolvido pelo ID em Atualizar vínculos), linha_planilha, classificacao (pda/espontanea, padrão "pda"), created_at, updated_at |

Migração `b7e2c41d9a63` (sobre `9da707016405`): cria `pda_plano` e acrescenta as colunas; apaga
linhas órfãs de `pda_base_prevista` antes do NOT NULL (a tabela estava vazia em todos os
ambientes); o downgrade apaga as bases previstas. Desde a ADR-0019 nada é apagado fisicamente:
`PlanoPda.bases` não tem cascata e `PdaDao.excluir_plano` marca o plano e as bases como
excluídos (`deleted`), registrando quem e quando (`changed`/`changed_id`). Migração `c3f8a2d15e70` (sobre
`b7e2c41d9a63`): índice único `uq_pda_plano_nome_ci` em `lower(nome)`; não altera dados. Migração
`b9d4e6f2a7c1` (sobre `a8e2f5c1d9b4`): acrescenta `pda_base_prevista.dataset_id_ckan_planilha`
(opcional; bases já importadas ficam vazias).

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
Decisões registradas: [ADR-0006](../adr/0006-regras-de-afericao-do-inventario.md),
[ADR-0020](../adr/0020-importacao-do-pda-configuravel-com-id-do-ckan.md).

- **Vários PDAs, um vigente** (decisão de 07/10/2026, Humberto/Eixo 1 — pendente de validação da
  GEDA). Nome obrigatório e único (espaços colapsados, sem diferenciar maiúsculas). A unicidade vale
  só entre os PDAs não excluídos: o nome de um PDA excluído pode ser reaproveitado (ADR-0019). O primeiro PDA
  cadastrado vira vigente mesmo sem `definir_vigente`. Garantia dupla: índice único parcial e
  transação (desmarca todos, marca o escolhido, flush). O vigente só pode ser excluído quando é o
  único PDA cadastrado (havendo outros, defina outro como vigente antes; 13/10/2026). Outros
  PDAs podem ser consultados na tela, mas indicadores e relatórios usam sempre o vigente.
- **ID do CKAN na planilha** (23/10/2026, ADR-0020): a coluna do ID do dataset no CKAN
  ("ID_UNICO" na tabela fato do PDA) tem prioridade — ID → `Dataset.id_ckan` do inventário →
  grava o `Dataset.id` (resolvido); ID sem dataset no inventário → pendente, guardado em
  `dataset_id_ckan_planilha` e resolvido pelo ID em Atualizar vínculos; com ID informado o link
  do portal não é usado para vincular. Só UUID conta como ID; "Não encontrado", "-" ou vazio = sem
  ID; outro texto = sem ID e aviso no resumo (a base é importada). No formulário, um ID pendente
  da planilha mantido sem alteração continua pendente (outro ID inexistente → 422).
- **Vínculo sempre pelo ID do dataset** (PBI-13). Sem ID na planilha: "Disponível no Portal" → `extrair_name_da_url`
  → `Dataset.name` do inventário → grava o `Dataset.id` (que guarda o ID do CKAN em `id_ckan`, ADR-0018). Name com dataset = resolvido; name sem
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
  das palavras significativas do título (CGE → Controladoria Geral Estado); sem resultado pela
  sigla, os mesmos critérios com o **nome do órgão** (coluna "ORGAO" da tabela fato), se houver. `Atualizar vínculos`
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
  ou .csv (UTF-8 com ou sem BOM → Windows-1252 → Latin-1; separador ";" ou ",", ou o delimitador
  configurado), até 5 MB. Colunas localizadas pelo cabeçalho normalizado (sem acento, minúsculo,
  "_" como espaço), nas 30 primeiras linhas ou exatamente na linha configurada; campo a campo, na
  ordem de `CAMPOS` (obrigatórios primeiro), vale a coluna configurada e, se ela não estiver no
  arquivo, os nomes usuais — uma coluna preenche um campo só (assim a configuração SIGLA/ORGAO
  continua lendo a planilha da GEDA, em que "Órgão" é a sigla). Obrigatórios o órgão ("Sigla" ou
  "Órgão") e o nome da base ("Base de Dados" ou "NOME_PDA"); com "Sigla" no arquivo, "Órgão" vira o
  nome do órgão; aceita "Periodicidade" no lugar de "Atualização", "ID_UNICO"/"ID do dataset"/"ID
  CKAN" para o ID e "Meta/Prazo para abertura" (formato da planilha do PDA 2025-2027 exportada pela
  GEDA), "Previsão de abertura", "Prazo para abertura", "Prazo de abertura" ou "Prazo" para o prazo. Linhas vazias e rodapés ("Total", "Nenhum filtro aplicado", "Filtros
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
- **Sem coluna de ID do CKAN e sem "Disponível no Portal"** (caso da planilha 2025-2027) nenhuma
  base é vinculada na importação: todas ficam `sem_vinculo` e a situação vem só do prazo. O resumo
  avisa (`tem_coluna_id_ckan=false` e `tem_coluna_portal=false`). Vínculo por nome do dataset não é
  feito (ADR-0006).
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
- **Vínculo em lote pelo ID** resolvido para a tabela fato do PDA (coluna "ID_UNICO", 23/10/2026):
  das 410 bases do arquivo de exemplo, 345 têm ID e todas foram vinculadas no inventário local; as
  65 restantes ("Não encontrado") ficam sem vínculo. Confirmar com a GEDA que a tabela fato é o
  formato oficial de envio. PDA já importado sem ID não é revinculado: reimportar com a coluna.
- A configuração da importação fica no navegador (ADR-0020): cada pessoa e cada máquina tem a sua.
  Se a equipe precisar de uma configuração única, levar para o banco (nova ADR).
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
| 21/10/2026 | Vínculo base → dataset pela busca no inventário: `GET /formulario/datasets` (`buscar_datasets`), `BaseIn.dataset_id` (precede `dataset_link`; mesmo dataset mantém o name da planilha) e campo de busca `DatasetBusca` no `BaseFormModal` no lugar do link digitado; o órgão acompanha o do dataset escolhido. Sem mudança de tabela (FKs `dataset_id` → `dataset` e `dataset.organizacao_id` → `organizacao` já existiam) | Victor |
| 21/10/2026 | Chave primária própria no inventário (ADR-0018): `pda_base_prevista.organizacao_id` e `.dataset_id` passam a inteiros (`organizacao.id`, `dataset.id`); `BaseIn`, `BaseOut`, `DatasetOpcaoOut` e as opções de organização usam o `id`; `BaseOut.dataset_id_ckan` para o link do portal; `orgao_chave` = `id` em texto | Victor |
| 22/10/2026 | DAO (ADR-0019): `PdaDao` em `dao.py` concentra todo acesso ao banco do módulo; exclusão de PDA e de base passa a ser lógica (`deleted`), com as bases do PDA excluídas junto; `total_bases` conta só as ativas; únicos do nome e do vigente só entre ativos (nome de PDA excluído pode ser reaproveitado); gravações registram o usuário em `created_id`/`changed_id` (rotas de editar, vigente, excluir e vincular passam a receber o usuário) | Victor |
| 23/10/2026 | Merge com `desenvolvimento`: o campo "ID do dataset no CKAN" do Humberto passa a `BaseIn.dataset_id_ckan` (`_vinculo_por_id_ckan`, mesma validação, agora pelo `PdaDao`), abaixo de `dataset_id` (busca) na prioridade; na tela, o ID do CKAN é colado no campo de busca `DatasetBusca`, que já o aceita, em vez de um campo separado | Victor |
| 23/10/2026 | Importação com o ID do CKAN da planilha (ADR-0020): coluna "ID_UNICO" vincula a base ao dataset do inventário na importação (pendente pelo ID se não coletado; `pda_base_prevista.dataset_id_ckan_planilha`, migração `b9d4e6f2a7c1`); Atualizar vínculos resolve pelo ID; órgão também pelo nome do órgão; leitura configurável (`ConfigLeitura`: colunas, linha do cabeçalho, delimitador; campo `config` no `POST /planos`); resumo com `tem_coluna_id_ckan` e `avisos`; modal Importar PDA com abas Carregar/Configuração (configuração salva no navegador); `BaseOut.dataset_id_ckan_planilha` no formulário, detalhe e tabela | Victor |
