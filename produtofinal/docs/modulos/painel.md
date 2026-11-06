# Módulo `painel` — Visão geral e organizações

| | |
|---|---|
| **Status** | Parcial: Dashboard (Visão Geral) e Organizações implementados, com indicadores que dependem do vínculo PDA × portal e da cobertura da varredura LGPD |
| **Responsável** | João (Dashboard) · Humberto (Organizações, PBI-84) |
| **User stories** | US19 (PBI-56 a PBI-59, PBI-75, PBI-76, PBI-84), US27 (exibição do ranking) |
| **Backend** | `backend/app/modules/painel/` |
| **Frontend** | `frontend/src/modules/dashboard/` · `frontend/src/modules/organizacoes/` |
| **Última atualização** | 06/11/2026 |

## Propósito
Consolida os indicadores dos eixos numa visão gerencial por órgão, usada pela GEDA e pela
Superintendência (inclusive para o Prêmio de Transparência).

## Telas
| Tela | Rota | Permissão para ver | Ações na tela (permissão) |
|---|---|---|---|
| Dashboard (Visão Geral) | `/` | `painel.acessar` | Cartões, gráficos e alertas prioritários; **Ver monitoramento completo** e **Ver** de cada alerta levam ao PDA (`/pda?orgao=<chave>`) ou a Datasets; "Atualizar dados" (`inventario.coletar`) |
| Organizações | `/organizacoes` | `painel.acessar` | Ordenação por coluna e paginação com total no rodapé (ADR-0028); detalhe do órgão (clique ou Enter na linha); **Ver bases no PDA** abre `/pda?orgao=<chave>` (`pda.acessar`); **Gerar relatório** do órgão (`relatorios.acessar`; exportar com `relatorios.exportar`); **Excel** e **PDF** da tabela como está na tela — filtros, ordem e todas as páginas (`relatorios.exportar`, ADR-0031) |

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
- **Possíveis dados pessoais** (só com `lgpd.acessar`, via `<Pode>` e no backend): barras por tipo
  (sem falso positivo), situação da triagem (Revisar, Confirmado, Falso positivo, Tratado),
  recursos com achados de N analisados e atalho **Ver dados pessoais** (`/lgpd`). O cartão do
  topo mostra os achados aguardando revisão.
- **Bases espontâneas** (ADR-0026): datasets ativos do portal sem base do PDA vigente vinculada
  pelo ID — total e % no título, barras pelos 10 órgãos com mais espontâneas (o resto em "Outros
  órgãos (N)") e atalho **Ver datasets**.
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
  Estática ou bases sem data) | **Riscos LGPD** (recursos com possível dado pessoal aguardando
  revisão ou confirmado, "N de M varridos"; badge âmbar com risco, verde sem; "não varrido" sem
  recurso varrido; "sem acesso" sem `lgpd.acessar`) | **Índice de atenção** (ADR-0030: faixa e
  valor 0–100, vermelho Alto, âmbar Médio, verde Baixo; dica com a conta; "sem dados" sem nenhum
  componente). Os pendentes aparecem como badge cinza, nunca 0. O rodapé explica as regras com os
  pesos e faixas em vigor.
- **Filtros** (na própria tela, sobre a lista já carregada): busca por nome ou sigla (sem
  diferenciar maiúsculas e acentos); **Em atraso** (com bases em atraso, sem atraso entre as
  vinculadas, com bases próximas do prazo, aguardando vínculo); **Índice de atenção** (Alto,
  Médio, Baixo, Sem dados); **Bases no PDA** (com/sem bases
  previstas); **Organização no portal** (com/sem). "Limpar filtros" volta a mostrar todos; o
  contador passa a "N de M órgão(s)".
- **Detalhe**: cartões do protótipo (previstas; publicadas e não publicadas, aguardando vínculo;
  **atualizações atrasadas** (de N bases com prazo, com o % em dia); possíveis dados pessoais, a
  definir; **recursos sem formato aberto** com
  o total de recursos e datasets), bases em atraso (mesma regra da tabela) e próximas do prazo,
  formatos fechados por tipo e a lista de formatos abertos em vigor; **Últimas alterações**: os 5
  eventos mais recentes do órgão na rastreabilidade (`HistoricoRecente`, com
  `rastreabilidade.acessar`) e o atalho para a tela Rastreabilidade filtrada pelo órgão.

## API
| Método | Rota (`/api/v1/painel`) | Permissão | Descrição |
|---|---|---|---|
| GET | `/visao-geral` | `painel.acessar` | `VisaoGeralOut` (escopo de órgão do usuário): plano vigente, hoje, `ultima_coleta`, `kpis` (`KpisOut`), `situacoes_pda` e `situacoes_atualizacao` (`[{rotulo, total}]`), `atualizacao_estimada`, `alertas` (`[{tipo, orgao, item, situacao, prazo, destino}]`, até 10 **por tipo**), `total_alertas`, `alertas_por_tipo`, `espontaneas` (`EspontaneasOut`) e `dados_pessoais` (`ResumoDadosPessoaisOut` do lgpd; null sem `lgpd.acessar`) |
| GET | `/organizacoes` | `painel.acessar` | `OrganizacoesOut`: plano vigente (`{id, nome}` ou null), hoje, `formatos_abertos` e uma `OrganizacaoOut` por órgão (escopo de órgão do usuário) |

`OrganizacaoOut`: chave (`id` da organização em texto ou `sigla:<SIGLA>`), organizacao_id (inteiro), nome, siglas,
datasets_no_portal, recursos_validos, recursos_formato_fechado, formatos_fechados `{formato: n}`
("" = sem formato), bases_previstas, bases_vinculadas, bases_publicadas, `bases_em_atraso` (só
entre as vinculadas; null sem nenhuma vinculada), bases_proximas_do_prazo, `atualizacao_pct` (% em
dia entre as vinculadas com prazo; null sem nenhuma), `atualizacoes_atrasadas` (null idem),
`atualizacoes_avaliadas`, `riscos_lgpd` (recursos com achado em aberto; null sem `lgpd.acessar` ou
sem recurso varrido), `lgpd_recursos_analisados`, `lgpd_aguardando_revisao`, `lgpd_confirmados`,
`risco_lgpd_pct`, `atraso_atualizacao_pct`, `indice_atencao` (Alto | Médio | Baixo; null sem
componente), `indice_atencao_valor` (0–100) e `indice_atencao_componentes`. `OrganizacoesOut` traz
também `lgpd_visivel` e `criterio_atencao` (pesos e faixas em vigor).

`KpisOut`: orgaos_monitorados, orgaos_no_pda, bases_previstas, bases_vinculadas, bases_publicadas,
`bases_em_atraso` (só entre as vinculadas; null sem nenhuma vinculada), bases_prazo_vencido,
datasets_publicados, datasets_fora_do_portal, recursos_monitorados, datasets_sem_recurso e os
`atualizacoes_em_atraso` (entre as vinculadas; null sem nenhuma) e `possiveis_dados_pessoais`
(achados aguardando revisão; null sem `lgpd.acessar`). `EspontaneasOut`: datasets_no_portal,
no_pda, espontaneas, por_orgao (`[{rotulo, total}]`).

## Serviços e métodos
`dao.py` — `PainelDao(Dao)` (ADR-0019): `organizacoes_visiveis`, `datasets_ativos_por_orgao`, `recursos_validos_por_orgao`, `orgao_de_cada_dataset`, `datasets_por_situacao(user)`, `recursos_validos(user)` e `datasets_ativos(user)` (Dashboard). Só leitura; registros excluídos não contam.

- `kpis(db, user, bases, *, orgaos, datasets, recursos, sem_recurso) -> KpisOut` — PBI-56.
- `visao_geral(db, user) -> VisaoGeralOut` — US19/PBI-56: bases do PDA vigente
  (`pda.bases_do_plano`), inventário no escopo do usuário, `metadados.datasets_sem_recurso`,
  `espontaneas(ativos, bases, orgs) -> EspontaneasOut` (ADR-0026, função pura) e
  `lgpd.service.resumo_dados_pessoais` (só com `lgpd.acessar`).
  `situacao_atualizacao(base, hoje)` (sem vínculo → Aguardando vínculo; dataset fora do portal →
  Sem informação; senão `atualizacoes.regras.situacao_periodicidade`) e `inventario.ultima_coleta`.
  Testes em `tests/test_painel_visao_geral.py`.
- `criterio_atencao(db) -> regras.CriterioAtencao` — pesos e faixas do índice, dos Parâmetros.
- `regras.indice_atencao(risco_lgpd_pct, atraso_pct, criterio)` (pura, ADR-0004) — média ponderada
  dos componentes com dado e peso > 0 (pesos redistribuídos), faixa pelos limites (inclusivos);
  `regras.pct`. ADR-0030.
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
| consome | lgpd | `service.resumo_dados_pessoais(db, user)` — cartão e gráfico "Possíveis dados pessoais" do Dashboard (só com `lgpd.acessar`); `service.riscos_por_orgao(db, user)` — coluna Riscos LGPD, cartão do detalhe e componente LGPD do índice de atenção em Organizações (só com `lgpd.acessar`); ranking de exposição (US27) a implementar |
| consome | metadados | completude média; `recursos_formato_fechado(db, formatos_abertos)` e `regras.normalizar_formato` (Organizações); `datasets_sem_recurso(db)` (Dashboard) |
| consome | parametros | `formatos_abertos`; `peso_lgpd_indice_atencao`, `peso_atualizacao_indice_atencao`, `indice_atencao_limite_medio`, `indice_atencao_limite_alto` (ADR-0030) |
| é consumido por | relatorios | `organizacoes(db, user)` (relatório por órgão) e `situacao_atualizacao(base, hoje)` (relatório de atualizações) |
| consome | rastreabilidade | tela: `HistoricoRecente` (`GET /rastreabilidade/eventos?orgao=<id>`) — "Últimas alterações" no detalhe do órgão em Organizações |
| consome | relatorios | tela: `GerarRelatorioOrgaoModal` (`relatorios/RelatorioOrgao.tsx`) no detalhe do órgão em Organizações — marca os relatórios e gera o documento do órgão (`/relatorios/por-orgao/{organizacao_id}/…`) |
| consome | relatorios | `POST /relatorios/tabela/exportar` (pelo frontend, `ExportarTabela`) — Excel e PDF da tabela da tela (ADR-0031) |

## Jobs agendados
Nenhum.

## Regras de negócio e decisões
Decisões registradas: [ADR-0007](../adr/0007-prototipo-v1-referencia-das-telas.md).

- Indicadores calculados somente a partir da última coleta, com data visível (PBI-58).
- Bloco de alertas LGPD só aparece se o usuário também tiver `lgpd.acessar` (usar `<Pode>`).
- Índice de atenção por órgão: média ponderada do risco LGPD e do atraso de atualização, pesos e
  faixas em Parâmetros ([ADR-0030](../adr/0030-indice-de-atencao-por-media-ponderada.md)). Sem
  `lgpd.acessar`, nem a coluna Riscos LGPD nem o componente LGPD do índice (o painel não amplia o
  acesso).

## Pendências
- Validar com a GEDA o critério do índice de atenção (ADR-0030): o que conta como risco LGPD e os
  pesos 70/30 e faixas 25/50 provisórios.
- Dashboard: gráficos de evolução temporal (PBI-75) exigem guardar os indicadores por coleta.
  Bases espontâneas: reclassificação manual (PBI-18) e filtro "espontânea" na tela Datasets.
- Organizações: "Bases publicadas" depende do vínculo base × dataset (hoje 0 de 409 no PDA vigente);
  "Atualização" da regra por periodicidade (`atualizacoes`, PBI-27/28); "Riscos LGPD" da
  cobertura da varredura (por demanda). Validar com a GEDA se ZIP (605 recursos no
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
| 30/10/2026 | Interações: `organizacoes` e `situacao_atualizacao` consumidos pelo módulo `relatorios` (sem mudança no código do painel) | Victor |
| 30/10/2026 | Dashboard: gráficos **Possíveis dados pessoais** (resumo do lgpd, só com `lgpd.acessar`; cartão com os achados aguardando revisão) e **Bases espontâneas** (ADR-0026: datasets ativos sem vínculo com o PDA vigente, por órgão); `espontaneas()`, `PainelDao.datasets_ativos`, `EspontaneasOut`, `dados_pessoais` | Humberto |
| 05/11/2026 | Tela Organizações: ordenação por qualquer coluna (clique no título) e paginação no rodapé com o total de registros (50 por página, ajustável até 999; `shared/ui/tabela.tsx`, ADR-0028); contador de órgãos movido para o rodapé. Sem mudança na API | Victor |
| 05/11/2026 | Organizações: botão **Gerar relatório** no detalhe do órgão (com `relatorios.acessar` e organização no portal) — marca os relatórios, como na tela Relatórios, e gera o documento só daquele órgão (`GerarRelatorioOrgaoModal`). Sem mudança na API | Humberto |
| 05/11/2026 | Organizações: **Últimas alterações** no detalhe do órgão com os últimos eventos da rastreabilidade (`HistoricoRecente`), no lugar do texto pendente. Sem mudança na API | Humberto |
| 05/11/2026 | Organizações: colunas **Riscos LGPD** e **Índice de atenção** (ADR-0030) — `regras.py` novo (`indice_atencao`, média ponderada com pesos e faixas dos Parâmetros), `criterio_atencao`, campos novos em `OrganizacaoOut`/`OrganizacoesOut`; filtro por faixa, ordenação pelo valor, cartão de dados pessoais e índice explicado no detalhe; `indice_atencao_por_orgao` (stub) removido | Humberto |
| 06/11/2026 | Organizações: botões **Excel** e **PDF** da tabela (`ExportarTabela`, ADR-0031); Riscos LGPD só entra no arquivo com `lgpd.acessar` | Humberto |
