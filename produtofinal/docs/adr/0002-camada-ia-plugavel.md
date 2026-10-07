# ADR-0002 — Acessar IA por um gateway próprio com provedores plugáveis e política de dados sensíveis

| | |
|---|---|
| **Status** | Aceita |
| **Tipo** | Técnica |
| **Data da decisão** | 30/09/2026 |
| **Data do registro** | 30/09/2026 |
| **Decisores** | Victor Hugo Benatti |
| **Consultados** | SECTI (31/08, sobre o Gemini); LIGO/TI Central e orientador (01/10, ver Revisões) |
| **Apoio de IA** | Claude: propôs o padrão gateway + adaptadores e implementou a página de configuração |
| **Origem** | Sessão de 30/09; pedido do coordenador de alternar entre modelos locais e comerciais |
| **Afeta** | Módulos `ia`, `lgpd`, `assistente`; US11, US28 |

## Contexto
Em 31/08 a SECTI orientou focar no Gemini, com uma chave específica para a aplicação, mas a chave
não tinha prazo (limite de decisão 19/10). A varredura LGPD processa dados pessoais reais, e enviá-los
a um serviço comercial é decisão institucional. O time precisava trocar de modelo sem reescrever código.

## Critérios de decisão
1. Não depender da chave comercial para avançar.
2. Impedir, por construção, que dado pessoal vá a modelo externo.
3. Trocar de modelo sem alterar código.
4. Poucas dependências.

## Opções consideradas

### Opção A — Chamar o SDK do Gemini diretamente nos módulos
- **Prós:** mais rápido de escrever no início.
- **Contras:** amarra o projeto a um fornecedor; trocar de modelo exige mexer em cada módulo; nenhuma
  barreira contra enviar dado pessoal para fora.

### Opção B — Biblioteca de abstração (LiteLLM, LangChain)
- **Prós:** suporte pronto a dezenas de provedores.
- **Contras:** dependência grande para duas tarefas; não resolve a política de dados sensíveis nem a
  configuração pela tela; mais uma camada para o time entender.

### Opção C — Gateway próprio + adaptadores HTTP + perfis configuráveis na tela
- **Prós:** um ponto único onde a política LGPD é aplicada; modelo trocado pela interface; adaptador
  "compatível com OpenAI" cobre vLLM, LM Studio, llama.cpp e serviços comerciais; sem SDKs.
- **Contras:** código próprio para manter (~400 linhas com testes).

## Decisão
Opção C. Módulos chamam `AIGateway.chat(tarefa, ...)`; cada tarefa tem perfil principal e de
contingência; tarefa marcada como sensível só aceita perfil de execução local, verificado ao vincular,
ao editar o perfil e a cada chamada. Chaves cifradas; uso registrado sem conteúdo (PBI-35).

## Consequências
- **Positivas:** o Eixo 2 avança sem a chave; a troca de modelo vira operação de tela.
- **Negativas e riscos:** modelo local em produção exige servidor (pendência com a SECTI).

## Validação
Coordenação (30/09). Reforçada pelo orientador e pelo LIGO em 01/10.

## Revisões
| Data | Revisão | Autor |
|---|---|---|
| 01/10/2026 | LIGO/TI Central ofereceu um Qwen ajustado internamente enquanto avalia o custo do Gemini; o orientador recomendou modelo offline para classificar conteúdo (custo, latência e LGPD) e Gemini para o Assistente. Ambos cabem no desenho atual (o Qwen entra como perfil `openai_compat` ou `ollama`), sem mudança de código. Estratégia de detecção registrada na ADR-0010 | Victor / Claude |
| 07/10/2026 | Reescrita no modelo de ADR com prós e contras por opção | Victor / Claude |
