# Módulo `lgpd` — Dados pessoais e anonimização

| | |
|---|---|
| **Status** | Parcial (varredura CSV/XLSX, triagem e anonimização prontas; PDF a implementar) |
| **Responsável** | Luiza (Eixo 2) |
| **User stories** | US11, US12, US13, US26, US27 (PBI-31 a PBI-42, PBI-86 a PBI-95) |
| **Backend** | `backend/app/modules/lgpd/` · escrita no CKAN em `backend/app/integrations/ckan/writer.py` |
| **Frontend** | `frontend/src/modules/lgpd/` |
| **Última atualização** | 30/10/2026 |

## Propósito
Varre os recursos publicados em busca de possíveis dados pessoais, prioriza os achados para revisão
humana e, após aprovação, publica no CKAN a versão anonimizada do recurso.

## Telas
| Tela | Rota | Permissão para ver | Ações na tela (permissão) |
|---|---|---|---|
| Riscos de Dados Pessoais | `/lgpd` | `lgpd.acessar` | Varrer recursos novos/alterados ou um dataset (`lgpd.varrer`; a busca de dataset usa `inventario.acessar`); marcar falso positivo / confirmado / tratado / voltar para revisão, com justificativa (`lgpd.triar`); anonimizar recurso com achados confirmados — prévia, baixar prévia, aprovar e publicar, descartar, reverter (`lgpd.aprovar_correcao`); painel Anonimizações (`lgpd.acessar`) |

Referência visual: `#screen-lgpd` e `#modal-lgpd` do Protótipo V1 (4 KPIs, filtros de
prioridade/tipo/órgão/status, tabela e modal com barra de confiança; o callout do topo foi retirado). Acréscimos ao protótipo:
painel "Varredura dos recursos" (o protótipo usava dados fixos), "Por que foi sinalizado" (trilha do
score), histórico de decisões e, no lugar do valor mascarado, o aviso de não retenção com a
coluna e a linha para conferir no arquivo.

## API
| Método | Rota (`/api/v1/lgpd`) | Permissão | Descrição |
|---|---|---|---|
| GET | `/achados?prioridade=&tipo=&orgao=&status=` | `lgpd.acessar` | KPIs, opções dos filtros e achados (prioridade, depois confiança) |
| GET | `/achados/{id}` | `lgpd.acessar` | Detalhe + explicação do score + histórico de decisões |
| POST | `/achados/{id}/decisao` | `lgpd.triar` | `{decisao: confirmado\|falso_positivo\|tratado\|revisar, justificativa?}` (PBI-40/42) |
| GET | `/varreduras?limite=30` | `lgpd.acessar` | Últimas varreduras e quantas estão em andamento |
| POST | `/varreduras` | `lgpd.varrer` | `{escopo: pendentes\|dataset\|recurso, id?}` (`id` próprio do dataset ou recurso, ADR-0018) → 202; só enfileira — o worker executa em até 1 min (ADR-0025); `pendentes` limitado a `GDA_LGPD_VARREDURA_MAX_RECURSOS` (200) por pedido |
| POST | `/varreduras/cancelar` | `lgpd.varrer` | Cancela as varreduras que ainda não começaram |

| GET | `/correcoes?limite=` | `lgpd.acessar` | Anonimizações + `escrita_habilitada`, operadores e alcances |
| GET | `/correcoes/{id}` | `lgpd.acessar` | Detalhe; na prévia, exemplos JÁ anonimizados lidos do arquivo |
| POST | `/correcoes` | `lgpd.aprovar_correcao` | `{recurso_id, itens: [{achado_id, operador, alcance}]}` → 202; gera a prévia em segundo plano (PBI-91) |
| GET | `/correcoes/{id}/arquivo-previa` | `lgpd.aprovar_correcao` | Baixa o arquivo anonimizado da prévia (o original nunca é servido) |
| POST | `/correcoes/{id}/aprovar` | `lgpd.aprovar_correcao` | Publica no CKAN (PBI-92/93); 409 com escrita desligada ou original alterado |
| POST | `/correcoes/{id}/descartar` | `lgpd.aprovar_correcao` | Descarta a prévia e apaga os arquivos |
| POST | `/correcoes/{id}/reverter` | `lgpd.aprovar_correcao` | `{motivo}` — reenvia o original (PBI-94) |

## Serviços e métodos
Motor de detecção — `deteccao.py`, porta do **`detector3.py`** (funções puras, sem rede):
reconhecedores CPF/CNPJ (inclusive alfanumérico) com dígito verificador, e-mail, telefone (DDD e
prefixos), CEP; `PerfilColuna` (valores atípicos); `AprimoradorContexto`; `Analisador`
(sobreposição e limiar); `descartar_coincidencias`; `FiltroEmbeddings` + `EnderecoLLMReconhecedor`
com o mesmo prompt, protótipos e amostra da coluna do script. A IA entra como funções:
`embed_fn` e `chat_fn`, montadas pelo service com o `AIGateway`.
- `montar_analisador(limiar, chat_fn, filtro, llm_todas, nome_modelo)` · `analisar_coluna(...)`.

Leitura — `leitura.py`: `ler(conteudo, formato)` → tabelas (CSV/TSV/TXT com encoding e separador
detectados; XLSX com todas as abas), blocos de 50 mil linhas; `formato_do_recurso`.

Regras — `regras.py`: `agregar` (um achado por coluna e tipo: primeira linha, nº de células, maior
confiança), `prioridade`, `impressao_digital`, `rotulo_tipo`.

`dao.py` — `LgpdDao(Dao)` (ADR-0019): todas as consultas e gravações do módulo (achados no escopo de
órgão, decisões, varreduras e fila, anonimizações, leitura do inventário e do modelo vinculado a uma
tarefa de IA). Achado que some do arquivo é excluído logicamente (`delete_generic`).

`service.py`:
- `listar_achados`, `obter_achado`, `decidir` — tela e triagem, no escopo de órgão.
- `solicitar(db, escopo, id, user)` → varreduras `pendente` (sem duplicar recurso na fila); a API
  só enfileira, quem executa é o worker (ADR-0025);
  `recursos_do_escopo` (pendentes = CSV/XLSX nunca varridos ou com `last_modified` posterior à
  última varredura).
- `job_executar_fila()` — job do worker, único executor da fila: `_retomar_interrompidas` (varredura
  ainda em `executando` no início do ciclo vira erro e o recurso volta à fila uma vez) e depois as
  pendentes, a mais antiga primeiro, até a fila esvaziar.
- `executar_varredura(db, v)` — baixa (`CkanClient.url_download` + `baixar`, até
  `tamanho_maximo_recurso_lgpd_mb`; intervalo por host e espera no HTTP 429), lê, roda o motor
  coluna a coluna, agrega e grava.
- `montar_motor(db)` — limiar = `confianca_minima_lgpd`/100; tarefa `classificacao_dp` (modelo
  local de chat, ex.: qwen2.5:7b-instruct, qwen3:8b, qwen3.5:9b) e `embeddings_dp` (ex.: bge-m3),
  margem `margem_embeddings_lgpd`.
- `job_varredura_incremental()` — job do worker; só enfileira.
- `classificar_colunas_ambiguas` — classificação por coluna anterior; não usada pela varredura.

Anonimização — `anonimizacao.py` (puro): operadores `mascara_cpf` (regra da GEDA: oculta 3 primeiros
e 2 últimos dígitos), `substituir` (`<CPF>`), `mascarar`, `hash` (com sal), `remover`; alcances
`detectados` (reencontra o trecho com o motor) e `coluna` (célula inteira); `planejar` e
`reescrever` (CSV com mesmo encoding/BOM, separador, quebra de linha e aspas; XLSX com openpyxl).

`correcoes.py`: `solicitar_previa` → `gerar_previa` (segundo plano: baixa, guarda a cópia em
`GDA_LGPD_ARQUIVOS_DIR/correcao_NNNNNN/original/`, aplica e grava `anonimizado/`), `obter`/`listar`,
`arquivo_previa`, `aprovar` (confere o hash do original no portal; publica com `CkanWriter`;
achados alterados viram "tratado"), `descartar` (apaga os arquivos), `reverter` (reenvia o original;
achados voltam a "confirmado").

## Modelo de dados
Diagrama e dicionário de dados completos: [MER](../banco/mer.md) · regras: [convenções do banco](../banco/convencoes.md).

| Tabela | Colunas relevantes |
|---|---|
| `lgpd_achado` | recurso_id (→ `recurso.id`, inteiro), coluna, linha, ocorrencias, tipo, metodo (regra/ia), confianca, prioridade, status, impressao_digital |
| `lgpd_decisao` | achado_id, decisao, justificativa, usuario, momento (histórico imutável — PBI-42) |
| `lgpd_correcao` | recurso_id (→ `recurso.id`, inteiro), aprovado_por, aprovado_em, caminho_backup, status, erro |
| `lgpd_achado` | recurso_id, coluna, linha (primeira), ocorrencias, tipo, metodo (regra/ia), confianca, prioridade, status, impressao_digital, explicacao |
| `lgpd_varredura` | recurso_id, status (pendente/executando/ok/erro/ignorado/cancelada), origem, solicitada_por, datas, linhas_analisadas, chamadas_ia, achados, modelo, aviso, erro |
| `lgpd_decisao` | achado_id, decisao, justificativa, usuario, momento (histórico imutável — PBI-42) |
| `lgpd_correcao` | recurso_id, status (gerando_previa/previa/publicando/publicada/revertendo/revertida/descartada/erro), solicitada_por, itens (JSON: achado, coluna, operador, alcance, contagens, linhas de exemplo — sem valores), celulas_alteradas, nome_arquivo, formato, hash_original, caminho_backup, caminho_previa, aprovado_por/em, justificativa, publicada_em, revertida_por/em, motivo_reversao, erro |

Toda tabela também tem `id` (PK), `deleted`, `created`/`created_id` e `changed`/`changed_id` (ADR-0019); `recurso_id` → `recurso.id` (ADR-0018).

## Permissões
| Permissão | Papéis padrão | Sensível |
|---|---|:-:|
| `lgpd.acessar` | Administrador, Gerência GEDA, Equipe GEDA | ✓ |
| `lgpd.triar` | Administrador, Gerência GEDA | ✓ |
| `lgpd.varrer` | Administrador, Gerência GEDA | ✓ |
| `lgpd.aprovar_correcao` | Administrador, Gerência GEDA | ✓ |

## Interações com outros módulos
| Direção | Módulo | O quê |
|---|---|---|
| consome | inventario | `Recurso` (url, url_type, formato, last_modified), `Dataset` (órgão, ativo), `recursos_atuais` |
| consome | ia | `AIGateway.chat(TarefaIA.CLASSIFICACAO_DADO_PESSOAL)` e `AIGateway.embed(TarefaIA.EMBEDDINGS_DADO_PESSOAL)` — sensíveis, só modelo local |
| consome | parametros | `tipos_dado_pessoal`, `confianca_minima_lgpd`, `margem_embeddings_lgpd`, `tamanho_maximo_recurso_lgpd_mb` |
| consome | CKAN (integração) | `CkanClient.url_download` + `baixar` (leitura dos arquivos, com intervalo mínimo por host e espera no HTTP 429 — ADR-0025); `CkanWriter.replace_resource_file` (publicação e reversão da anonimização) — única escrita do sistema |
| é consumido por | painel | `service.resumo_dados_pessoais(db, user)` — **apenas contagens** por tipo e status (cartão e gráfico "Possíveis dados pessoais" do Dashboard, só com `lgpd.acessar`); ranking de exposição por órgão (US27) a implementar |
| é consumido por | atualizacoes | correções publicadas não contam como atualização (PBI-79) |
| é consumido por | relatorios | relatório priorizado (PBI-38) |
| é consumido por | assistente | `Achado`: **apenas contagens** por dataset, tipo e status — nunca coluna, linha ou valor |

## Jobs agendados
| Job | Quando | O quê |
|---|---|---|
| `lgpd.varredura_incremental` | `GDA_LGPD_VARREDURA_CRON` (padrão 05:00) | Enfileira recursos novos ou alterados, até `GDA_LGPD_VARREDURA_MAX_RECURSOS` (200) por execução (PBI-34) |
| `lgpd.fila_varredura` | `GDA_LGPD_FILA_CRON` (padrão a cada minuto) | Executa a fila: retoma a interrompida (uma vez por recurso) e varre as pendentes até esvaziar (ADR-0025) |

## Regras de negócio e decisões
Decisões registradas: [ADR-0008](../adr/0008-anonimizacao-com-publicacao-no-ckan.md) · [ADR-0010](../adr/0010-deteccao-de-dados-pessoais-hibrida.md) · [ADR-0021](../adr/0021-varredura-lgpd-com-motor-do-detector3.md) (proposta) · [ADR-0025](../adr/0025-fila-da-varredura-lgpd-executada-pelo-worker.md).

- **Não retenção** (PBI-35): o achado guarda localização, tipo e a trilha do score — nunca o valor.
  A tela mostra onde conferir (coluna e linha) em vez do valor mascarado do protótipo.
- **Um achado por (recurso, coluna, tipo)**: linha = primeira ocorrência; ocorrências = células.
- **Prioridade** (proposta até validação da GEDA): CPF sempre Alta; demais pela confiança (≥90 Alta,
  ≥70 Média, abaixo Baixa); CNPJ e CEP no máximo Média.
- **Tipos reportados** = parâmetro `tipos_dado_pessoal` (padrão sem `cnpj` e `cep`: incluir lá se a
  GEDA quiser vê-los). O motor ainda não detecta `nome` nem `data_nascimento`.
- Achado já avaliado não volta como novo (`impressao_digital`, PBI-41); achado que sumiu do arquivo e
  ninguém avaliou é removido na nova varredura.
- **Falha explícita**: modelo local fora do ar → varredura com erro e nada gravado. Etapa sem modelo
  vinculado → pulada com aviso na varredura (só regras, ou só atípicos sem o filtro semântico).
- Resposta do modelo fora do formato → célula marcada para revisão com score `max(0.5, limiar)`.
- Arquivo enviado ao CKAN (`url_type = upload`) é baixado pelo endereço da API do CKAN configurado,
  montado com o `id_ckan` do dataset e do recurso
  (`GDA_CKAN_BASE_URL`), não pela URL pública gravada — no Docker, `localhost:5000` não é o CKAN.
- Sinaliza, não bloqueia a publicação (PBI-39).
- **Fila no banco, executada pelo worker** (ADR-0025): reiniciar a API ou o worker não perde a fila.
  Varredura interrompida no meio vira erro ("Varredura interrompida…") e o recurso volta à fila uma
  vez; se for interrompido de novo, fica só o erro (arquivo que derruba o processo não prende a fila).
- Downloads espaçados por host (`GDA_CKAN_DOWNLOAD_INTERVALO_S`, padrão 2 s); no HTTP 429 espera o
  `Retry-After` ou 60 s, 2 min, 4 min… até `GDA_CKAN_DOWNLOAD_ESPERAS_429` vezes (padrão 5).
- **Anonimização** (ADR-0008): só achados *confirmados*; só recursos `upload` (link externo → acionar o
  órgão); prévia obrigatória; publica exatamente o arquivo da prévia e só se o original no portal
  ainda tiver o mesmo hash; escrita exige `GDA_CKAN_WRITE_ENABLED=true` e token da GEDA.
  Operador padrão: CPF com a regra da GEDA, demais com o marcador do tipo.
- Cópia do original e prévia **fora do banco** (permissão 600), apagadas ao descartar ou em erro;
  a cópia de uma correção publicada é mantida para reversão até a política de retenção da GEDA.
- Depois da publicação o `last_modified` do recurso muda: a próxima varredura "pendentes" relê o
  arquivo e confirma que os dados sumiram.

## Pendências
- PDF (motor do `detector3_pdf.py`: texto, tabelas e OCR) — exige PyMuPDF e Tesseract (ADR).
- Prazo de retenção da cópia do original e expurgo automático (GEDA).
- Correções publicadas não contam como atualização (PBI-79, módulo atualizacoes).
- Validar com a GEDA: regra de prioridade, lista de tipos e se CNPJ/CEP entram.
- Calibrar `margem_embeddings_lgpd` com o gabarito (avaliar.py) e comparar qwen2.5 × qwen3 × qwen3.5.
- Lista objetiva de tipos de dado pessoal e regras de anonimização por tipo (CGE-GO).
- Política de retenção do original (GEDA). Credencial de escrita e autorização formal (PBI-95).
- Servidor para modelo local em produção (SECTI).
- Prévia da anonimização ainda roda em segundo plano na API e se perde num reinício (aplicar a
  solução da ADR-0025).
- Tempo máximo por varredura: um modelo local travado já prendeu a fila por 5 h (29/10).

## Histórico de alterações
| Data | Alteração | Autor |
|---|---|---|
| 30/09/2026 | Tabelas, pipeline e etapa de classificação por IA (`classificar_colunas_ambiguas`) | Victor |
| 30/09/2026 | Permissões granulares `lgpd.acessar`, `lgpd.triar`, `lgpd.aprovar_correcao` | Victor |
| 07/10/2026 | Docstring nas tabelas sem descrição, para o MER gerado (ADR-0013); sem mudança de esquema | Victor |
| 21/10/2026 | Chave primária própria no inventário (ADR-0018): `lgpd_achado.recurso_id` e `lgpd_correcao.recurso_id` passam a inteiros → `recurso.id` (migração `f6c3a8d2b1e7`) | Victor |
| 23/10/2026 | Interações: o que o Assistente consome deste módulo | Squad 2 |
| 26/10/2026 | Varredura com o motor do detector3 (regras + filtro semântico + modelo local pelo gateway), leitura CSV/XLSX, tabela `lgpd_varredura`, `explicacao` no achado, rotas, permissão `lgpd.varrer`, job incremental e tela Riscos de Dados Pessoais conforme o Protótipo V1 | Squad 2 |
| 26/10/2026 | Anonimização (US26): prévia em segundo plano com cópia do original fora do banco, aprovação com conferência de hash e publicação via `CkanWriter`, descarte, reversão; operadores (regra da GEDA para CPF) e alcances; tabela `lgpd_correcao` ampliada; telas de prévia, aprovação e painel Anonimizações | Squad 2 |
| 26/10/2026 | Cancelar fila de varredura; `pendentes` limitado por pedido; link quebrado (404) e acesso negado (403) explicados na varredura; arquivo compactado/PDF declarado como CSV vira "ignorado" | Squad 2 |
| 26/10/2026 | Tela: removido o aviso fixo do topo ("resultados indicativos…"), a pedido da Eixo 2 | Squad 2 |
| 26/10/2026 | Painel de varredura com as duas opções explicadas (todo o portal × um dataset específico); detecção: CPF/CNPJ com máscara completa não é descartado pela regra de coincidência (colunas de códigos) | Luiza |
| 27/10/2026 | Merge com `desenvolvimento` (ADR-0018/0019): `LgpdDao` concentra o acesso ao banco; `lgpd_achado`, `lgpd_varredura` e `lgpd_correcao` apontam para `recurso.id` e herdam `id`/`deleted`/auditoria da `Base`; API e tela usam o `id` próprio de dataset e recurso; download e publicação no CKAN pelo `id_ckan`; migrações refeitas numa só (`9d583e5bd118`, sobre `a8e2f5c1d9b4`) | Luiza |
| 28/10/2026 | Migração `9d583e5bd118`: `lgpd_varredura.deleted` com `server_default=sa.false()` (era `sa.text('0')`, aceito no SQLite e recusado no PostgreSQL — a API não subia no Docker) | Victor |
| 29/10/2026 | Fila executada pelo worker (ADR-0025): `POST /varreduras` só enfileira; job `lgpd.fila_varredura` a cada minuto retoma a interrompida (uma vez por recurso) e varre as pendentes; `executar_fila` e a liberação após 12 h removidos; job incremental só enfileira; download com intervalo por host e espera no HTTP 429 | Victor |
| 30/10/2026 | Resumo agregado para o Dashboard: `service.resumo_dados_pessoais` e `ResumoDadosPessoaisOut` (recursos analisados e com achados, aguardando revisão, críticos, por tipo sem falso positivo e por status) — só contagens, no escopo do usuário | Humberto |
