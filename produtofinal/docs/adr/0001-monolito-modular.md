# ADR-0001 — Construir um monólito modular com FastAPI (Python) e React (TypeScript)

| | |
|---|---|
| **Status** | Aceita |
| **Tipo** | Técnica |
| **Data da decisão** | 30/09/2026 |
| **Data do registro** | 30/09/2026 |
| **Decisores** | Victor Hugo Benatti (coordenação e arquitetura) |
| **Consultados** | — (validação com o time pendente) |
| **Origem** | Sessão de arquitetura de 30/09; commit `c6b4020` |
| **Afeta** | Todo o repositório; PBI-05 (US4) |

## Contexto
O protótipo HTML validado em 17/09 precisava virar um sistema com backend próprio para coletar o CKAN,
processar dados pessoais e servir várias telas por perfil. Restrições: quatro residentes em dedicação
parcial, dois eixos em paralelo, entrega em 02/12/2026, só ferramentas gratuitas (PGP v2) e
infraestrutura estadual sem contêineres. A GEDA já usa Python, e o CKAN é Python.

## Critérios de decisão
1. Prazo e curva de aprendizado do time.
2. Permitir que os eixos trabalhem em paralelo sem conflito.
3. Custo zero e implantação leve.
4. Manutenção possível pela CGE-GO após a Residência.

## Opções consideradas

### Opção A — Monólito modular: FastAPI + SQLAlchemy + React/TS
- **Prós:** um só deploy e um só banco; módulos com fronteira clara permitem trabalho paralelo;
  FastAPI gera a documentação OpenAPI usada como contrato entre front e back; Python alinhado à GEDA e
  ao CKAN; React é a tecnologia de frontend com mais material de apoio.
- **Contras:** duas linguagens no repositório; autenticação e administração precisam ser escritas
  (não vêm prontas).

### Opção B — Django + Django REST Framework
- **Prós:** autenticação, ORM, migrações e painel de administração prontos.
- **Contras:** mais convenções para aprender em pouco tempo; acoplamento maior entre camadas; o painel
  administrativo pronto não segue o visual aprovado no protótipo.

### Opção C — Microsserviços por eixo
- **Prós:** isolamento máximo entre os eixos.
- **Contras:** custo de deploy, observabilidade e integração incompatível com o prazo e com a
  infraestrutura disponível.

### Opção D — Node.js (NestJS) com TypeScript nas duas pontas
- **Prós:** uma linguagem só.
- **Contras:** afasta do ecossistema Python da GEDA e do CKAN; bibliotecas de dados (pandas) e de
  leitura de planilhas são mais maduras em Python, o que pesa no Eixo 2.

## Decisão
Opção A. Atende o prazo com o menor número de peças e mantém o código em Python, onde a CGE-GO tem
mais condição de manter. Derivada: **SQLAlchemy síncrono** — o ganho do modo assíncrono é irrelevante
para ~450 datasets e poucos usuários, e a depuração fica mais simples (o FastAPI executa rotas
síncronas em thread pool).

## Consequências
- **Positivas:** um deploy; contrato de API documentado; módulo grande pode ser extraído depois.
- **Negativas e riscos:** o time precisa dominar Python e TypeScript; mitigado pelos guias em `docs/`
  e pelo esqueleto de cada módulo.

## Validação
Validar com o time (em especial João, responsável pelo PBI-05) e apresentar as alternativas à Paloma,
conforme orientação de 01/10.

## Revisões
| Data | Revisão | Autor |
|---|---|---|
| 07/10/2026 | Reescrita no modelo de ADR com prós e contras por opção; decisão inalterada | Victor |
