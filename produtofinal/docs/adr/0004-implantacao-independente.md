# ADR-0004 — Desenvolver como aplicação independente do CKAN, com regras de domínio portáveis

| | |
|---|---|
| **Status** | Aceita para o desenvolvimento · forma de entrega final em aberto (PBI-102) |
| **Tipo** | Técnica / Escopo |
| **Data da decisão** | 30/09/2026 |
| **Data do registro** | 30/09/2026 |
| **Decisores** | Victor Hugo Benatti, com o time |
| **Consultados** | SECTI (31/08); Paloma e Júnior (17/09) |
| **Origem** | Reunião 3 (17/09); sessão de 30/09 |
| **Afeta** | Arquitetura geral; US22; PBI-102 |

## Contexto
Em 31/08 a SECTI informou que só a extensão DataStore está ativa no portal e que seria possível
testar extensões da comunidade ou desenvolver uma própria. Em 17/09 a Paloma explicou que uma
ferramenta incorporada formalmente ao portal, como extensão do CKAN, precisa ser liberada para toda a
organização que mantém o CKAN e ser livre; o Júnior pediu avaliação técnica antes. Segundo o relato
do time, a análise das alternativas levou cerca de seis dias sem código, até a orientação de seguir
com o desenvolvimento.

## Critérios de decisão
1. Não bloquear o desenvolvimento por uma decisão institucional ainda aberta.
2. Não alterar o CKAN de produção sem aval da SECTI.
3. Manter as duas formas de entrega possíveis até a decisão.

## Opções consideradas

### Opção A — Extensão do CKAN (`ckanext-*`)
- **Prós:** a ferramenta aparece dentro do portal; acesso direto aos dados e ao activity stream.
- **Contras:** depende de aprovação e instalação pela SECTI; precisa ser liberada a toda a
  organização mantenedora (Paloma, 17/09); preso à versão do Python e do CKAN 2.9.5; desenvolvimento
  e testes mais lentos.

### Opção B — Aplicação independente, acessada por link ou embutida no site do portal
- **Prós:** desenvolvimento sem esperar aprovação; stack e ciclo de teste próprios; zero alteração no
  CKAN; pode ser embutida no portal depois.
- **Contras:** mais uma aplicação para hospedar; lê o CKAN pela API pública, com as limitações dela.

### Opção C — Híbrido: aplicação independente com regras portáveis
- **Prós:** tudo de B, e as regras de cálculo (`regras.py`, funções puras) podem ser reaproveitadas
  numa extensão se essa for a decisão final.
- **Contras:** disciplina extra para manter as regras sem dependência de FastAPI ou banco.

## Decisão
Opção C para desenvolver agora. A forma final de entrega (extensão × aplicação acessada pelo portal)
será decidida no PBI-102, com a CGE-GO e a SECTI.

## Consequências
- **Positivas:** o time desenvolve sem bloqueio; a decisão final continua aberta.
- **Negativas e riscos:** se a opção for extensão, confirmar a versão do Python das VMs do CKAN com a
  SECTI e ajustar a compatibilidade das `regras.py`.

## Validação
Repassar as alternativas e a escolha à Paloma (orientação do orientador em 01/10) e confirmar com
Wagner (SECTI) a viabilidade técnica de cada forma de entrega.

## Revisões
| Data | Revisão | Autor |
|---|---|---|
| 01/10/2026 | Na reunião com o orientador, o time relatou que a SECTI poderia liberar uma extensão do CKAN (ligada aos logs de alteração — ver ADR-0009). Pendente de confirmação formal | Victor |
| 07/10/2026 | Reescrita no modelo de ADR; contexto completado com as respostas da SECTI (31/08) e da Reunião 3 (17/09) | Victor |
