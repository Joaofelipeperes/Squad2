# ADR-0013 — Usar PostgreSQL com convenções de modelagem explícitas e MER gerado do código

| | |
|---|---|
| **Status** | Aceita |
| **Tipo** | Técnica |
| **Data da decisão** | 30/09/2026 (banco e nomes de constraints); 07/10/2026 (convenções e MER) |
| **Data do registro** | 07/10/2026 |
| **Decisores** | Victor Hugo Benatti |
| **Consultados** | Orientador (01/10): as instruções de modelagem e nomenclatura devem fazer parte das regras do projeto (AGENTS.md) |
| **Origem** | Sessões de 30/09 e 07/10; reunião com o orientador (01/10) |
| **Afeta** | `backend/app/core/db.py`, todos os `models.py`, `docs/banco/` |

## Contexto
O banco guarda o espelho do inventário, achados, decisões humanas e configuração. Em 30/09 o SQLite
rejeitou uma migração por constraint sem nome, o que levou a adotar uma convenção de nomes. Em 01/10 o
orientador lembrou que, sem instruções de modelagem, a IA cria o banco "de qualquer jeito". Em 07/10
o time notou que não havia MER documentando os relacionamentos.

## Critérios de decisão
1. Gratuito e suportado pela SECTI.
2. Migrações reproduzíveis.
3. Documentação do banco sempre igual ao código.
4. Não gerar retrabalho no que já está versionado.

## Opções consideradas — banco

### PostgreSQL em homologação e produção, SQLite em desenvolvimento
- **Prós:** PostgreSQL é o banco do próprio CKAN (familiar à SECTI), robusto e gratuito; SQLite
  permite rodar e testar sem instalar nada.
- **Contras:** diferenças entre os dois (ALTER TABLE no SQLite) — tratadas com `render_as_batch`.

### Somente PostgreSQL, inclusive em desenvolvimento
- **Prós:** paridade total.
- **Contras:** cada residente precisa de PostgreSQL ou Docker para rodar os testes.

### MySQL / MariaDB
- **Prós:** gratuito e conhecido.
- **Contras:** sem vantagem sobre PostgreSQL aqui; foge do ecossistema do CKAN.

### Usar o banco do próprio CKAN
- **Prós:** dados "na fonte".
- **Contras:** viola a regra de não alterar o CKAN; acopla a solução ao esquema interno dele.

## Opções consideradas — documentação do modelo

### MER desenhado à mão (draw.io, dbdiagram)
- **Prós:** layout livre.
- **Contras:** fica desatualizado no primeiro commit que muda uma tabela.

### MER gerado dos modelos, verificado por hook e teste
- **Prós:** nunca diverge do código; dicionário de dados incluído.
- **Contras:** layout automático, menos refinado.

## Opções consideradas — inconsistências encontradas ao gerar o MER

Tabelas sem prefixo de módulo (`coleta`, `dataset`, `usuario`…) e `created_at`/`updated_at` em inglês.
- **Renomear agora:** padroniza tudo, mas exige migração de renomeação e ajuste de código já
  versionado pelo time, sem ganho funcional.
- **Manter como exceção documentada e exigir o padrão em tabelas novas:** sem retrabalho e com
  regra clara daqui em diante.

Autoria em trilhas de auditoria (`lgpd_decisao.usuario`, `*.alterado_por`).
- **Chave estrangeira para `usuario`:** integridade, mas o histórico depende do usuário existir.
- **E-mail gravado como texto no momento da ação:** o histórico sobrevive a exclusões e renomeações.

## Decisão
- PostgreSQL em homologação e produção; SQLite em desenvolvimento e testes.
- `NAMING_CONVENTION` no `MetaData` (`core/db.py`); a migração inicial foi regenerada em 30/09,
  antes de qualquer implantação.
- Convenções formalizadas em `docs/banco/convencoes.md`: exceções atuais mantidas, padrão exigido
  em tabelas novas; autoria de auditoria como e-mail texto; referências sem FK declaradas.
- MER gerado por `scripts/gerar_mer.py` em `docs/banco/mer.md`, verificado no hook e nos testes;
  docstring obrigatória em todo modelo.

## Consequências
- **Positivas:** documentação do banco confiável; instrução clara para humanos e IA.
- **Negativas e riscos:** convivência temporária com as exceções de nomenclatura.

## Validação
Revisão do time ao criar a primeira tabela do Eixo 1 ou 2 seguindo as convenções.

## Revisões
| Data | Revisão | Autor |
|---|---|---|
| 07/10/2026 | Docstrings acrescentadas aos modelos sem descrição (acesso, inventario, lgpd, parametros) para o dicionário de dados | Victor |
