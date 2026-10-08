# Módulo `pda` — Monitoramento do Plano de Dados Abertos

| | |
|---|---|
| **Status** | Parcial — US6 e US8 implementadas (importação, múltiplos PDAs, vigente, vínculo por ID, situação do prazo, tela); US7 (PDA × espontânea) pendente |
| **Responsável** | Humberto (Eixo 1) |
| **User stories** | US6 (PBI-12 a PBI-15), US7 (PBI-16 a PBI-18, PBI-82), US8 (PBI-19 a PBI-22, PBI-80) |
| **Backend** | `backend/app/modules/pda/` · migrações `b7e2c41d9a63_pda_planos_e_bases_previstas.py` e `c3f8a2d15e70_pda_nome_unico_sem_maiusculas.py` |
| **Frontend** | `frontend/src/modules/pda/` · upload multipart por `api.upload` em `frontend/src/shared/api/client.ts` |
| **Última atualização** | 08/10/2026 |

## Propósito
Importa a planilha do PDA (Plano de Dados Abertos), cruza cada base prevista com os datasets
publicados no CKAN (pelo ID) e mostra, por órgão, a situação do prazo de abertura. Vários PDAs
podem ficar cadastrados; o **vigente** rege a tela e os indicadores e relatórios de gestão.

## Telas
| Tela | Rota | Permissão para ver | Ações na tela (permissão) |
|---|---|---|---|
| Monitoramento do PDA | `/pda` | `pda.acessar` | Escolher o PDA exibido (padrão = vigente); filtros e "Limpar filtros"; detalhe da base (clique ou Enter na linha); **Importar PDA** (`pda.gerenciar_planos`); **Definir como vigente** e **Excluir PDA**, só para PDA não vigente e com confirmação em modal (`pda.gerenciar_planos`); **Atualizar vínculos (N pendentes)**, só se houver pendentes (`pda.editar_vinculos`) |

- **Painel "PDA"** (acima dos filtros): select com os PDAs ("Nome (vigente)"), badge Vigente /
  Não vigente e a linha "N bases previstas · importado em dd/mm/aaaa por Fulano · vigência … ·
  arquivo". Trocar o PDA limpa os filtros e fecha o detalhe.
- **Filtros** (enviados ao backend): Órgão, Periodicidade e Ano (opções vindas de `opcoes` em
  `GET /bases`); Situação com os 6 rótulos fixos na ordem do protótipo (constante `SITUACOES` em
  `frontend/src/modules/pda/api.ts`, espelho de `regras.SITUACOES`); Prazo (Vencido / Próximos N
  dias, N = `janela_alerta_dias`).
- **Tabela**: Órgão | Base prevista (PDA) | Dataset CKAN | ID CKAN | Prazo | Periodicidade | Última
  atualização | Situação. Vínculo pendente mostra o name da planilha + badge "vínculo pendente";
  dataset inativo recebe badge "fora do portal"; ID abreviado (8 caracteres) com o completo no
  `title`; data estimada pela criação leva "(est.)". Contador "N base(s) encontrada(s) de M previstas".
- **Modal Importar PDA**: nome*, início e fim da vigência, arquivo .xlsx/.csv* (até 5 MB), "Definir
  como vigente" (marcado e travado quando é o primeiro PDA). Após o envio mostra o resumo (bases
  importadas, linhas ignoradas com motivo, vínculos resolvidos/pendentes, sem vínculo, órgãos sem
  correspondência), avisa quando falta a coluna "Prazo" (e lista as demais colunas opcionais
  ausentes) e seleciona o PDA novo.
- **Modal de detalhe** (`showDatasetDetails` do protótipo): nome, órgão, unidade, ID do dataset,
  dataset no portal, prazo, data de publicação (`metadata_created` do dataset vinculado e ativo;
  sem vínculo, "Não publicado"), periodicidade (+ original da planilha), última atualização real,
  recursos válidos, formatos dos recursos (sem repetição; formato é atributo do recurso), situação, conteúdo sigiloso, políticas públicas, PDA de origem e descrição;
  aviso se o dataset não está mais visível no portal; "Abrir no portal" (`/dataset/<ID>`). Usa os
  dados da própria linha (não chama `GET /bases/{id}`).
- **Teclado**: os modais (`shared/ui/Modal.tsx`) recebem o foco ao abrir, prendem Tab/Shift+Tab
  e devolvem o foco ao fechar; as linhas da tabela abrem o detalhe com Enter ou Espaço.
- **Estado vazio** (nenhum PDA): orienta a importar; botão Importar PDA ou, sem permissão, "Peça à
  Gerência de Dados Abertos para importar o PDA."

Referência visual: `#screen-pda` do Protótipo V1 (`renderPDA`, `getFilteredPDA`,
`pdaSituacaoDeadlineFlag`, `showDatasetDetails`, `statusBadge`). Ressalva de 17/09: PDA trata do
**prazo de abertura**; atualização periódica tem tela própria (módulo `atualizacoes`).

## API
| Método | Rota (`/api/v1/pda`) | Permissão | Descrição |
|---|---|---|---|
| GET | `/planos` | `pda.acessar` | PDAs cadastrados (`PlanoOut[]`): vigente primeiro, depois `importado_em` desc. Totais e vínculos respeitam o escopo de órgão do usuário |
| POST | `/planos` | `pda.gerenciar_planos` | multipart: `nome`, `arquivo`, `vigencia_inicio`/`vigencia_fim` (aaaa-mm-dd, opcionais), `definir_vigente` (padrão false) → 201 `ImportacaoResumoOut` (PBI-12). **409** nome repetido (sem diferenciar maiúsculas); **413** arquivo > 5 MB; **422** nome vazio ou com mais de 200 caracteres, extensão diferente de .xlsx/.csv, .xlsx/.csv ilegível, .xlsx grande demais descompactado (> 50 MB), mais de 20 abas ou de 20.000 linhas, cabeçalho obrigatório ausente, prazo ilegível, planilha sem base, data inválida ou fim < início |
| PUT | `/planos/{id}/vigente` | `pda.gerenciar_planos` | Define o PDA vigente → `PlanoOut`; **404** |
| DELETE | `/planos/{id}` | `pda.gerenciar_planos` | Exclui o PDA e suas bases → 204; **409** se for o vigente; **404** |
| POST | `/planos/{id}/vincular` | `pda.editar_vinculos` | Tenta de novo os vínculos pendentes → `VinculosOut` (PBI-12/13); **404** |
| GET | `/bases` | `pda.acessar` | `?plano_id=&orgao=&situacao=&periodicidade=&ano=&prazo=` → `BasesOut` (PBI-19 a 21). Sem `plano_id` usa o vigente; sem PDA → `plano=null` e listas vazias. **404** plano inexistente; **422** `ano` não numérico ou `prazo` diferente de `vencido`/`proximo` |
| GET | `/bases/{id}` | `pda.acessar` | `BaseOut`; **404** se não existe ou é de outro órgão para usuário restrito |

Conflito de gravação em paralelo (nome ou vigente) também devolve 409. Contrato JSON em
`schemas.py`, espelhado em `frontend/src/modules/pda/api.ts`; datas `aaaa-mm-dd`, datetimes ISO 8601 (UTC):
- `PlanoOut`: id, nome, vigencia_inicio, vigencia_fim, vigente, arquivo_nome, importado_por (nome
  do usuário), importado_em, total_bases, vinculos_resolvidos, vinculos_pendentes.
- `ImportacaoResumoOut`: plano, bases_importadas, linhas_ignoradas `[{linha, motivo}]`,
  vinculos_resolvidos, vinculos_pendentes, sem_vinculo, orgaos_sem_correspondencia,
  tem_coluna_prazo, colunas_opcionais_ausentes (rótulos).
- `VinculosOut`: vinculos_resolvidos (nesta execução), vinculos_pendentes (que continuam pendentes).
- `BaseOut`: dados da planilha + `orgao_chave` (organizacao_id ou `sigla:<SIGLA>`), orgao_nome,
  `vinculo` (resolvido/pendente/sem_vinculo), dataset_id, dataset_name e dataset_titulo **atuais**
  do inventário, dataset_name_planilha, dataset_ativo, data_publicacao, recursos_validos,
  formatos, ultima_atualizacao,
  ultima_atualizacao_estimada, situacao, `flag_prazo` (vencido/proximo/""), classificacao.
- `BasesOut`: plano, hoje, janela_alerta_dias, total_previstas (visíveis ao usuário, sem filtros),
  opcoes `{orgaos: [{valor, rotulo}], periodicidades, anos}`, bases (por órgão e nome).

## Serviços e métodos
`regras.py` (funções puras, reaproveitáveis numa extensão CKAN — ADR 0004):
- `ler_planilha(conteudo: bytes, nome_arquivo: str) -> PlanilhaLida` — PBI-12; `linhas:
  list[LinhaPda]`, `ignoradas: list[(linha, motivo)]`, `tem_coluna_prazo`,
  `colunas_opcionais_ausentes`. Leitura sob demanda e limitada (`TAMANHO_DESCOMPACTADO_MAXIMO` 50 MB,
  `ABAS_MAXIMO` 20, `LINHAS_MAXIMO` 20.000, `COLUNAS_MAXIMO` 60, fim da aba após 1.000 linhas vazias
  seguidas). Lança `PlanilhaInvalida`.
- `normalizar_periodicidade(texto) -> str` — valor do domínio `DOMINIO_PERIODICIDADE`.
- `extrair_name_da_url(valor) -> str | None` — name de `.../dataset/<name>`, só para achar o ID (PBI-13).
- `casar_orgao(sigla, orgaos: Iterable[(ckan_id, name, titulo, sigla)]) -> str | None`.
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
- `listar_planos(db, user=None) -> list[PlanoOut]` · `definir_vigente(db, plano_id) -> PlanoOut` ·
  `excluir_plano(db, plano_id) -> None`.
- `listar_bases(db, user, *, plano_id, orgao, situacao, periodicidade, ano, prazo) -> BasesOut` — PBI-20/21.
- `obter_base(db, base_id, user) -> BaseCalculada`.
- **Para outros módulos:** `plano_vigente(db) -> PlanoPda | None` e
  `bases_do_plano(db, plano_id, user=None, *, hoje=None, janela_dias=None) -> list[BaseCalculada]`
  — PBI-19; `BaseCalculada` é uma dataclass congelada com os campos de `BaseOut`; `user=None` =
  sem escopo de órgão (uso consolidado). 404 se o plano não existe.
- `hoje_local() -> date` (America/Sao_Paulo) · `janela_alerta_dias(db) -> int` (PBI-22) ·
  `calcular_base(base, plano_nome, hoje, janela_dias)` · `orgao_chave(organizacao_id, orgao_sigla)`.

Datasets, recursos e organizações são carregados com `selectinload`: 7 consultas para ~450 bases,
sem N+1. Testes: `tests/test_pda_regras.py`, `tests/test_pda_api.py` e
`tests/test_pda_revisao.py` (regressões da revisão de 08/10/2026).

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
| `pda.gerenciar_planos` | Administrador, Gerência GEDA — importar PDA, definir o vigente e excluir PDA |

Em banco já existente, a Gerência GEDA não recebe `pda.gerenciar_planos` sozinha (ver Pendências).

## Interações com outros módulos
| Direção | Módulo | O quê |
|---|---|---|
| consome | inventario | `Dataset` (ID, name, título, órgão, `ativo_no_portal`, `metadata_created`), `Recurso` (`eh_dicionario_dados`, `formato`, `last_modified`, `created`) via `service.recursos_atuais(ds)` (só recursos ainda no pacote do dataset), `Organizacao` (casamento da sigla) |
| consome | parametros | `obter(db, "janela_alerta_prazo_dias")` (PBI-22) |
| consome | atualizacoes | `service.ultima_atualizacao_real(recursos)` → `UltimaAtualizacao(data, estimada)` (implementada em `atualizacoes/regras.py`) |
| consome | acesso | `filtrar_por_orgao(stmt, BasePrevista.organizacao_id, user)` nas consultas de bases |
| é consumido por | painel | `plano_vigente(db)` + `bases_do_plano(db, plano.id, user)` — bases previstas × publicadas e prazos por órgão (US19); sempre o PDA vigente |
| é consumido por | relatorios | idem — relatório de bases não publicadas e prazos; sempre o PDA vigente |
| é consumido por | assistente | idem, só agregados e com `user` para respeitar o escopo de órgão |
| é consumido por | atualizacoes | `classificacao` para o indicador PDA × espontânea (PBI-82, previsto) |

## Jobs agendados
Nenhum. A situação é calculada na consulta, sobre o inventário da última coleta. Vínculos
pendentes só são refeitos pelo botão Atualizar vínculos (não automaticamente após a coleta).

## Regras de negócio e decisões
Decisões registradas: [ADR-0006](../adr/0006-regras-de-afericao-do-inventario.md).

- **Vários PDAs, um vigente** (decisão de 07/10/2026, Humberto/Eixo 1 — pendente de validação da
  GEDA). Nome obrigatório e único (espaços colapsados, sem diferenciar maiúsculas). O primeiro PDA
  cadastrado vira vigente mesmo sem `definir_vigente`. Garantia dupla: índice único parcial e
  transação (desmarca todos, marca o escolhido, flush). O vigente não pode ser excluído. Outros
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
  como SEAD × "administracao"); c) `casar_orgao` (sem acento, minúsculo): 1) `Organizacao.sigla`;
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
  | Em atraso | não publicada e prazo < hoje | vermelho |
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
  de Dados"; aceita "Periodicidade" no lugar de "Atualização" e "Prazo de abertura" no lugar de
  "Prazo". Linhas vazias e rodapés ("Total", "Nenhum filtro aplicado" — só na coluna Órgão) são
  pulados; cabeçalho repetido no meio da planilha e linha sem Órgão ou Base de Dados vão para
  `linhas_ignoradas` (número 1-based e motivo). Tetos contra planilha malformada ou "bomba" de
  compressão: ver `ler_planilha`.
- **Prazo** só da coluna opcional "Prazo" (date do xlsx, dd/mm/aaaa ou aaaa-mm-dd, com hora
  opcional ignorada, ou serial do Excel 2000–2099). Sem a coluna → nulo; **nunca** derivado da vigência; valor presente e ilegível → 422
  na importação inteira.
- Importação **atômica** (qualquer erro → rollback). O arquivo bruto não é gravado: só os dados
  extraídos e o nome do arquivo. Textos longos são cortados no tamanho da coluna.
- Bases espontâneas também devem ser monitoradas (Paloma e Júnior, 17/09) — ainda não
  implementado: `classificacao` é sempre "pda".

## Pendências
- **Prazo de abertura ausente na planilha da GEDA**: sem a coluna "Prazo", quase todas as bases não
  publicadas caem em "Não publicado" e os filtros Ano e Prazo ficam vazios. Pedir a coluna à GEDA.
- Validar com a GEDA a regra de vários PDAs com um vigente (decisão de 07/10/2026).
- "Bianual" mapeado para Bienal, mas é ambíguo (pode significar semestral) — validar com a GEDA.
- De-para de órgãos: as organizações do portal não têm `sigla`; siglas como AGEHAB, AGR, SECULT,
  SANEAGO, DETRAN e CASA MLITAR ficam sem correspondência quando a base não tem dataset vinculado. Hoje só há a
  heurística; avaliar preencher `Organizacao.sigla` ou criar uma tabela de-para.
- Banco já existente: `sincronizar_papeis_padrao` não sobrescreve ajustes, então o papel Gerência
  GEDA **não** recebe `pda.gerenciar_planos` automaticamente — conceder pela tela Usuários e papéis
  (o Administrador recebe por `todas`).
- Fora deste escopo: critério das bases espontâneas e reclassificação PDA × espontânea (PBI-16 a
  PBI-18, PBI-82); edição manual de vínculo base a base.
- Relatórios e exportação das bases do PDA (US20): consumir `bases_do_plano` no módulo `relatorios`.
- A última atualização usa `created` só quando nenhum recurso válido tem `last_modified`; o PBI-25
  pode pedir o fallback por recurso — validar.
- O órgão de uma base já vinculada não acompanha mudança de órgão do dataset após a importação.
- US7 (PBI-16 a PBI-18, PBI-82) e os PBI-14 e PBI-80 do Backlog v2 não foram atendidos nesta
  entrega: conferir no backlog o escopo de cada um (a edição manual de vínculo base a base é
  candidata ao PBI-14).
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
