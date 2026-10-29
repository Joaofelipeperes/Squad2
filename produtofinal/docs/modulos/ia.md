# Módulo `ia` — Configuração de modelos de IA

| | |
|---|---|
| **Status** | Implementado |
| **Responsável** | Luiza (uso nas US11/US28) |
| **User stories** | US11, US28 (PBI-96) |
| **Backend** | `backend/app/modules/ia/` · adaptadores em `backend/app/integrations/ai/` |
| **Frontend** | `frontend/src/modules/ia/` |
| **Última atualização** | 27/10/2026 |

## Propósito
Permite trocar entre modelos locais e comerciais sem alterar código e garante que dados pessoais
só sejam processados por modelos de execução local.

## Telas
| Tela | Rota | Permissão para ver | Ações na tela (permissão) |
|---|---|---|---|
| Modelos de IA | `/admin/ia` | `ia.configurar` | Vincular modelo principal/contingência por tarefa; criar, editar, testar e excluir perfis; testar tarefa; ver uso recente (todas com `ia.configurar`) |

## API
Todas as rotas exigem `ia.configurar` (dependência no nível do router).

| Método | Rota (`/api/v1/ia`) | Descrição |
|---|---|---|
| GET | `/tipos-provedor` | Adaptadores disponíveis e campos do formulário |
| GET / POST | `/perfis` | Lista / cria perfil |
| PUT / DELETE | `/perfis/{id}` | Edita / exclui (409 se vinculado a tarefa) |
| POST | `/testar-conexao` | Testa e lista modelos antes de salvar |
| POST | `/perfis/{id}/testar` | Envia mensagem curta ao modelo salvo |
| GET | `/tarefas` | Tarefas e vínculos atuais |
| PUT | `/tarefas/{tarefa}` | Define principal e contingência |
| GET | `/uso?limite=50` | Registro de chamadas (sem conteúdo) |
| POST | `/playground` | Executa uma tarefa pelo gateway |

## Serviços e métodos
`gateway.py` — **ponto único de acesso à IA** para os demais módulos:
- `AIGateway(db).chat(tarefa, request) -> (ChatResponse, perfil, usou_fallback)` — resolve o
  vínculo, aplica a política, chama o adaptador, tenta a contingência, registra o uso.
- `AIGateway(db).embed(tarefa, textos) -> (EmbedResponse, perfil, usou_fallback)` — o mesmo
  caminho para tarefas do tipo `embeddings` (ex.: bge-m3); `configurada(tarefa)` diz se há perfil
  ativo (para etapas opcionais). Chamar `chat` numa tarefa de embeddings (ou o contrário) é erro.

`service.py`: `listar_tipos`, `salvar_perfil`, `config_do_perfil`, `testar`, `testar_resposta`,
`listar_tarefas`, `vincular`, `listar_perfis`, `excluir_perfil` (exclusão lógica; vinculado → erro),
`listar_usos`.

`dao.py` — `IaDao(Dao)` (ADR-0019): todas as consultas e gravações (perfis, vínculos, uso). O
gateway grava o uso pelo DAO; `excluir_perfil` limpa vínculos que apontassem para o perfil (como o
antigo ON DELETE SET NULL).

`integrations/ai/`: contrato `AIProvider` (`chat`, `list_models`, `fields` e o opcional `embed`,
implementado por `ollama` e `openai_compat`), `registry`
(`@register_provider`, `build_provider`), `policy` (`TarefaIA`, `TAREFAS`, `verificar`) e
adaptadores `anthropic`, `gemini`, `ollama`, `openai_compat`, `mock`.

Adaptador `anthropic` (Claude, `/v1/messages`, sem SDK): junta mensagens seguidas do mesmo papel e
descarta as que antecedem a primeira pergunta; desliga o raciocínio (`thinking`) para responder
mais rápido; se o modelo recusar `temperature` (HTTP 400), refaz sem o parâmetro e lembra o modelo
até reiniciar; só os blocos de texto da resposta contam. Sugestões: `claude-haiku-5-5`,
`claude-haiku-4-5`.

## Modelo de dados
Diagrama e dicionário de dados completos: [MER](../banco/mer.md) · regras: [convenções do banco](../banco/convencoes.md).

| Tabela | Colunas relevantes |
|---|---|
| `ia_vinculo_tarefa` | id (PK), tarefa (única entre ativos; antes era a PK), perfil_id, perfil_fallback_id, alterado_por |
| `ia_perfil_provedor` | nome (único entre ativos), tipo, modelo, base_url, api_key_cifrada (Fernet), api_key_dica, execucao_local, temperatura, max_tokens, timeout_s, ativo, extra (campos adicionais do provedor, não secretos) |
| `ia_uso` | momento, tarefa, perfil, modelo, sucesso, usou_fallback, latência, tokens, erro |

Toda tabela também tem `id` (PK), `deleted`, `created`/`created_id` e `changed`/`changed_id` (ADR-0019); únicos valem só entre registros ativos.

## Permissões
| Permissão | Papéis padrão | Sensível |
|---|---|:-:|
| `ia.configurar` | Administrador | ✓ |

## Interações com outros módulos
| Direção | Módulo | O quê |
|---|---|---|
| é consumido por | lgpd | tarefas `classificacao_dp` (chat) e `embeddings_dp` (embeddings), ambas sensíveis → só modelo local |
| é consumido por | assistente | tarefa `assistente` (não sensível) |

## Jobs agendados
Nenhum.

## Regras de negócio e decisões
Decisões registradas: [ADR-0002](../adr/0002-camada-ia-plugavel.md) · [ADR-0010](../adr/0010-deteccao-de-dados-pessoais-hibrida.md) · [ADR-0020](../adr/0020-claude-haiku-no-assistente.md) (em análise).

- Tarefa sensível só aceita perfil local; checado ao vincular, ao editar o perfil e a cada chamada.
  Exceção apenas com `GDA_IA_PERMITIR_EXTERNO_PARA_SENSIVEL=true` (decisão da CGE-GO).
- Chave de API cifrada no banco e nunca devolvida pela API.
- `ia_uso` não guarda prompt nem resposta (PBI-35).
- Novo fornecedor = um arquivo em `integrations/ai/providers/` com `@register_provider`.
- Campos adicionais de um provedor: declarar em `fields()` com nome diferente de `base_url`,
  `model` e `api_key`. A tela mostra o campo, `PerfilIn.extra`/`TesteConexaoIn.extra` recebem o
  valor e `service.extra_valido` grava em `extra` só o que o provedor declarou (não secreto).
  Ex.: "ID do workspace" do `anthropic` (cabeçalho `anthropic-workspace-id`, exigido por chave
  de API que não pertence a um workspace).
- Nova tarefa = entrada em `integrations/ai/policy.py`; aparece sozinha na tela. `MetaTarefa.tipo`
  (`chat` | `embeddings`) define o que o gateway aceita; o playground lista só tarefas de chat e o
  botão Testar de um perfil vinculado só a embeddings gera um embedding de teste.
- Ollama: pede `think: false` (Qwen3/Qwen3.5 sem raciocínio, mais rápidos em CPU e com JSON limpo);
  modelo que não aceita o parâmetro (Qwen2.5) é chamado de novo sem ele e lembrado até reiniciar;
  bloco `<think>` no texto é descartado. Sugestões: `qwen2.5:7b-instruct`, `qwen3:8b`,
  `qwen3.5:9b`, `bge-m3` (confirmar as tags no `ollama list`).

## Pendências
- Chave do Gemini (SECTI) e servidor para modelo local em produção.
- Escolha do modelo do Assistente (ADR-0020).

## Histórico de alterações
| Data | Alteração | Autor |
|---|---|---|
| 30/09/2026 | Implementação: perfis, tarefas, gateway com política LGPD e tela | Victor |
| 30/09/2026 | Acesso passa a exigir `ia.configurar` do catálogo central | Victor |
| 07/10/2026 | Link para o MER e as convenções do banco | Victor |
| 22/10/2026 | Banco só pelo `IaDao` (ADR-0019): exclusão lógica de perfis (o nome fica livre), `ia_vinculo_tarefa` com `id` próprio, auditoria com quem configurou; `atualizado_em` vem de `changed` | Victor |
| 23/10/2026 | Adaptador `anthropic` (Claude) para modelos comerciais da Anthropic | Squad 2 |
| 23/10/2026 | Campos adicionais por provedor gravados em `extra` (tela, API e teste de conexão); campo "ID do workspace" no `anthropic` | Squad 2 |
| 26/10/2026 | Embeddings no contrato (`embed`) e no gateway; tarefa `embeddings_dp` (filtro semântico da varredura LGPD); `think: false` com fallback no Ollama; tipo da tarefa na API e na tela | Squad 2 |
| 27/10/2026 | Merge com `desenvolvimento`: `embed`, `configurada` e o teste de embedding pelo `IaDao` (`vinculos_do_perfil`); `extra` devolvido com `atualizado_em` = `changed` | Luiza |
