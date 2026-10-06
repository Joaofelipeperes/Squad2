# Módulo `parametros` — Parâmetros de monitoramento

| | |
|---|---|
| **Status** | Implementado |
| **Responsável** | — (base comum) |
| **User stories** | US8 (PBI-22), US11 (PBI-31, PBI-86), US16 (PBI-48), US17 (PBI-52) |
| **Backend** | `backend/app/modules/parametros/` |
| **Frontend** | `frontend/src/modules/parametros/` |
| **Última atualização** | 30/09/2026 |

## Propósito
Concentra os valores de negócio que a GEDA precisa ajustar sem depender do time (janelas, listas,
limites), com valor padrão no código.

## Telas
| Tela | Rota | Permissão para ver | Ações na tela (permissão) |
|---|---|---|---|
| Parâmetros de monitoramento | `/admin/parametros` | `parametros.acessar` | Editar valores (`parametros.editar`) |

## API
| Método | Rota (`/api/v1/parametros`) | Permissão | Descrição |
|---|---|---|---|
| GET | `` | `parametros.acessar` | Lista parâmetros com valor atual e padrão |
| PUT | `/{chave}` | `parametros.editar` | Altera o valor (tipo deve ser igual ao do padrão) |

## Serviços e métodos
- `obter(db, chave)` em `router.py` — **uso pelos outros módulos**; devolve o valor salvo ou o padrão.
- `catalogo.CATALOGO` — definição de cada parâmetro (rótulo, descrição, padrão, PBI).

| Chave | Padrão | Usado por |
|---|---|---|
| `janela_alerta_prazo_dias` | 30 | pda |
| `metadados_obrigatorios` | notes, license_id, author, author_email, periodicidade (provisório) | metadados |
| `tipos_dado_pessoal` | cpf, email, telefone, endereco, data_nascimento, nome (provisório) | lgpd |
| `formatos_abertos` | CSV, JSON, XML, ODS, GEOJSON, TXT | metadados |
| `confianca_minima_lgpd` | 60 | lgpd |

## Modelo de dados
| Tabela | Colunas relevantes |
|---|---|
| `parametro` | chave (PK), valor (JSON), alterado_por |

## Permissões
| Permissão | Papéis padrão |
|---|---|
| `parametros.acessar` | Administrador, Gerência GEDA, Equipe GEDA |
| `parametros.editar` | Administrador, Gerência GEDA |

## Interações com outros módulos
| Direção | Módulo | O quê |
|---|---|---|
| é consumido por | pda, lgpd, metadados | `obter(db, chave)` |

## Jobs agendados
Nenhum.

## Regras de negócio e decisões
- Parâmetro novo = entrada em `catalogo.py`; aparece sozinho na tela.

## Pendências
- Valores oficiais da GEDA para os parâmetros provisórios.
- Mover `obter` para `service.py` quando o módulo crescer.

## Histórico de alterações
| Data | Alteração | Autor |
|---|---|---|
| 30/09/2026 | Implementação inicial | Claude / Victor |
| 30/09/2026 | Separação entre ver (`parametros.acessar`) e editar (`parametros.editar`) | Claude / Victor |
