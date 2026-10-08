# Monitor Dados Abertos GO

Camada de monitoramento e governança do **Portal de Dados Abertos do Estado de Goiás**
(dadosabertos.go.gov.br, CKAN 2.9.5) para a GEDA/CGE-GO. Projeto do Squad 2 —
Residência em Sistemas de Informação da UFG.

A solução é **externa ao CKAN**: lê o inventário pela API pública e só escreve no portal em um
caso — a publicação de recurso anonimizado aprovada por quem tem a permissão `lgpd.aprovar_correcao` (US26).

## Stack

| Camada | Tecnologia |
|---|---|
| Frontend | React 18 + TypeScript + Vite, TanStack Query, React Router. Visual = CSS do Protótipo V1 |
| Backend | Python 3.11, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2 |
| Banco | PostgreSQL 16 (SQLite em dev local) |
| Tarefas agendadas | APScheduler em processo próprio (`app.worker`) |
| Acesso | Papéis e permissões (RBAC) com catálogo central e escopo por órgão |
| IA | Camada plugável: Gemini, Ollama (local), servidores compatíveis com OpenAI, simulado |

Todas as dependências são gratuitas e de código aberto (restrição do PGP v2).

## Como rodar

**Com Docker** (recomendado):

```bash
cp .env.example .env            # ajuste GDA_SECRET_KEY e GDA_ENCRYPTION_KEY
docker compose up -d --build
docker compose exec api python -m app.cli criar-usuario --email voce@cge.go.gov.br --nome "Seu Nome" --papel administrador
docker compose exec api python -m app.cli semear-ia     # perfis de IA de exemplo
```

Web em http://localhost:8080 · API em http://localhost:8000/api/v1/docs

**Sem Docker** (desenvolvimento):

```bash
cd backend && python -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"
alembic upgrade head && python -m app.cli criar-usuario --email a@b.gov.br --nome Dev --papel administrador
uvicorn app.main:app --reload                 # API em :8000
python -m pytest                              # testes

cd ../frontend && npm install && npm run dev  # web em :5173 (proxy /api → :8000)
```

Depois de clonar, ative o hook que exige a documentação dos módulos:
`git config core.hooksPath produtofinal/.githooks` (a raiz do git é a pasta acima de `produtofinal/`).

## Estrutura

```
AGENTS.md          contexto do projeto e regras obrigatórias (leia primeiro)
backend/app/
  core/            configuração, banco, cifragem, contrato de módulo
    permissoes.py  CATÁLOGO CENTRAL de permissões e papéis
    deps.py        portão de acesso: require, autenticado, escopo de órgão
  integrations/
    ckan/          client.py (leitura) · writer.py (escrita restrita, desligada por padrão)
    ai/            contrato AIProvider, registro, política LGPD, adaptadores por fornecedor
  modules/         um pacote por domínio: router · service · models · schemas
    __init__.py    INSTALLED_MODULES — registro único dos módulos
frontend/src/
  app/             shell (sidebar/topbar), autenticação, rotas
  design-system/   CSS do Protótipo V1 (intocado) + overrides
  modules/         uma pasta por tela; index.ts declara módulo, permissão, menu e rota
    registry.ts    registro único das telas
  shared/          cliente HTTP, componentes de UI, acesso (<Pode>, permissoes.gen.ts)
docs/
  modulos/         um .md por módulo: telas, API, métodos, interações, histórico
  adr/             decisões com alternativas, prós e contras + linha do tempo
  banco/           MER (gerado) e convenções de modelagem
scripts/           gerar_permissoes_ts.py · gerar_mer.py · checar_docs_modulos.py · checar_decisoes.py
.githooks/         pre-commit (docs por módulo, decisões, permissões, MER)
prototipos/        Protótipo V1 (referência visual — PBI-66)
```

## Documentação

- [AGENTS.md — contexto e regras](AGENTS.md)
- [Arquitetura](docs/arquitetura.md)
- [Módulos](docs/modulos/README.md)
- [Decisões — linha do tempo (ADRs)](docs/adr/README.md)
- [MER e dicionário de dados](docs/banco/mer.md) · [Convenções do banco](docs/banco/convencoes.md)
- [Como criar um módulo](docs/como-criar-modulo.md)
- [Padrões de código e commits](docs/padroes.md)
