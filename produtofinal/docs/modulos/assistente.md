# Módulo `assistente` — Assistente GEDA

| | |
|---|---|
| **Status** | Implementado (contexto com órgão, dataset/arquivo, PDA vigente e contagem LGPD) |
| **Responsável** | Luiza |
| **User stories** | US28 (PBI-96, PBI-97) |
| **Backend** | `backend/app/modules/assistente/` |
| **Frontend** | `frontend/src/modules/assistente/` (widget global) |
| **Última atualização** | 27/10/2026 |

## Propósito
Responde em linguagem natural perguntas rápidas sobre órgãos, datasets, arquivos (recursos), prazos do
PDA e alertas de dados pessoais, com base na última coleta. Segue o chatbot do Protótipo V1, agora com
os dados reais e um modelo de IA redigindo a resposta.

## Telas
| Tela | Rota | Permissão para ver | Ações na tela (permissão) |
|---|---|---|---|
| Botão flutuante + painel de chat | todas as telas | `assistente.usar` | Perguntar; sugestões rápidas (as 5 do protótipo); resposta com negrito/listas e linha "Consultado: …" com as fontes |

Referência visual: `#chat-fab` e `#chat-panel` do Protótipo V1. É um `AppWidget` (fora das rotas).

## API
| Método | Rota (`/api/v1/assistente`) | Permissão | Descrição |
|---|---|---|---|
| POST | `/perguntar` | `assistente.usar` | `{pergunta, historico?: [{papel: user\|assistant, texto}]}` → `{resposta, modelo, fontes: [{tipo, id, titulo}]}`; 503 sem modelo vinculado, 502 se o provedor falhar |

## Serviços e métodos
`dao.py` — `AssistenteDao(Dao)` (ADR-0019): `organizacoes_visiveis`, `datasets_visiveis` (com os
recursos em lote) e `achados_por_dataset` (só contagens por tipo e status), sempre no escopo de
órgão. Só leitura; registros excluídos não contam.

`service.py`
- `contexto_da_pergunta(db, pergunta, user, pergunta_anterior=None) -> Contexto(texto, fontes)` —
  fatos determinísticos, sempre no escopo de órgão do usuário:
  - cabeçalho: data da última coleta, totais (só sem restrição de órgão), resumo do PDA vigente;
  - órgão citado (título, `name` ou sigla): datasets por situação no portal, bases do PDA vigente
    por situação, bases em atraso/prazo vencido, próximos prazos, contagem de achados LGPD;
  - dataset citado (título, `name` ou **nome de arquivo**): ficha com recursos, formatos, última
    atualização real, periodicidade declarada, descrição (e-mails mascarados), vínculo com o PDA
    vigente e contagem de achados LGPD por tipo; sem citação exata, até 5 datasets parecidos;
  - sem órgão nem dataset: listas por intenção (atraso, prazo, não publicado, sem recurso, LGPD,
    atualização mais antiga, contagens);
  - continuação curta ("e o prazo dela?") sem entidade própria usa a pergunta anterior.
- `montar_contexto(db, pergunta, user) -> str` — compatibilidade: só o texto.
- `perguntar(db, pergunta, user, historico) -> (resposta, perfil, usou_fallback, fontes)` — envia
  sistema + até 6 mensagens anteriores + contexto + pergunta à tarefa `assistente` pelo `AIGateway`.

`regras.py` (funções puras): `normalizar`, `termos`, `intencoes`, `contem_frase`, `sigla_citada`,
`pontuar`/`melhores` (pontuação de um dataset para a pergunta), `cortar`.

## Modelo de dados
Sem tabelas próprias. A conversa fica só no navegador (nada é gravado); uso registrado em `ia_uso`
pelo gateway, sem conteúdo.

## Permissões
| Permissão | Papéis padrão |
|---|---|
| `assistente.usar` | Administrador, Gerência GEDA, Equipe GEDA, Superintendência |

## Interações com outros módulos
| Direção | Módulo | O quê |
|---|---|---|
| consome | ia | `AIGateway.chat(TarefaIA.ASSISTENTE, ...)` |
| consome | inventario | `Coleta`, `Organizacao`, `Dataset`, `Recurso` (pelo `AssistenteDao`); `ultima_coleta`, `recursos_atuais`; `regras.situacao_no_portal` |
| consome | acesso | `filtrar_por_orgao` |
| consome | pda | `plano_vigente(db)` + `bases_do_plano(db, plano.id, user)`: situação e prazos **sempre do PDA vigente**, no escopo de órgão |
| consome | atualizacoes | `regras.ultima_atualizacao_real` (data real pelos recursos) |
| consome | lgpd | `Achado`: só **contagem** por dataset, tipo e status (nunca coluna, linha ou valor) |
| consumirá | atualizacoes | situação por periodicidade quando `situacao_periodicidade` for implementada |

## Jobs agendados
Nenhum.

## Regras de negócio e decisões
Decisões registradas: [ADR-0002](../adr/0002-camada-ia-plugavel.md) · [ADR-0011](../adr/0011-assistente-sem-banco-vetorial.md).

Decisão em análise: [ADR-0020](../adr/0020-claude-haiku-no-assistente.md) (Claude Haiku como modelo principal).

- Sem banco vetorial: o backend monta os fatos e o modelo só redige (risco de infraestrutura do PGP).
- O prompt proíbe inventar números; sem dado no contexto, indica a tela onde conferir.
- O modelo não lê o conteúdo dos arquivos, só os metadados; o prompt manda não deduzir o conteúdo.
- Nunca recebe conteúdo de achados LGPD, autor nem e-mail de contato do dataset — por isso pode
  usar modelo comercial. Textos do portal entram como dados (o prompt manda ignorar ordens neles).
- Contexto curto (fichas de até 3 datasets, listas de até 10 itens) para resposta rápida e barata.

## Pendências
- Escolha do modelo (ADR-0020): Claude Haiku × Gemini da SECTI × modelo local.
- Situação de atualização por periodicidade (quando `atualizacoes.situacao_periodicidade` existir).
- Validar com perguntas reais da GEDA (ADR-0011) e medir custo por pergunta em `ia_uso`.

## Histórico de alterações
| Data | Alteração | Autor |
|---|---|---|
| 30/09/2026 | Implementação inicial: contexto da coleta e widget de chat | Victor |
| 30/09/2026 | Permissão `assistente.usar` e escopo de órgão no contexto | Victor |
| 07/10/2026 | Interações: consumo previsto do pda via `plano_vigente`/`bases_do_plano` (sempre o PDA vigente) | Humberto |
| 08/10/2026 | Correção: o efeito de rolagem do chat devolvia a Promise de `scrollIntoView` (Chrome atual) e o React a chamava ao desmontar — sair ou sessão expirada deixava a tela em branco; contagem de recursos por órgão no contexto passa a usar só datasets ativos, recursos ainda no portal e sem dicionário de dados | Humberto |
| 21/10/2026 | Chave primária própria no inventário (ADR-0018): recorte por órgão filtra e junta por `Organizacao.id`; sem mudança de comportamento | Victor |
| 22/10/2026 | Banco só pelo `AssistenteDao` (ADR-0019); contagens do contexto sem os registros excluídos | Victor |
| 23/10/2026 | Contexto por dataset/arquivo citado, listas por intenção (como no Protótipo V1), PDA vigente e contagem LGPD; histórico curto da conversa; resposta com fontes; widget com sugestões, indicador de digitação e formatação do protótipo | Squad 2 |
| 27/10/2026 | Merge com `desenvolvimento`: contexto lido pelo `AssistenteDao` (`datasets_visiveis`, `achados_por_dataset`; saem `datasets_ativos` e `recursos_validos`); chaves internas e fontes pelo `id` próprio (ADR-0018), ficha com o `id_ckan`; data de criação do recurso em `created_ckan` | Luiza |
