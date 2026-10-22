# Módulo `painel` — Visão geral e organizações

| | |
|---|---|
| **Status** | Parcial: tela Organizações implementada (com indicadores pendentes); Dashboard em esqueleto |
| **Responsável** | João (Dashboard) · Humberto (Organizações, PBI-84) |
| **User stories** | US19 (PBI-56 a PBI-59, PBI-75, PBI-76, PBI-84), US27 (exibição do ranking) |
| **Backend** | `backend/app/modules/painel/` |
| **Frontend** | `frontend/src/modules/dashboard/` · `frontend/src/modules/organizacoes/` |
| **Última atualização** | 21/10/2026 |

## Propósito
Consolida os indicadores dos eixos numa visão gerencial por órgão, usada pela GEDA e pela
Superintendência (inclusive para o Prêmio de Transparência).

## Telas
| Tela | Rota | Permissão para ver | Ações na tela (permissão) |
|---|---|---|---|
| Dashboard (Visão Geral) | `/` | `painel.acessar` | KPIs, gráficos, alertas prioritários; "Atualizar dados" (`inventario.coletar`) |
| Organizações | `/organizacoes` | `painel.acessar` | Detalhe do órgão (clique ou Enter na linha); **Ver bases no PDA** abre `/pda?orgao=<chave>` (`pda.acessar`) |

Referência visual: `#screen-dashboard` e `#screen-organizations`. Ressalvas de 17/09: gráficos de
evolução temporal abaixo dos cards (PBI-75).

**Organizações** (`OrganizacoesPage.tsx`, `OrganizacaoDetalheModal.tsx`):
- **Tabela**: Órgão (título da organização + siglas usadas no PDA; sigla do PDA sem organização no
  portal vira linha própria com badge "sem organização no portal") | Bases previstas (PDA vigente) |
  Bases publicadas ("N de M vinculada(s)" ou **aguardando vínculo** quando o órgão não tem base
  vinculada) | **Em atraso** (só entre as bases **vinculadas**: prazo vencido e dataset fora do
  portal; **aguardando vínculo** quando o órgão não tem base vinculada, porque sem vínculo não há
  como saber se a base já foi publicada; com vínculo parcial, "N de M vinculada(s)") | Atualização,
  Riscos LGPD e Índice de atenção (**a definir**). Os pendentes aparecem como badge cinza, nunca 0.
- **Filtros** (na própria tela, sobre a lista já carregada): busca por nome ou sigla (sem
  diferenciar maiúsculas e acentos); **Em atraso** (com bases em atraso, sem atraso entre as
  vinculadas, com bases próximas do prazo, aguardando vínculo); **Bases no PDA** (com/sem bases
  previstas); **Organização no portal** (com/sem). "Limpar filtros" volta a mostrar todos; o
  contador passa a "N de M órgão(s)".
- **Detalhe**: cartões do protótipo (previstas; publicadas e não publicadas, aguardando vínculo;
  atualizações atrasadas e possíveis dados pessoais, a definir; **recursos sem formato aberto** com
  o total de recursos e datasets), bases em atraso (mesma regra da tabela) e próximas do prazo,
  formatos fechados por tipo e a lista de formatos abertos em vigor; "Últimas alterações" pendente
  da rastreabilidade.

## API
| Método | Rota (`/api/v1/painel`) | Permissão | Descrição |
|---|---|---|---|
| GET | `/organizacoes` | `painel.acessar` | `OrganizacoesOut`: plano vigente (`{id, nome}` ou null), hoje, `formatos_abertos` e uma `OrganizacaoOut` por órgão (escopo de órgão do usuário) |

`OrganizacaoOut`: chave (organizacao_id ou `sigla:<SIGLA>`), organizacao_id, nome, siglas,
datasets_no_portal, recursos_validos, recursos_formato_fechado, formatos_fechados `{formato: n}`
("" = sem formato), bases_previstas, bases_vinculadas, bases_publicadas, `bases_em_atraso` (só
entre as vinculadas; null sem nenhuma vinculada), bases_proximas_do_prazo e os pendentes
`atualizacao_pct`, `riscos_lgpd`, `indice_atencao` (null).

Ainda previstos: `GET /api/v1/painel/kpis` e `/alertas` (`painel.acessar`).

## Serviços e métodos
- `kpis(db) -> dict` — PBI-56.
- `indice_atencao_por_orgao(db)` — PBI-76/84, critério documentado e auditável (PBI-59).
- `organizacoes(db, user) -> OrganizacoesOut` — US19: inventário (datasets ativos, recursos atuais
  sem dicionário, formatos fechados via `metadados.recursos_formato_fechado` e o parâmetro
  `formatos_abertos`) + `pda.bases_do_plano` do PDA vigente, agrupado por `orgao_chave`. Testes em
  `tests/test_painel_organizacoes.py`.

## Modelo de dados
Sem tabelas próprias. Séries temporais podem exigir uma tabela de indicadores por coleta (a decidir).

## Permissões
| Permissão | Papéis padrão |
|---|---|
| `painel.acessar` | Administrador, Gerência GEDA, Equipe GEDA, Superintendência |

## Interações com outros módulos
| Direção | Módulo | O quê |
|---|---|---|
| consome | inventario | contagens e última coleta; `Organizacao`, `Dataset`, `Recurso` e `condicao_recurso_atual()` (Organizações) |
| consome | pda | `plano_vigente(db)` + `bases_do_plano(db, plano.id, user)`: bases previstas, vinculadas, publicadas e metas por órgão, **sempre do PDA vigente** (Organizações); `regras` (situações, `chave_sigla`); `hoje_local()` |
| consome | atualizacoes | desatualizados por órgão |
| consome | lgpd | indicador de risco e ranking de exposição (US27) |
| consome | metadados | completude média; `recursos_formato_fechado(db, formatos_abertos)` e `regras.normalizar_formato` (Organizações) |
| consome | parametros | `formatos_abertos` |

## Jobs agendados
Nenhum.

## Regras de negócio e decisões
Decisões registradas: [ADR-0007](../adr/0007-prototipo-v1-referencia-das-telas.md).

- Indicadores calculados somente a partir da última coleta, com data visível (PBI-58).
- Bloco de alertas LGPD só aparece se o usuário também tiver `lgpd.acessar` (usar `<Pode>`).

## Pendências
- Fórmula do índice de atenção (validar com a GEDA).
- Organizações: "Bases publicadas" depende do vínculo base × dataset (hoje 0 de 409 no PDA vigente);
  "Atualização" da regra por periodicidade (`atualizacoes`, PBI-27/28); "Riscos LGPD" do módulo
  `lgpd`; "Últimas alterações" da `rastreabilidade`. Validar com a GEDA se ZIP (605 recursos no
  portal) e XLSX (105) devem contar como formato aberto — hoje contam como fechados.

## Histórico de alterações
| Data | Alteração | Autor |
|---|---|---|
| 30/09/2026 | Esqueleto: contratos, duas telas e permissão | Victor |
| 07/10/2026 | Interações: consumo do pda via `plano_vigente`/`bases_do_plano` (sempre o PDA vigente) | Humberto |
| 18/10/2026 | Tela Organizações (US19): `GET /painel/organizacoes` e `service.organizacoes`; tabela e detalhe do protótipo com bases do PDA vigente, recursos em formato fechado (parâmetro `formatos_abertos`) e indicadores pendentes como "aguardando vínculo" / "a definir" | Humberto |
| 18/10/2026 | Organizações: coluna "Em atraso" (nome do protótipo) conta só bases vinculadas; sem vínculo mostra "aguardando vínculo" em vez de contar toda base com prazo vencido (`bases_em_atraso`, `bases_proximas_do_prazo`) | Humberto |
| 21/10/2026 | Organizações: filtros na tela (busca por nome/sigla, Em atraso, Bases no PDA, Organização no portal), sem mudança na API | Victor |
