# Módulo `ia` — Configuração de modelos de IA

| | |
|---|---|
| **Status** | Implementado |
| **Responsável** | Luiza (uso nas US11/US28) |
| **User stories** | US11, US28 (PBI-96) |
| **Backend** | `backend/app/modules/ia/` · adaptadores em `backend/app/integrations/ai/` |
| **Frontend** | `frontend/src/modules/ia/` |
| **Última atualização** | 30/09/2026 |

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

`service.py`: `listar_tipos`, `salvar_perfil`, `config_do_perfil`, `testar`, `testar_resposta`,
`listar_tarefas`, `vincular`.

`integrations/ai/`: contrato `AIProvider` (`chat`, `list_models`, `fields`), `registry`
(`@register_provider`, `build_provider`), `policy` (`TarefaIA`, `TAREFAS`, `verificar`) e
adaptadores `gemini`, `ollama`, `openai_compat`, `mock`.

## Modelo de dados
| Tabela | Colunas relevantes |
|---|---|
| `ia_perfil_provedor` | nome, tipo, modelo, base_url, api_key_cifrada (Fernet), api_key_dica, execucao_local, temperatura, max_tokens, timeout_s, ativo |
| `ia_vinculo_tarefa` | tarefa (PK), perfil_id, perfil_fallback_id, alterado_por |
| `ia_uso` | momento, tarefa, perfil, modelo, sucesso, usou_fallback, latência, tokens, erro |

## Permissões
| Permissão | Papéis padrão | Sensível |
|---|---|:-:|
| `ia.configurar` | Administrador | ✓ |

## Interações com outros módulos
| Direção | Módulo | O quê |
|---|---|---|
| é consumido por | lgpd | tarefa `classificacao_dp` (sensível → só modelo local) |
| é consumido por | assistente | tarefa `assistente` (não sensível) |

## Jobs agendados
Nenhum.

## Regras de negócio e decisões
- Tarefa sensível só aceita perfil local; checado ao vincular, ao editar o perfil e a cada chamada.
  Exceção apenas com `GDA_IA_PERMITIR_EXTERNO_PARA_SENSIVEL=true` (decisão da CGE-GO).
- Chave de API cifrada no banco e nunca devolvida pela API.
- `ia_uso` não guarda prompt nem resposta (PBI-35).
- Novo fornecedor = um arquivo em `integrations/ai/providers/` com `@register_provider`.
- Nova tarefa = entrada em `integrations/ai/policy.py`; aparece sozinha na tela.

## Pendências
- Chave do Gemini (SECTI) e servidor para modelo local em produção.

## Histórico de alterações
| Data | Alteração | Autor |
|---|---|---|
| 30/09/2026 | Implementação: perfis, tarefas, gateway com política LGPD e tela | Claude / Victor |
| 30/09/2026 | Acesso passa a exigir `ia.configurar` do catálogo central | Claude / Victor |
