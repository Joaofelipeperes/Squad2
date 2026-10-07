# ADR-0005 — Controlar acesso por papéis e permissões, com catálogo central e escopo por órgão

| | |
|---|---|
| **Status** | Aceita |
| **Tipo** | Técnica |
| **Data da decisão** | 30/09/2026 |
| **Data do registro** | 30/09/2026 |
| **Decisores** | Victor Hugo Benatti |
| **Consultados** | — (distribuição dos papéis padrão a validar com a Paloma) |
| **Apoio de IA** | Claude: implementou catálogo, portão, guarda de subida, tela e testes; identificou e corrigiu falha de escopo no Assistente |
| **Origem** | Sessão de 30/09; commit `26878bb` |
| **Afeta** | Módulo `acesso` e todos os demais; US24 |

## Contexto
A primeira versão tinha três perfis fixos (consulta, gestor, admin). Isso não atendia: telas precisam
ser liberadas por usuário (o painel é da gerência; servidores de órgãos só lidam com dados do próprio
órgão), e ações dentro de uma tela também variam (ver, atualizar dados, aprovar anonimização). As
regras precisavam ficar num lugar só e valer em toda chamada.

## Critérios de decisão
1. Segurança: nenhuma rota ou tela sem verificação.
2. Regra em um único lugar.
3. Revogação imediata.
4. Administração possível pela própria GEDA.

## Opções consideradas

### Opção A — Perfis hierárquicos fixos (versão inicial)
- **Prós:** simples.
- **Contras:** não expressa "vê o painel, mas não vê LGPD"; qualquer variação exige código.

### Opção B — Permissões atribuídas direto ao usuário
- **Prós:** flexibilidade máxima.
- **Contras:** difícil de administrar com ~48 órgãos e equipes.

### Opção C — RBAC: usuário → papéis → permissões `<modulo>.<acao>`, catálogo central
- **Prós:** regra única em `permissoes.py`; papéis administrados na tela; escopo de órgão por usuário;
  verificável automaticamente.
- **Contras:** consulta leve ao banco a cada requisição.

### Opção D — Permissões dentro do token JWT
- **Prós:** sem consulta ao banco.
- **Contras:** revogar só vale quando o token expira (até 8 h).

### Opção E — Biblioteca de autorização (Casbin, Oso)
- **Prós:** modelos de política poderosos.
- **Contras:** mais um conceito para o time; a necessidade cabe em ~150 linhas próprias e testadas.

## Decisão
Opção C, com permissões lidas do banco a cada requisição. Garantias automáticas: a API não sobe com
rota sem controle de acesso; tela sem `permissao` não compila; o TypeScript das permissões é gerado
do catálogo Python.

## Consequências
- **Positivas:** toda tela e ação passa pelo mesmo portão; revogação imediata.
- **Negativas e riscos:** o papel "Órgão publicador" antecipa um uso fora do escopo atual (módulo
  `envio`, não comprometido).

## Validação
Validar com a Paloma a distribuição dos papéis padrão (matriz em `docs/modulos/acesso.md`).

## Revisões
| Data | Revisão | Autor |
|---|---|---|
| 30/09/2026 | Módulo `auth` renomeado para `acesso`; CLI passa a usar `--papel` | Victor / Claude |
| 30/09/2026 | Assistente passa a respeitar o escopo de órgão ao montar o contexto (falha encontrada na revisão) | Victor / Claude |
| 07/10/2026 | Reescrita no modelo de ADR com prós e contras por opção | Victor / Claude |
