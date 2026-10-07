# ADR-0011 — Montar o contexto do Assistente no backend, sem banco vetorial

| | |
|---|---|
| **Status** | Aceita |
| **Tipo** | Técnica |
| **Data da decisão** | 30/09/2026 |
| **Data do registro** | 07/10/2026 (registro retroativo) |
| **Decisores** | Victor Hugo Benatti |
| **Consultados** | SECTI (31/08); orientador (01/10) |
| **Origem** | Sessão de 30/09 |
| **Afeta** | Módulo `assistente`; US28 |

## Contexto
O Assistente responde perguntas da gerência sobre órgãos, bases e prazos. Em 31/08 a SECTI informou
que um banco vetorial exigiria conexão externa, e o PGP registra a falta de infraestrutura como risco.
Em 01/10 o orientador reforçou que o Gemini seria excelente para esse chatbot.

## Critérios de decisão
1. Não inventar números (alucinação inaceitável em resposta à alta gestão).
2. Sem infraestrutura nova.
3. Respeitar escopo de órgão e não expor achados LGPD.

## Opções consideradas

### RAG com banco vetorial (pgvector, Qdrant)
- **Prós:** responde sobre textos livres e descrições.
- **Contras:** infraestrutura extra indisponível; a maior parte das perguntas é numérica e estruturada.

### Chamada de funções (function calling) sobre a API da solução
- **Prós:** o modelo escolhe a consulta certa; escala para perguntas variadas.
- **Contras:** suporte varia entre modelos locais; mais complexo de testar.

### Texto para SQL
- **Prós:** perguntas abertas.
- **Contras:** risco de consulta errada ou vazamento entre órgãos; difícil de auditar.

### Contexto determinístico montado pelo backend
- **Prós:** o backend calcula os fatos e o modelo só redige; escopo de órgão aplicado no código.
- **Contras:** cobre só as perguntas previstas.

## Decisão
Contexto determinístico agora. Evoluir para chamada de funções se as perguntas da gerência
extrapolarem o contexto.

## Consequências
- **Positivas:** funciona com qualquer modelo; sem infraestrutura nova.
- **Negativas e riscos:** o contexto precisa ser enriquecido à medida que os eixos ficarem prontos.

## Validação
Teste com perguntas reais da GEDA quando o Eixo 1 estiver integrado.

## Revisões
| Data | Revisão | Autor |
|---|---|---|
| 30/09/2026 | Contexto passa a respeitar o escopo de órgão do usuário | Victor |
