---
name: revisao-iso27001
description: Revisa o código e a configuração do repositório contra os controles da ISO/IEC 27001:2022 (Anexo A) e as orientações da ISO/IEC 27002:2022 que se aplicam a software — controle de acesso, autenticação, criptografia, logging, desenvolvimento seguro, gestão de vulnerabilidades, configuração, segregação de ambientes e dados de teste. Use quando o usuário pedir revisão ISO 27001, ISO 27002, SGSI, controles do Anexo A, gap analysis de segurança da informação ou evidências de conformidade no código.
---

# Revisão contra ISO/IEC 27001:2022 e 27002:2022

A ISO 27001 certifica um **sistema de gestão** (SGSI), não um código. Esta skill avalia a parte
que o código e o repositório podem evidenciar: os controles **tecnológicos** (tema 8 do Anexo A) e
os organizacionais que se materializam em software. Para cada controle aplicável, classifique como
**Atende**, **Atende parcialmente**, **Não atende** ou **Fora do alcance do código**, com evidência
arquivo:linha. Não é auditoria de certificação: diga isso no relatório.

## Regras invioláveis

- **Nada sai da máquina.** Não envie código, trechos ou dados a serviços externos, MCPs remotos
  (inclusive gateways de compliance), APIs de IA de terceiros nem buscas na web. Só leitura local
  (Read, Grep, Glob, git, e ferramentas locais já instaladas como `pip-audit`/`npm audit` **apenas
  se o usuário autorizar**, pois consultam bases públicas de vulnerabilidades enviando nomes e
  versões de pacotes — nunca código).
- Não reproduza o texto das normas (protegido por direitos autorais). Cite só o número e o título
  curto do controle e descreva com suas palavras.
- Não altere código durante a revisão. Não abra `.env`, chaves ou dados reais.

## Escopo

1. Arquivos/pasta indicados; senão o diff da branch (`git diff --merge-base origin/desenvolvimento`,
   ou `origin/main`). Num diff, avalie só os controles que o diff toca.
2. Revisão completa: `produtofinal/backend/app/core` (permissões, deps, segurança, config),
   `backend/app/modules/acesso`, `integrations/`, `alembic/`, `pyproject.toml`/`requirements`,
   `frontend/package.json`, `Dockerfile`s, `docker-compose*.yml`, `deploy/`, `nginx*.conf`,
   `.githooks`, `.github/`, testes, `.gitignore`, scripts `.ps1`/`.py` da raiz.
3. Leia `produtofinal/AGENTS.md` e as ADRs (`produtofinal/docs/adr/`) — ADRs e o processo de
   decisões são **evidência** para controles organizacionais (ex.: gestão de mudanças).

## Controles a avaliar (ISO/IEC 27001:2022, Anexo A)

### Acesso e identidade
- **5.15 Controle de acesso / 8.3 Restrição de acesso à informação** — autorização aplicada no
  servidor em toda rota; negar por padrão; escopo por órgão; frontend não é barreira.
- **5.16 Gestão de identidade / 5.18 Direitos de acesso** — criação, alteração e desativação de
  usuários rastreáveis; revisão de papéis; contas padrão/de teste removidas em produção.
- **5.17 Informação de autenticação** — senhas com hash forte (argon2/bcrypt), política de senha,
  nada de senha padrão versionada (ex.: credenciais em `docker-compose.yml`/README).
- **8.2 Acesso privilegiado** — papéis administrativos separados, ações administrativas registradas.
- **8.5 Autenticação segura** — tokens/sessões com expiração, assinatura forte, cookies `HttpOnly`/
  `Secure`/`SameSite`, proteção contra força bruta (limite de tentativas), MFA para administradores.

### Criptografia e dados
- **8.24 Uso de criptografia** — algoritmos atuais, chaves geradas com CSPRNG, guardadas fora do
  código, TLS no transporte, rotação possível.
- **5.33 Proteção de registros / 5.34 Privacidade e dados pessoais** — integridade de trilhas e logs;
  remeta os detalhes de dados pessoais à skill `revisao-lgpd`.
- **8.10 Exclusão de informação / 8.11 Mascaramento de dados / 8.12 Prevenção de vazamento** —
  expurgo, mascaramento na exibição e exportação, dados sensíveis fora de respostas de erro/logs.
- **8.13 Backup** — evidência de rotina de backup e teste de restauração (geralmente "Fora do
  alcance" ou "A confirmar").

### Registro e monitoramento
- **8.15 Registro de eventos (logging)** — eventos de segurança (login, falha de login, mudança de
  permissão, exportação, publicação) registrados com quem/quando/onde; logs protegidos contra
  alteração; sem segredos nos logs.
- **8.16 Atividades de monitoramento** — alertas ou consultas para comportamento anômalo.
- **8.17 Sincronização de relógio** — timestamps em UTC/fuso explícito vindos do servidor.

### Desenvolvimento seguro
- **8.25 Ciclo de vida de desenvolvimento seguro / 8.27 Arquitetura segura** — revisão de código,
  ADRs de segurança, separação de responsabilidades, menor privilégio entre serviços.
- **8.26 Requisitos de segurança da aplicação** — validação de entrada (schemas), tratamento de erros
  sem vazamento, cabeçalhos de segurança (CSP, HSTS, X-Content-Type-Options, frame-ancestors), CORS
  restrito, limites de tamanho de upload/requisição.
- **8.28 Codificação segura** — injeção (SQL cru, comandos, path traversal), XSS
  (`dangerouslySetInnerHTML`), SSRF em chamadas a URLs configuráveis (ex.: CKAN), desserialização
  insegura, uso de `eval`/`pickle`/`yaml.load`, segredos no código.
- **8.29 Testes de segurança** — testes automatizados de autorização/autenticação e de casos
  maliciosos; guardas no pre-commit/CI.
- **8.31 Separação de ambientes** — dev/teste/produção com configurações e credenciais distintas;
  modo debug/reload desligado em produção; docs da API expostas só quando intencional.
- **8.32 Gestão de mudanças** — migrações versionadas, branches/PR, registro de decisões.
- **8.33 Informação de teste** — testes e fixtures só com dados fictícios ou públicos.
- **8.4 Acesso ao código-fonte** — nada sensível versionado; `.gitignore` cobre `.env`, chaves,
  dumps.

### Componentes, configuração e fornecedores
- **8.8 Gestão de vulnerabilidades técnicas** — dependências fixadas com versão, sem pacotes
  abandonados/vulneráveis conhecidos, imagens base de Docker atualizadas e fixadas.
- **8.9 Gestão de configuração** — configuração segura por padrão, containers sem root, portas
  mínimas expostas, sem `privileged`, variáveis de ambiente obrigatórias validadas na inicialização.
- **8.20–8.22 Segurança de redes / serviços de rede / segregação** — serviços internos (banco,
  Redis, Solr) não expostos publicamente; proxy reverso confiável configurado.
- **5.19–5.23 Fornecedores e serviços em nuvem** — integrações externas (IA comercial, APIs)
  identificadas, com dados mínimos enviados e chave segregada.
- **5.9 Inventário de ativos** — lista de dependências/serviços identificável (lockfiles, compose).

Controles de pessoas (tema 6) e físicos (tema 7) e a maior parte do tema 5 (políticas, papéis,
fornecedores, incidentes, continuidade) ficam **Fora do alcance do código** — liste-os de forma
resumida no relatório como itens a tratar no SGSI do órgão, sem avaliá-los.

## Severidade dos "Não atende" / "Atende parcialmente"

- **Alta** — falha explorável ou exposição (rota sem autorização, segredo versionado, injeção,
  serviço interno exposto, log alterável).
- **Média** — controle ausente sem exploração demonstrada (sem MFA admin, sem rate limit, sem
  cabeçalhos de segurança, dependências sem versão fixa).
- **Baixa** — melhoria de evidência/documentação.

## Formato do relatório

```markdown
# Revisão ISO/IEC 27001:2022 / 27002:2022 — <escopo> — <data>

> Avaliação automatizada dos controles evidenciáveis em código. Não é auditoria de certificação;
> controles organizacionais, de pessoas e físicos dependem do SGSI do órgão.

## Resumo
<2–4 frases + contagem: Atende / Parcial / Não atende / Fora do alcance>

## Matriz de controles
| Controle | Situação | Evidência | Severidade |
|---|---|---|---|
| 8.5 Autenticação segura | Parcial | `backend/app/core/seguranca.py:40` | Média |

## Lacunas (detalhe, por severidade)
### [ALTA] 8.28 — <título>
- **Onde:** `arquivo:linha`
- **O que falta:** <descrição>
- **Correção sugerida:** <ação>

## Fora do alcance do código (tratar no SGSI)
## A confirmar (ambiente de produção)
```

Mostre no chat; grave em arquivo só se o usuário pedir.
