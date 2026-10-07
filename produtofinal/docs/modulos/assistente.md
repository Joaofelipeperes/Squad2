# Módulo `assistente` — Assistente GEDA

| | |
|---|---|
| **Status** | Implementado (contexto básico; enriquecer com os eixos) |
| **Responsável** | Luiza |
| **User stories** | US28 (PBI-96, PBI-97) |
| **Backend** | `backend/app/modules/assistente/` |
| **Frontend** | `frontend/src/modules/assistente/` (widget global) |
| **Última atualização** | 30/09/2026 |

## Propósito
Responde em linguagem natural perguntas sobre órgãos, bases, prazos e alertas, com base na última coleta.

## Telas
| Tela | Rota | Permissão para ver | Ações na tela (permissão) |
|---|---|---|---|
| Botão flutuante + painel de chat | todas as telas | `assistente.usar` | Perguntar; sugestões rápidas |

Referência visual: `#chat-fab` e `#chat-panel` do Protótipo V1. É um `AppWidget` (fora das rotas).

## API
| Método | Rota (`/api/v1/assistente`) | Permissão | Descrição |
|---|---|---|---|
| POST | `/perguntar` | `assistente.usar` | `{pergunta}` → `{resposta, modelo}`; 503 sem modelo vinculado, 502 se o provedor falhar |

## Serviços e métodos
- `montar_contexto(db, pergunta, user) -> str` — fatos determinísticos da última coleta; respeita o
  escopo de órgão (usuário restrito não recebe totais estaduais nem dados de outros órgãos).
- `perguntar(db, pergunta, user)` — envia sistema + contexto + pergunta à tarefa `assistente`
  pelo `AIGateway`.

## Modelo de dados
Sem tabelas próprias. Uso registrado em `ia_uso` pelo gateway, sem conteúdo.

## Permissões
| Permissão | Papéis padrão |
|---|---|
| `assistente.usar` | Administrador, Gerência GEDA, Equipe GEDA, Superintendência |

## Interações com outros módulos
| Direção | Módulo | O quê |
|---|---|---|
| consome | ia | `AIGateway.chat(TarefaIA.ASSISTENTE, ...)` |
| consome | inventario | `Coleta`, `Organizacao`, `Dataset`, `Recurso` |
| consome | acesso | `filtrar_por_orgao` |
| consumirá | pda, atualizacoes, lgpd | situação de prazos, atrasos e **contagem** de achados |

## Jobs agendados
Nenhum.

## Regras de negócio e decisões
Decisões registradas: [ADR-0002](../adr/0002-camada-ia-plugavel.md) · [ADR-0011](../adr/0011-assistente-sem-banco-vetorial.md).

- Sem banco vetorial: o backend monta os fatos e o modelo só redige (risco de infraestrutura do PGP).
- O prompt proíbe inventar números; sem dado no contexto, indica a tela onde conferir.
- Nunca recebe conteúdo de achados LGPD — por isso pode usar modelo comercial.

## Pendências
- Chave do Gemini da SECTI (limite 19/10); sem ela, vincular um modelo local na tela de IA.
- Enriquecer o contexto com os dados dos módulos dos eixos à medida que forem implementados.

## Histórico de alterações
| Data | Alteração | Autor |
|---|---|---|
| 30/09/2026 | Implementação inicial: contexto da coleta e widget de chat | Claude / Victor |
| 30/09/2026 | Permissão `assistente.usar` e escopo de órgão no contexto | Claude / Victor |
