# Módulo `rastreabilidade` — Linha do tempo de mudanças

| | |
|---|---|
| **Status** | Esqueleto (contrato definido; insumo já gravado pelo inventário) |
| **Responsável** | João (US29, diff) · Humberto (tela) |
| **User stories** | US14 (PBI-43 a PBI-45, PBI-85), US29 (PBI-69, PBI-70) |
| **Backend** | `backend/app/modules/rastreabilidade/` |
| **Frontend** | `frontend/src/modules/rastreabilidade/` |
| **Última atualização** | 30/09/2026 |

## Propósito
Registra inclusões, alterações, privações e exclusões de datasets e recursos — hoje uma exclusão no
portal não deixa rastro para a GEDA.

## Telas
| Tela | Rota | Permissão para ver | Ações na tela (permissão) |
|---|---|---|---|
| Rastreabilidade | `/rastreabilidade` | `rastreabilidade.acessar` | Filtros por tipo de alteração e órgão |

Referência visual: `#screen-traceability` (linha do tempo em linguagem humana, PBI-85).

## API
Nenhum endpoint ainda. Previsto: `GET /api/v1/rastreabilidade/eventos` (`rastreabilidade.acessar`).

## Serviços e métodos
- `diff_coletas(db, coleta_anterior_id, coleta_atual_id)` — compara `dataset_snapshot` das duas
  coletas (mesmo `dataset_id`, `hash_conteudo` diferente = alteração; ausente na atual = exclusão
  ou privação; novo = inclusão; `last_modified` de recurso mudou = recurso atualizado). PBI-43.

## Modelo de dados
Lê `coleta` e `dataset_snapshot`. Tabela de eventos a definir na implementação.

## Permissões
| Permissão | Papéis padrão |
|---|---|
| `rastreabilidade.acessar` | Administrador, Gerência GEDA, Equipe GEDA |

## Interações com outros módulos
| Direção | Módulo | O quê |
|---|---|---|
| consome | inventario | `Coleta`, `DatasetSnapshot` |
| consome | pda | destacar mudança em base do PDA já cumprida (PBI-45) |
| é consumido por | relatorios | mudanças do período por órgão (PBI-44) |

## Jobs agendados
Previsto: gerar eventos ao fim de cada coleta.

## Regras de negócio e decisões
- Fonte técnica decidida na US29 (PBI-70): extensão × diff entre coletas × activity stream. O
  diff já é viável com o que a coleta grava; o activity stream exige acesso interno à rede do Estado.

## Pendências
- Registro da decisão go/no-go da US29.

## Histórico de alterações
| Data | Alteração | Autor |
|---|---|---|
| 30/09/2026 | Esqueleto: contrato `diff_coletas` e permissão | Claude / Victor |
