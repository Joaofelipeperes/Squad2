# ADR-0019 — Acessar o banco só por DAOs, com `id` em toda tabela, exclusão lógica e auditoria

| | |
|---|---|
| **Status** | Aceita |
| **Tipo** | Técnica |
| **Data da decisão** | 22/10/2026 |
| **Data do registro** | 22/10/2026 |
| **Decisores** | Victor Hugo Benatti (coordenação) |
| **Consultados** | — |
| **Origem** | Sessão de trabalho de 22/10/2026 (revisão do MER após a ADR-0018) |
| **Afeta** | `app/core/db.py` (`RegistroMixin`, `unico_entre_ativos`), `app/core/dao.py` (novo); `dao.py` em cada módulo com acesso ao banco; todas as 19 tabelas; `docs/banco/convencoes.md`; `AGENTS.md` §6; `tests/test_guardas_do_projeto.py`; migração `a8e2f5c1d9b4` |

## Contexto
Depois da ADR-0018, o MER ainda misturava padrões de chave primária: `id` na maioria das tabelas,
`chave` em `parametro`, `tarefa` em `ia_vinculo_tarefa` e chaves compostas nas associações
(`acesso_usuario_papel`, `acesso_papel_permissao`). Não havia regra central de exclusão: cada
módulo apagava registros fisicamente (`db.delete`, cascatas `delete-orphan`, `ON DELETE CASCADE`),
sem rastro de quem excluiu, e só algumas tabelas tinham `created_at`/`updated_at`, sem o usuário.
As consultas eram montadas e executadas diretamente nos services e routers.

## Critérios de decisão
1. Um padrão único e evidente para toda tabela (chave, exclusão, auditoria).
2. Nenhuma consulta pode "esquecer" de ignorar registros excluídos.
3. Auditoria de quem criou e de quem foi o último a alterar (inclusive excluir) cada registro.
4. Funcionar em PostgreSQL e SQLite (ADR-0013); preservar os dados existentes.

## Opções consideradas — acesso ao banco

### Opção A — Filtro automático na sessão, consultas continuam nos services
- **Prós:** pouca mudança de código.
- **Contras:** o acesso ao banco segue espalhado; a regra fica implícita num evento da sessão.

### Opção B — Classe-pai `Dao` com funções genéricas; DAOs por módulo herdam dela
- **Prós:** uma porta única e explícita: as funções genéricas (`buscar*`, `obter`, `save_generic`,
  `delete_generic`, `update_generic`) montam o SQL com `deleted = false`, preenchem a auditoria e
  fazem a exclusão lógica; cada módulo declara suas consultas num `dao.py`. Verificável por teste.
- **Contras:** reescrever todas as consultas; um arquivo a mais por módulo.

## Opções consideradas — campos únicos com exclusão lógica

### Únicos entre todos os registros
- **Prós:** nenhuma mudança nas restrições.
- **Contras:** um e-mail ou nome de PDA excluído nunca poderia ser reaproveitado.

### Únicos só entre os registros ativos (índice parcial `WHERE NOT deleted`)
- **Prós:** excluir libera o valor; PostgreSQL e SQLite suportam índice parcial.
- **Contras:** as restrições viram índices (nomes `uq_<tabela>_<colunas>` mantidos).

## Opções consideradas — auditoria da exclusão

### Só `deleted`
- **Prós:** mínimo.
- **Contras:** não diz quem nem quando.

### `deleted` + `created`/`created_id` + `changed`/`changed_id` em toda tabela
- **Prós:** quem criou e quem mexeu por último em qualquer registro; a exclusão é a última alteração.
- **Contras:** cinco colunas em toda tabela.

## Decisão
- **Toda tabela** herda de `Base` (`RegistroMixin`): `id` inteiro (PK), `deleted` (false = ativo),
  `created`/`created_id` (data UTC e `usuario.id` de quem criou) e `changed`/`changed_id` (data e
  usuário da última alteração; a exclusão é uma alteração). `created_id`/`changed_id` são
  referências lógicas a `usuario.id` (sem FK, para não criar ciclo `usuario` → `organizacao` →
  `usuario`); vazio = sistema (coleta agendada, CLI, migração). Os nomes seguem o pedido do decisor
  (em inglês), como exceção documentada nas convenções.
- `parametro`, `ia_vinculo_tarefa`, `acesso_usuario_papel` e `acesso_papel_permissao` ganham `id`;
  a chave antiga vira índice único entre ativos.
- **Campos únicos valem só entre os ativos** (`unico_entre_ativos`, índice parcial `NOT deleted`).
- **Opção B**: `app/core/dao.py` é a única porta para a sessão; cada módulo tem `dao.py` com uma
  classe que herda de `Dao`. A leitura aplica `deleted = false` a toda tabela da consulta
  (inclusive joins, subconsultas e relacionamentos carregados, via `with_loader_criteria`);
  `save_generic` preenche a auditoria com o usuário do DAO; `delete_generic` faz a exclusão lógica.
  Nada é apagado fisicamente; exclusões em cascata são feitas pelo DAO do módulo (ex.: excluir um
  PDA exclui suas bases). `tests/test_guardas_do_projeto.py` falha se algum arquivo fora de um DAO
  chamar a sessão.
- `recurso.created` (data do CKAN) passa a `recurso.created_ckan`, pois `created` agora é a auditoria.

## Consequências
- **Positivas:** um padrão para todas as tabelas; exclusão reversível e auditada; consultas de cada
  módulo reunidas num lugar; impossível consultar registros excluídos por esquecimento.
- **Negativas e riscos:** migração `a8e2f5c1d9b4` mexe nas 19 tabelas — testada em SQLite,
  PostgreSQL e cópia do banco de desenvolvimento; downgrade recusado se houver registro excluído.
  Registros excluídos continuam ocupando espaço (expurgo, se necessário, será outra decisão).
  Um dataset excluído na solução que continue no portal volta como registro novo na próxima coleta
  (o espelho do CKAN prevalece).

## Validação
Revisão do time na próxima sincronização; a GEDA (Paloma) valida o uso da trilha "quem alterou".

## Revisões

| Data | Revisão | Autor |
|---|---|---|
