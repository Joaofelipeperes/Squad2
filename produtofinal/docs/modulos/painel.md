# Módulo `painel` — Visão geral e organizações

| | |
|---|---|
| **Status** | Parcial: Dashboard (Visão Geral) e Organizações implementados, com indicadores pendentes (atualização por periodicidade, LGPD, índice de atenção) |
| **Responsável** | João (Dashboard) · Humberto (Organizações, PBI-84) |
| **User stories** | US19 (PBI-56 a PBI-59, PBI-75, PBI-76, PBI-84), US27 (exibição do ranking) |
| **Backend** | `backend/app/modules/painel/` |
| **Frontend** | `frontend/src/modules/dashboard/` · `frontend/src/modules/organizacoes/` |
| **Última atualização** | 28/10/2026 |

## Propósito
Consolida os indicadores dos eixos numa visão gerencial por órgão, usada pela GEDA e pela
Superintendência (inclusive para o Prêmio de Transparência).

## Telas
| Tela | Rota | Permissão para ver | Ações na tela (permissão) |
|---|---|---|---|
| Dashboard (Visão Geral) | `/` | `painel.acessar` | Cartões, gráficos e alertas prioritários; **Ver monitoramento completo** e **Ver** de cada alerta levam ao PDA (`/pda?orgao=<chave>`) ou a Datasets; "Atualizar dados" (`inventario.coletar`) |
| Organizações | `/organizacoes` | `painel.acessar` | Detalhe do órgão (clique ou Enter na linha); **Ver bases no PDA** abre `/pda?orgao=<chave>` (`pda.acessar`) |

Referência visual: `#screen-dashboard` e `#screen-organizations`. Ressalvas de 17/09: gráficos de
evolução temporal abaixo dos cards (PBI-75).

**Dashboard** (`DashboardPage.tsx`, `BarrasHorizontais.tsx`):
- Faixa informativa do protótipo com a **data da última coleta** (PBI-58).
- **8 cartões**: Órgãos monitorados (pé: órgãos com bases no PDA vigente); Bases previstas no PDA
  (pé: nome do PDA vigente); Datasets publicados (ativos; pé: quantos saíram do portal); Recursos
  monitorados (atuais, sem dicionário); **Bases atrasadas** só entre as vinculadas ("—" e
  "aguardando vínculo" sem nenhuma vinculada); **Atualizações em atraso** (bases vinculadas
  "Atrasado" pela periodicidade do PDA, ADR-0023); Datasets sem recurso (PBI-51). Possíveis dados
  pessoais aparece como "—", com o rodapé em branco (nunca 0).
- **Cumprimento do PDA por situação**: barras horizontais com as 7 situações do PDA vigente (cor de
  status + rótulo; dica com quantidade e % ao passar o mouse ou com o teclado) e a nota de que
  "Prazo vencido" ainda não é atraso confirmado.
- **Status das atualizações** (rosca do protótipo, `Rosca.tsx`): bases **vinculadas** do PDA vigente
  por situação de atualização (ADR-0023) — Atualizado, Próximo do vencimento, Atrasado, Sem
  periodicidade definida (hachurado) e Sem informação; legenda fixa com ícone, rótulo, quantidade e
  %; centro com o total ou a fatia em foco. As bases sem vínculo ficam numa nota abaixo.
- **Alertas prioritários** em abas **Todos / PDA / Atualização / Inventário** com o total de cada
  tipo; cada aba mostra até 10 do tipo e "Todos" mostra até 4 de cada tipo, para um tipo numeroso
  não esconder os outros. Ordem de prioridade: base em atraso confirmado → **atualização
  atrasada** (tipo "Atualização", prazo = vencimento pela periodicidade) → base vinculada sem
  recurso → base próxima do prazo → dataset sem recurso (inventário). "Prazo vencido" sem vínculo
  não vira alerta.
- **Fluxo de governança monitorado** (faixa estática do protótipo).
- Gráficos em HTML/CSS, sem biblioteca de gráficos (nenhuma dependência nova).

**Organizações** (`OrganizacoesPage.tsx`, `OrganizacaoDetalheModal.tsx`):
- **Tabela**: Órgão (título da organização + siglas usadas no PDA; sigla do PDA sem organização no
  portal vira linha própria com badge "sem organização no portal") | Bases previstas (PDA vigente) |
  Bases publicadas ("N de M vinculada(s)" ou **aguardando vínculo** quando o órgão não tem base
  vinculada) | **Em atraso** (só entre as bases **vinculadas**: prazo vencido e dataset fora do
  portal; **aguardando vínculo** quando o órgão não tem base vinculada, porque sem vínculo não há
  como saber se a base já foi publicada; com vínculo parcial, "N de M vinculada(s)") |
  **Atualização** (% das bases vinculadas com prazo definido que estão dentro da periodicidade do PDA
  — Atualizado ou Próximo do vencimento, ADR-0023; badge verde sem atrasadas, âmbar ≥ 50%, vermelho
  abaixo; "aguardando vínculo" sem base vinculada; "sem prazo definido" quando só há Eventual,
  Estática ou bases sem data) | Riscos LGPD e Índice de atenção (**a definir**). Os pendentes
  aparecem como badge cinza, nunca 0.
- **Filtros** (na própria tela, sobre a lista já carregada): busca por nome ou sigla (sem
  diferenciar maiúsculas e acentos); **Em atraso** (com bases em atraso, sem atraso entre as
  vinculadas, com bases próximas do prazo, aguardando vínculo); **Bases no PDA** (com/sem bases
  previstas); **Organização no portal** (com/sem). "Limpar filtros" volta a mostrar todos; o
  contador passa a "N de M órgão(s)".
- **Detalhe**: cartões do protótipo (previstas; publicadas e não publicadas, aguardando vínculo;
  **atualizações atrasadas** (de N bases com prazo, com o % em dia); possíveis dados pessoais, a
  definir; **recursos sem formato aberto** com
  o total de recursos e datasets), bases em atraso (mesma regra da tabela) e próximas do prazo,
  formatos fechados por tipo e a lista de formatos abertos em vigor; "Últimas alterações" pendente
  da rastreabilidade.

## API
| Método | Rota (`/api/v1/painel`) | Permissão | Descrição |
|---|---|---|---|
| GET | `/visao-geral` | `painel.acessar` | `VisaoGeralOut` (escopo de órgão do usuário): plano vigente, hoje, `ultima_coleta`, `kpis` (`KpisOut`), `situacoes_pda` e `situacoes_atualizacao` (`[{rotulo, total}]`), `atualizacao_estimada`, `alertas` (`[{tipo, orgao, item, situacao, prazo, destino}]`, até 10 **por tipo**), `total_alertas` e `alertas_por_tipo` |
| GET | `/organizacoes` | `painel.acessar` | `OrganizacoesOut`: plano vigente (`{id, nome}` ou null), hoje, `formatos_abertos` e uma `OrganizacaoOut` por órgão (escopo de órgão do usuário) |

`OrganizacaoOut`: chave (`id` da organização em texto ou `sigla:<SIGLA>`), organizacao_id (inteiro), nome, siglas,
datasets_no_portal, recursos_validos, recursos_formato_fechado, formatos_fechados `{formato: n}`
("" = sem formato), bases_previstas, bases_vinculadas, bases_publicadas, `bases_em_atraso` (só
entre as vinculadas; null sem nenhuma vinculada), bases_proximas_do_prazo, `atualizacao_pct` (% em
dia entre as vinculadas com prazo; null sem nenhuma), `atualizacoes_atrasadas` (null idem),
`atualizacoes_avaliadas` e os pendentes `riscos_lgpd`, `indice_atencao` (null).

`KpisOut`: orgaos_monitorados, orgaos_no_pda, bases_previstas, bases_vinculadas, bases_publicadas,
`bases_em_atraso` (só entre as vinculadas; null sem nenhuma vinculada), bases_prazo_vencido,
datasets_publicados, datasets_fora_do_portal, recursos_monitorados, datasets_sem_recurso e os
`atualizacoes_em_atraso` (entre as vinculadas; null sem nenhuma) e o pendente
`possiveis_dados_pessoais` (null).

## Serviços e métodos
`dao.py` — `PainelDao(Dao)` (ADR-0019): `organizacoes_visiveis`, `datasets_ativos_por_orgao`, `recursos_validos_por_orgao`, `orgao_de_cada_dataset`, `datasets_por_situacao(user)` e `recursos_validos(user)` (Dashboard). Só leitura; registros excluídos não contam.

- `kpis(db, user, bases, *, orgaos, datasets, recursos, sem_recurso) -> KpisOut` — PBI-56.
- `visao_geral(db, user) -> VisaoGeralOut` — US19/PBI-56: bases do PDA vigente
  (`pda.bases_do_plano`), inventário no escopo do usuário, `metadados.datasets_sem_recurso`,
  `situacao_atualizacao(base, hoje)` (sem vínculo → Aguardando vínculo; dataset fora do portal →
  Sem informação; senão `atualizacoes.regras.situacao_periodicidade`) e `inventario.ultima_coleta`.
  Testes em `tests/test_painel_visao_geral.py`.
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
| consome | atualizacoes | `regras.situacao_periodicidade` e `vencimento_atualizacao` (status das atualizações, cartão e alertas do Dashboard; coluna Atualização e cartão do detalhe em Organizações) |
| consome | lgpd | indicador de risco e ranking de exposição (US27) |
| consome | metadados | completude média; `recursos_formato_fechado(db, formatos_abertos)` e `regras.normalizar_formato` (Organizações); `datasets_sem_recurso(db)` (Dashboard) |
| consome | parametros | `formatos_abertos` |

## Jobs agendados
Nenhum.

## Regras de negócio e decisões
Decisões registradas: [ADR-0007](../adr/0007-prototipo-v1-referencia-das-telas.md).

- Indicadores calculados somente a partir da última coleta, com data visível (PBI-58).
- Bloco de alertas LGPD só aparece se o usuário também tiver `lgpd.acessar` (usar `<Pode>`).

## Pendências
- Fórmula do índice de atenção (validar com a GEDA).
- Dashboard: "Possíveis dados pessoais" depende do módulo `lgpd`; gráficos de evolução temporal
  (PBI-75) exigem guardar os indicadores por coleta.
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
| 21/10/2026 | Chave primária própria no inventário (ADR-0018): `organizacao_id` inteiro e `chave` = `id` em texto; consultas juntam por `Dataset.id` | Victor |
| 22/10/2026 | Banco só pelo `PainelDao` (ADR-0019): agregados da tela Organizações sem os registros excluídos | Victor |
| 28/10/2026 | Dashboard (Visão Geral, US19/PBI-56): `GET /painel/visao-geral`, `service.visao_geral`/`kpis`/`faixa_de_idade`, `PainelDao.datasets_por_situacao`/`recursos_validos`; tela com cartões, PDA vigente por situação, idade da última atualização real, alertas prioritários e fluxo; pendentes como "—" com o motivo | Humberto |
| 28/10/2026 | Dashboard: gráfico "Status das atualizações" (rosca) e cartão "Atualizações em atraso" pela periodicidade do PDA vigente (ADR-0023), no lugar da idade da última atualização; alerta "Atualização atrasada"; `situacoes_atualizacao` no lugar de `idade_atualizacao` | Humberto |
| 28/10/2026 | Dashboard: alertas em abas por tipo (Todos / PDA / Atualização / Inventário), até 10 de cada (`alertas_por_tipo`), para um tipo numeroso não esconder os outros | Humberto |
| 28/10/2026 | Organizações: coluna **Atualização** (% em dia pela periodicidade do PDA, ADR-0023) e cartão "Atualizações atrasadas" no detalhe (`atualizacao_pct`, `atualizacoes_atrasadas`, `atualizacoes_avaliadas`) | Humberto |
