# CLAUDE.md — Monitor Dados Abertos GO

Instruções para o Claude (e para qualquer pessoa) que trabalhe neste repositório. Leia inteiro
antes de alterar código. As regras da seção **Regras obrigatórias** não são sugestões.

## O projeto

Camada de monitoramento e governança do **Portal de Dados Abertos do Estado de Goiás**
(https://dadosabertos.go.gov.br, CKAN 2.9.5), desenvolvida pelo **Squad 2 da Residência em
Sistemas de Informação da UFG** para a **CGE-GO / Gerência de Dados Abertos (GEDA)**.

- **Problema:** o monitoramento do portal (~446 bases, ~2.939 recursos, ~48 órgãos) é manual,
  feito em planilhas por uma servidora e um estagiário. Não há como verificar de forma contínua o
  cumprimento do PDA 2025/2027, a atualização real dos recursos nem a exposição de dados pessoais.
- **Base normativa:** Decreto estadual nº 10.176/2022 (Política de Dados Abertos) e LGPD.
- **Eixo 1** — monitoramento do PDA e atualização temporal (João e Humberto).
- **Eixo 2** — dados pessoais / LGPD, metadados obrigatórios e Assistente (Luiza).
- **Base comum** (coleta, acesso, painel, relatórios) — João. **Coordenação** — Victor.
- **Cliente:** Paloma Peixoto (Gerente de Dados Abertos, dona do negócio); Júnior Costa
  (Superintendente de Transparência, patrocinador). **Infraestrutura CKAN:** Wagner (SECTI).
  **Orientação:** Prof. Alessandro Cruvinel.
- **Prazo:** residência de 10/08 a 02/12/2026; entregas amarradas aos checkpoints presenciais
  (23/09, 28/09, 07/10, 14/10, 19/10, 26/10, 04/11, 09/11, 18/11, 23/11, 02/12).
- **Referência das telas:** `prototipos/prototipoV1.html`, validado com a CGE-GO em 17/09/2026.
- **Backlog:** 29 user stories / 103 PBIs (Backlog v2). Compromissos: US16, US24, US28; US14 e
  US17 deixaram de ser condicionais; US13, US15, US18 não comprometidas.

Restrições do PGP v2 que moldam o código:
- A solução é **externa ao CKAN**. Não altera código, configuração nem extensões do portal.
- A **única escrita** no CKAN é a publicação de recurso anonimizado, após aprovação humana (US26).
- Só ferramentas gratuitas ou de código aberto. Infraestrutura leve (sem banco vetorial).
- Testes apenas com dados públicos ou fictícios.

## Stack e comandos

Backend Python 3.11 + FastAPI + SQLAlchemy 2 (síncrono) + Alembic · Frontend React 18 + TS + Vite
· PostgreSQL 16 (SQLite em dev) · APScheduler em processo próprio · IA plugável.

```bash
# backend (em backend/)
pip install -e ".[dev]"
alembic upgrade head
python -m app.cli criar-usuario --email voce@cge.go.gov.br --nome "Nome" --papel administrador
uvicorn app.main:app --reload          # API :8000, docs em /api/v1/docs
python -m app.worker                   # jobs agendados
python -m pytest                       # testes (inclui as guardas deste arquivo)
alembic revision --autogenerate -m "<modulo>: <mudança>"

# frontend (em frontend/)
npm install && npm run dev             # :5173, proxy /api → :8000
npm run build                          # tsc estrito + build

# raiz
python scripts/gerar_permissoes_ts.py  # após alterar o catálogo de permissões
python scripts/gerar_mer.py            # após alterar modelos (use o Python de backend/.venv)
python scripts/checar_decisoes.py      # valida ADRs e linha do tempo
git config core.hooksPath .githooks    # uma vez por clone: ativa o pre-commit
docker compose up -d --build           # ambiente completo
```

## Estrutura

```
backend/app/core/permissoes.py    CATÁLOGO CENTRAL de permissões e papéis padrão
backend/app/core/deps.py          PORTÃO de acesso: require, autenticado, publico, escopo de órgão
backend/app/modules/<id>/         um módulo = router · service · models · schemas · regras
backend/app/modules/__init__.py   INSTALLED_MODULES (registro dos módulos)
backend/app/integrations/ckan/    client.py (leitura) · writer.py (escrita restrita)
backend/app/integrations/ai/      contrato, adaptadores, política LGPD
frontend/src/modules/<pasta>/     uma tela; index.ts declara modulo, permissao, rota, menu
frontend/src/modules/registry.ts  registro das telas
frontend/src/shared/acesso/       <Pode>, permissoes.gen.ts (GERADO — não editar)
docs/modulos/<id>.md              documentação de cada módulo (formato em _MODELO.md)
docs/adr/                         DECISÕES: uma ADR por decisão + linha do tempo (README.md)
docs/banco/convencoes.md          regras de modelagem do banco (obrigatórias)
docs/banco/mer.md                 MER + dicionário de dados (GERADO — não editar)
docs/arquitetura.md               visão geral da arquitetura
```

## Regras obrigatórias

### 1. Documentação de módulo acompanha o código
- **Toda alteração em um módulo atualiza `docs/modulos/<id>.md` no mesmo commit.** Atualize as
  seções afetadas (Telas, API, Serviços e métodos, Modelo de dados, Permissões, Interações,
  Pendências), a data em "Última atualização" e acrescente uma linha no **Histórico**.
- Um arquivo pertence ao módulo `<id>` quando está em `backend/app/modules/<id>/` ou numa tela
  `frontend/src/modules/<pasta>/` cujo `index.ts` declara `modulo: "<id>"`. Alterar
  `backend/app/core/permissoes.py` conta como alteração do módulo `acesso`.
- Se a mudança afeta outro módulo (ex.: novo dado consumido), atualize a seção Interações dos dois.
- Módulo novo: copie `docs/modulos/_MODELO.md`, preencha e inclua no índice `docs/modulos/README.md`.
- Verificação: `.githooks/pre-commit` (`scripts/checar_docs_modulos.py`) e
  `tests/test_guardas_do_projeto.py`.

### 2. Controle de acesso centralizado
- **Permissões existem só em `backend/app/core/permissoes.py`** (enum `P`, convenção
  `<modulo>.<acao>`; `<modulo>.acessar` = ver o módulo). Nunca crie permissão em outro lugar.
- **Toda rota do backend declara controle de acesso:** `Depends(require(P.X))`,
  `require_qualquer(...)`, `autenticado` ou, só para login/saúde, `publico`. A API não sobe se
  alguma rota não declarar (`verificar_controle_de_acesso` em `main.py`).
- **Toda tela declara `permissao` no manifesto** (`index.ts`); sem ela o TypeScript não compila.
  Botões e ações dentro da tela usam `<Pode permissao="...">` ou `useAuth().pode(...)`.
- Esconder no frontend não é segurança: a ação correspondente **também** exige a permissão no backend.
- Consultas que retornam dados por órgão aplicam `filtrar_por_orgao(stmt, coluna, user)`; ações
  sobre um registro específico chamam `exigir_mesmo_orgao(user, orgao_id)`.
- **Nunca verifique por nome de papel** (`if "gerente_geda" in user.papeis`). Sempre por permissão.
- Alterou o catálogo: rode `python scripts/gerar_permissoes_ts.py`, ajuste papéis padrão se
  preciso e atualize a matriz em `docs/modulos/acesso.md`.

### 3. CKAN
- Leitura apenas por `integrations/ckan/client.py`. Escrita apenas por `integrations/ckan/writer.py`,
  chamada exclusivamente pelo fluxo de anonimização do módulo `lgpd`, após aprovação registrada.
- Vínculo sempre pelo **ID do dataset**, nunca pelo `name`.
- Atualização real = `last_modified` do **recurso**. `metadata_modified` não é indicador.
- Dicionário de dados não entra na contagem de recursos.

### 4. IA e dados pessoais
- Módulos usam IA **somente** via `AIGateway(db).chat(TarefaIA.X, ...)`. Nunca importe um adaptador.
- Tarefa que processa dado pessoal tem `sensivel=True` em `integrations/ai/policy.py` e só roda em
  modelo local.
- Nunca persistir valores de dados pessoais: achados guardam localização e tipo; `ia_uso` guarda
  só metadados da chamada.
- O Assistente recebe apenas indicadores agregados e respeita o escopo de órgão.

### 5. Escopo
- Não implemente funcionalidade fora do Backlog v2 sem sinalizar. Ex.: o módulo `envio` (órgão
  publicador enviando recursos) está **não comprometido** e depende de decisão da CGE-GO/SECTI.
- Dúvida técnica de CKAN/infraestrutura → Wagner (SECTI). Decisão institucional → Paloma/Júnior.

### 6. Código
- Regra de negócio em `service.py`/`regras.py`; `router.py` só valida e delega.
  Funções puras em `regras.py` (reaproveitáveis numa extensão CKAN — ADR 0004).
- Banco: siga `docs/banco/convencoes.md` (nomes, chaves, tipos, privacidade). Mudou tabela →
  docstring no modelo, migração Alembic revisada e `python scripts/gerar_mer.py`, no mesmo commit.
- Nomes de domínio em português; termos do CKAN em inglês (`last_modified`, `package_search`).
- Commits: `feat(<modulo>): descrição (PBI-NN)` — ver `docs/padroes.md`.
- Nunca versionar `.env`, bancos locais, chaves ou cópias de recursos com dados pessoais.

### 7. Decisões técnicas são registradas (ADR-0015)
- **Toda decisão técnica vira uma ADR** em `docs/adr/` (modelo `_MODELO.md`) e uma linha na linha do
  tempo `docs/adr/README.md`, **no mesmo commit** da mudança. Exemplos: adotar ou trocar biblioteca,
  ferramenta ou serviço; escolher entre dois desenhos; mudar convenção; aceitar um risco.
- Registre **ao menos duas opções com prós e contras**, os critérios, quem decidiu, quem foi
  consultado e o **apoio de IA** (o que a IA sugeriu ou implementou; a decisão é sempre humana).
- Decisão aceita não é reescrita. Fato novo ou melhoria → linha em "Revisões" da ADR. Mudou a decisão
  → ADR nova; a antiga fica "Substituída por ADR-XXXX".
- Quando a decisão surgir numa conversa com IA, **proponha a ADR antes de implementar**, com as
  alternativas, e só registre como "Aceita" depois da escolha do responsável.
- Mudanças em dependências ou infraestrutura (`pyproject.toml`, `package.json`, Docker, `core/db.py`,
  `core/security.py`, `core/crypto.py`, `alembic/env.py`) exigem ADR ou revisão no mesmo commit
  (`scripts/checar_decisoes.py`).
- Decisão que depende do cliente ou da SECTI fica "Em análise" e entra em "Decisões em aberto".

## Antes de concluir uma tarefa
1. `python -m pytest` (backend) e `npm run build` (frontend) passando.
2. `docs/modulos/<id>.md` de cada módulo tocado atualizado, com linha no Histórico.
3. Rotas e telas novas com permissão do catálogo; catálogo alterado → TS regenerado.
4. Mudança de tabela: migração revisada e MER regenerado.
5. Decisão técnica tomada: ADR criada ou revisada e linha do tempo atualizada.
