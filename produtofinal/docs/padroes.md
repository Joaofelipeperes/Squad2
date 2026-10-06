# Padrões de código e de trabalho

## Branches
`main` protegida · trabalho em `feat/PBI-19-situacao-prazo`, `fix/PBI-25-recurso-sem-data`.

## Commits (Conventional Commits, em português)
```
feat(pda): calcula situação do prazo de abertura (PBI-19)
fix(inventario): trata recurso sem last_modified (PBI-25)
docs(arquitetura): registra decisão da US29
```
Tipos: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`. Escopo = nome do módulo.

## Pull requests
Um PBI por PR; descrição cita o ID do ClickUp; ao menos uma revisão de outro residente;
`pytest` e `npm run build` passando.

## Documentação de módulo
Todo PR que altera um módulo atualiza `docs/modulos/<modulo>.md`, com linha no Histórico. O hook
de pre-commit verifica: ative com `git config core.hooksPath .githooks`.

## Código
- Python: `ruff` (linha 100); nomes de domínio em português, termos do CKAN em inglês
  (`last_modified`, `package_search`).
- Regra de negócio fica no `service.py`/`regras.py`, nunca no `router.py`.
- TypeScript estrito; chamadas HTTP somente via `shared/api/client.ts`.
- Permissão sempre do catálogo (`P.X` no backend, string tipada no frontend); nunca checar nome de papel.

## Dados
Testes apenas com dados públicos ou fictícios. Nunca versionar `.env`, bancos locais ou cópias de
recursos com dados pessoais.
