# ADR-0014 — Documentar cada módulo num Markdown versionado junto ao código, com verificação automática

| | |
|---|---|
| **Status** | Aceita |
| **Tipo** | Processo |
| **Data da decisão** | 30/09/2026 |
| **Data do registro** | 07/10/2026 (registro retroativo) |
| **Decisores** | Victor Hugo Benatti |
| **Consultados** | Orientador (01/10): a documentação é evidência da etapa de construção |
| **Apoio de IA** | Claude: criou o modelo, os 13 documentos, o hook e os testes |
| **Origem** | Sessão de 30/09; commit `26878bb` |
| **Afeta** | `docs/modulos/`, `CLAUDE.md`, `.githooks/`, `scripts/checar_docs_modulos.py` |

## Contexto
O desenvolvimento é assistido por IA. Sem documentação atualizada, cada sessão precisa reler o código
inteiro ou perde contexto, e o time não tem uma visão confiável de como os módulos interagem.

## Critérios de decisão
1. A documentação não pode ficar desatualizada.
2. Servir ao time, à IA e à CGE-GO após a Residência.

## Opções consideradas

### README único
- **Prós:** simples.
- **Contras:** cresce sem estrutura; ninguém sabe o que atualizar.

### Wiki ou Drive fora do repositório
- **Prós:** edição fácil.
- **Contras:** desvinculado do código e dos commits; a IA não lê.

### Só docstrings e OpenAPI
- **Prós:** junto do código.
- **Contras:** não descreve telas, interações e decisões de negócio.

### Um `MODULO.md` por módulo, no repositório, exigido por hook e testes
- **Prós:** muda no mesmo commit que o código; estrutura fixa; lido pela IA como contexto.
- **Contras:** disciplina extra a cada commit.

## Decisão
Um arquivo por módulo em `docs/modulos/`, modelo único, histórico de alterações. O hook bloqueia
commit que altera módulo sem atualizar o documento.

## Consequências
- **Positivas:** contexto confiável para a IA e para o time.
- **Negativas e riscos:** `--no-verify` permite pular o hook; mitigado pelos testes.

## Validação
Em uso desde 30/09.

## Revisões
| Data | Revisão | Autor |
|---|---|---|
| 30/09/2026 | Checagem passa a ignorar módulos removidos ou renomeados (caso da renomeação `auth` → `acesso`) | Victor / Claude |
