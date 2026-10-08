# Como criar um módulo

Exemplo: módulo `pda` (já implementado — use-o como referência de estrutura; os passos abaixo mostram
como ele foi criado).

## Backend

1. Pasta `backend/app/modules/pda/` com `__init__.py`, `router.py`, `service.py` e, se houver
   tabelas, `models.py`.
2. No `__init__.py`:
   ```python
   module = BackendModule(name="pda", prefix="/pda", tags=["Eixo 1 · Monitoramento do PDA"],
                          router=router, user_stories=["US6", "US7", "US8"])
   ```
3. Registrar `"pda"` em `INSTALLED_MODULES` (`app/modules/__init__.py`).
4. Criou ou alterou tabela: `alembic revision --autogenerate -m "pda: base prevista"` e revise o
   arquivo gerado antes do commit.
5. **Permissões:** acrescente as do módulo em `app/core/permissoes.py` (`P.PDA_ACESSAR`,
   `P.PDA_EDITAR_VINCULOS`, com `META`), inclua nos papéis padrão adequados e rode
   `python scripts/gerar_permissoes_ts.py`. **Toda rota** declara uma:
   `dependencies=[Depends(require(P.PDA_ACESSAR))]` ou `user = Depends(require(P.X))` quando
   precisar do usuário. Dados por órgão: `filtrar_por_orgao(stmt, Model.orgao, user)`.
6. Precisa de IA? Use `AIGateway(db).chat(TarefaIA.X, ...)`. Tarefa nova: acrescente em
   `integrations/ai/policy.py` (com `sensivel=True` se tocar dado pessoal). Ela aparece sozinha
   na página de configuração.
7. Job agendado: `jobs=[JobSpec(id="...", func=..., cron="0 4 * * *")]`.

## Frontend

1. Pasta `frontend/src/modules/pda/` com `index.ts` (manifesto, com `modulo: "pda"` e
   `permissao: "pda.acessar"`) e a página. Botões de ação: `<Pode permissao="pda.editar_vinculos">`.
2. Registrar o manifesto em `src/modules/registry.ts`, na posição desejada do menu.
3. Copie a marcação da seção correspondente de `prototipos/prototipoV1.html` (ex.:
   `#screen-pda`) e troque o `mockData` por chamadas `api.get(...)` com `useQuery`.

## Documentação

1. Copie `docs/modulos/_MODELO.md` para `docs/modulos/pda.md` e preencha.
2. Inclua o módulo no índice `docs/modulos/README.md`.
3. Daqui em diante, **todo commit que tocar o módulo atualiza esse arquivo** (regra do AGENTS.md).
