# Módulo `metadados` — Conformidade de metadados e formatos

| | |
|---|---|
| **Status** | Esqueleto (contratos definidos) |
| **Responsável** | Luiza (US16) · João (US17) |
| **User stories** | US16 (PBI-48 a PBI-50), US17 (PBI-51 a PBI-53) |
| **Backend** | `backend/app/modules/metadados/` |
| **Frontend** | sem tela própria — resultados aparecem em Datasets, Organizações e Relatórios |
| **Última atualização** | 30/09/2026 |

## Propósito
Mede o preenchimento dos metadados obrigatórios e identifica datasets sem recurso e recursos em
formato não aberto — critérios que o CKAN não valida.

## Telas
Sem tela própria. Fornece dados para:
| Tela | Módulo da tela | O que mostra |
|---|---|---|
| Datasets | inventario | completude e formato de cada recurso (PBI-83) |
| Organizações / Dashboard | painel | completude média por órgão |
| Relatórios | relatorios | metadados não preenchidos por órgão (PBI-50); formatos fechados (PBI-53) |

## API
Nenhum endpoint ainda. Previsto: `GET /api/v1/metadados/completude` e `/formatos-fechados`
(`metadados.acessar`).

## Serviços e métodos
Contratos em `service.py`:
- `completude(dataset, obrigatorios) -> float` — PBI-49.
- `datasets_sem_recurso(db)` — PBI-51.
- `recursos_formato_fechado(db, formatos_abertos)` — PBI-53, excluindo dicionário de dados.

## Modelo de dados
Sem tabelas próprias: lê `dataset` e `recurso`.

## Permissões
| Permissão | Papéis padrão |
|---|---|
| `metadados.acessar` | Administrador, Gerência GEDA, Equipe GEDA |

## Interações com outros módulos
| Direção | Módulo | O quê |
|---|---|---|
| consome | inventario | `Dataset` (campos e extras), `Recurso.formato` |
| consome | parametros | `metadados_obrigatorios`, `formatos_abertos` |
| é consumido por | painel, relatorios | indicadores e listas exportáveis |

## Jobs agendados
Nenhum.

## Regras de negócio e decisões
- Formato é atributo do **recurso**, não do dataset (Paloma, 17/09).
- Dicionário de dados não conta como recurso de formato fechado.

## Pendências
- Lista oficial de metadados obrigatórios (GEDA) — hoje provisória em `parametros`.

## Histórico de alterações
| Data | Alteração | Autor |
|---|---|---|
| 30/09/2026 | Esqueleto: contratos e permissão | Claude / Victor |
