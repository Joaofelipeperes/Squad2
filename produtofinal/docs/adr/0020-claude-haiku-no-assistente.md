# ADR-0020 — Usar um modelo Claude da família Haiku como modelo principal do Assistente GEDA

| | |
|---|---|
| **Status** | Em análise |
| **Tipo** | Técnica |
| **Data da decisão** | pendente (proposta em 23/10/2026) |
| **Data do registro** | 23/10/2026 |
| **Decisores** | Paloma Peixoto (GEDA), por envolver custo de serviço comercial; time do Eixo 2 propõe |
| **Consultados** | — (a consultar: SECTI/LIGO sobre a chave do Gemini, que venceu o limite de 19/10) |
| **Origem** | Sessão de trabalho de 23/10/2026: pedido de implementar o chatbot com um modelo barato do Claude |
| **Afeta** | Módulos `ia` (novo adaptador `anthropic`) e `assistente`; US28; ADR-0002, ADR-0011 |

## Contexto
O Assistente (US28) precisa de um modelo comercial ou local vinculado na tela Modelos de IA. A chave
do Gemini prometida pela SECTI tinha limite de decisão em 19/10 e não chegou; sem ela, a alternativa
registrada era um modelo local, que exige servidor (pendência com a SECTI). O time propôs testar um
modelo barato e rápido da Anthropic. O PGP prefere ferramentas gratuitas ou de código aberto, então
usar um serviço pago é decisão do cliente.

O Assistente não recebe dado pessoal (ADR-0011: só metadados públicos do portal e contagens), por
isso pode usar modelo externo sem violar a política da ADR-0002.

## Critérios de decisão
1. Respostas rápidas no chat (latência baixa).
2. Custo baixo e previsível por pergunta.
3. Não depender de infraestrutura nova.
4. Trocar de modelo sem alterar código (ADR-0002).

## Opções consideradas

### Opção A — Gemini Flash com a chave da SECTI
- **Prós:** orientação original da SECTI (31/08) e do orientador (01/10); custo assumido pelo Estado.
- **Contras:** a chave não chegou no prazo; sem data prevista.

### Opção B — Claude Haiku (API da Anthropic)
- **Prós:** modelo barato e rápido; o contexto do Assistente é curto (poucos milhares de tokens por
  pergunta), então o custo por pergunta é pequeno; funciona hoje com uma chave própria.
- **Contras:** serviço pago, com cobrança fora do contrato do Estado; exige cadastrar cartão/conta;
  dados (metadados públicos) saem da infraestrutura do Estado.

### Opção C — Modelo local (Ollama/vLLM, ex.: Qwen do LIGO)
- **Prós:** sem custo por uso; nada sai da infraestrutura.
- **Contras:** precisa de servidor com recursos (pendência com a SECTI); em CPU as respostas ficam
  lentas para um chat.

## Decisão
Ainda não tomada. O código foi preparado para as três opções: o adaptador `anthropic` foi incluído
na camada de IA (sem SDK, mesmo padrão dos demais), e qual modelo atende o Assistente continua sendo
uma escolha na tela Modelos de IA. Recomendação do time: Opção B como principal enquanto a chave do
Gemini não chega, com um perfil local como contingência quando houver servidor.

## Consequências
- **Positivas:** o Assistente pode ser demonstrado com modelo real sem esperar a SECTI; trocar
  depois para Gemini ou modelo local é só mudar o vínculo na tela.
- **Negativas e riscos:** custo mensal a acompanhar (o uso fica registrado em `ia_uso`, com tokens
  de entrada e saída); a política impede, por construção, que esse perfil atenda a tarefa sensível
  `classificacao_dp`.

## Validação
Apresentar à Paloma no checkpoint de 26/10/2026 com estimativa de custo mensal a partir do `ia_uso`
dos testes.

## Revisões
| Data | Revisão | Autor |
|---|---|---|
| 27/10/2026 | Renumerada de ADR-0017 para ADR-0020 no merge com a `desenvolvimento` (a ADR-0017 de lá trata do modo desenvolvimento no Docker). Sem mudança na decisão | Luiza |
