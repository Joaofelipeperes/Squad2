# Módulo `metadados` — Conformidade de metadados e formatos

| | |
|---|---|
| **Status** | Parcial: formato fechado (PBI-53) implementado; completude e sem recurso em esqueleto |
| **Responsável** | Luiza (US16) · João (US17) |
| **User stories** | US16 (PBI-48 a PBI-50), US17 (PBI-51 a PBI-53) |
| **Backend** | `backend/app/modules/metadados/` |
| **Frontend** | sem tela própria — resultados aparecem em Datasets, Organizações e Relatórios |
| **Última atualização** | 21/10/2026 |

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
- `recursos_formato_fechado(db, formatos_abertos) -> list[Recurso]` — PBI-53: recursos atuais (ainda
  no pacote) de datasets ativos, sem dicionário de dados, com formato fora da lista. **Implementado.**

`regras.py` (funções puras): `normalizar_formato(formato)` (".csv " → "CSV") e
`eh_formato_aberto(formato, formatos_abertos)` — recurso sem formato informado conta como não aberto.

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
| é consumido por | painel | `recursos_formato_fechado` e `regras.normalizar_formato` — "Recursos sem formato aberto" na tela Organizações |
| é consumido por | relatorios | indicadores e listas exportáveis |

## Jobs agendados
Nenhum.

## Regras de negócio e decisões
Decisões registradas: [ADR-0006](../adr/0006-regras-de-afericao-do-inventario.md).

- Formato é atributo do **recurso**, não do dataset (Paloma, 17/09).
- Dicionário de dados não conta como recurso de formato fechado.
- Lista de formatos abertos = parâmetro `formatos_abertos` (padrão CSV, JSON, XML, ODS, GeoJSON,
  TXT), editável pela GEDA. Recurso sem formato informado conta como fechado. Só recursos atuais de
  datasets ativos entram.

## Pendências
- Lista oficial de metadados obrigatórios (GEDA) — hoje provisória em `parametros`.
- Validar com a GEDA se ZIP (605 recursos no portal, provavelmente com CSV dentro) e XLSX (105)
  contam como formato aberto; hoje contam como fechados.

## Histórico de alterações
| Data | Alteração | Autor |
|---|---|---|
| 30/09/2026 | Esqueleto: contratos e permissão | Victor |
| 18/10/2026 | Formato fechado (PBI-53): `regras.eh_formato_aberto`/`normalizar_formato` e `service.recursos_formato_fechado`, usados pela tela Organizações | Humberto |
| 21/10/2026 | Chave primária própria no inventário (ADR-0018): `recursos_formato_fechado` junta `Recurso` × `Dataset` por `Dataset.id`; sem mudança de comportamento | Victor |
