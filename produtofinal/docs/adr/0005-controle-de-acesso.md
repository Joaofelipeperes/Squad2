# ADR 0005 — Controle de acesso por papéis e permissões, com catálogo central

**Status:** proposta · **Data:** 30/09/2026

## Contexto
A primeira versão tinha três perfis fixos (consulta, gestor, admin). Isso não atende: telas
precisam ser liberadas por usuário (o painel é da gerência; servidores de órgãos estaduais só
enviam dados do próprio órgão), e ações dentro de uma tela também variam (ver × atualizar dados ×
aprovar anonimização). As regras precisam ficar num único lugar e ser aplicadas em toda chamada.

## Decisão
- **RBAC:** usuário → papéis → permissões no formato `<modulo>.<acao>`, onde `<modulo>.acessar`
  libera ver o módulo.
- **Catálogo único** em `backend/app/core/permissoes.py`; o frontend recebe tipos gerados dele.
- **Portão único** em `backend/app/core/deps.py`. Toda rota declara `require`, `require_qualquer`,
  `autenticado` ou `publico`; a aplicação não inicia se faltar.
- **Escopo de órgão** por usuário (`orgao_id`), aplicado com `filtrar_por_orgao`/`exigir_mesmo_orgao`.
- Papéis padrão criados na subida; a GEDA pode criar papéis e ajustar permissões pela tela.
- Permissões lidas do banco a cada requisição, não embutidas no token.

## Alternativas consideradas
- **Perfis hierárquicos fixos:** simples, mas não expressa "vê o painel e não vê LGPD".
- **Permissões direto no usuário, sem papéis:** flexível, porém difícil de administrar com ~48 órgãos.
- **Permissões no JWT:** evita consulta ao banco, mas a revogação só valeria quando o token expirasse.
- **Biblioteca externa (Casbin, Oso):** poderosa, mas mais um conceito para o time aprender; a
  necessidade atual cabe em ~150 linhas próprias e testadas.

## Consequências
Cada requisição faz uma consulta leve de papéis (irrelevante para o volume do projeto). Toda
permissão nova passa por um único arquivo, com geração do TypeScript e atualização da matriz em
`docs/modulos/acesso.md`. O papel Órgão publicador antecipa um uso fora do escopo atual (ver
`docs/modulos/envio.md`).
