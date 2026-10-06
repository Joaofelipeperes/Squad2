# Módulo `envio` — Área do órgão publicador

| | |
|---|---|
| **Status** | **Não comprometido** — fora do escopo do PGP v2 e do Backlog v2 |
| **Responsável** | a definir |
| **User stories** | nenhuma (requer nova US) |
| **Backend** | `backend/app/modules/envio/` |
| **Frontend** | `frontend/src/modules/envio/` |
| **Última atualização** | 30/09/2026 |

## Propósito
Permitir que servidores dos órgãos estaduais acessem a solução apenas para consultar os datasets
do próprio órgão e enviar datasets/recursos. Existe hoje para materializar o papel *Órgão
publicador* e o escopo de órgão no controle de acesso.

> **Atenção ao escopo.** O PGP v2 define que a única escrita no CKAN é a publicação de recurso
> anonimizado (US26) e deixa fora do escopo os pipelines de ingestão dos órgãos (SECTI). Implementar
> o envio exige decisão da CGE-GO, alinhamento técnico com a SECTI (credenciais, fluxo de aprovação)
> e registro como alteração de escopo (nova US no backlog e revisão do PGP).

## Telas
| Tela | Rota | Permissão para ver | Ações na tela (permissão) |
|---|---|---|---|
| Envio de dados do órgão | `/envio` | `envio.acessar` | Enviar recurso (`envio.enviar_recurso`) — a implementar |

Hoje a tela mostra apenas o órgão do usuário e um aviso de funcionalidade em definição.

## API
Nenhum endpoint. Toda rota futura deve aplicar o escopo:
```python
user = Depends(require(P.ENVIO_ACESSAR))
stmt = filtrar_por_orgao(select(Dataset), Dataset.organizacao_id, user)
exigir_mesmo_orgao(user, dataset.organizacao_id)   # antes de qualquer ação sobre um dataset
```

## Serviços e métodos
Contratos em `service.py`: `datasets_do_orgao(db, user)`, `enviar_recurso(db, user, dataset_id, arquivo)`.

## Modelo de dados
Nenhum.

## Permissões
| Permissão | Papéis padrão | Sensível |
|---|---|:-:|
| `envio.acessar` | Administrador, Órgão publicador | |
| `envio.enviar_recurso` | Administrador, Órgão publicador | ✓ |

O papel Órgão publicador **exige órgão** vinculado ao usuário.

## Interações com outros módulos
| Direção | Módulo | O quê |
|---|---|---|
| consome | acesso | escopo de órgão |
| consome | inventario | `Dataset`, `Organizacao` |
| consumiria | CKAN (integração) | escrita — hoje restrita à US26 |

## Jobs agendados
Nenhum.

## Regras de negócio e decisões
- Usuário de órgão nunca vê dados de outro órgão (`filtrar_por_orgao`, `exigir_mesmo_orgao`).

## Pendências
- Decisão de escopo (Paloma / Júnior) e viabilidade técnica (Wagner, SECTI).

## Histórico de alterações
| Data | Alteração | Autor |
|---|---|---|
| 30/09/2026 | Criado como esqueleto não comprometido para o papel Órgão publicador | Claude / Victor |
