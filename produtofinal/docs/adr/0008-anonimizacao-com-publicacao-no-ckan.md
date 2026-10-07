# ADR-0008 — Incluir a anonimização no escopo, publicando no CKAN só após aprovação humana

| | |
|---|---|
| **Status** | Aceita (publicação em produção depende de autorização formal — PBI-95) |
| **Tipo** | Escopo |
| **Data da decisão** | 22/09/2026 (D2) |
| **Data do registro** | 07/10/2026 (registro retroativo; também consta no Backlog v2) |
| **Decisores** | Squad 2 |
| **Consultados** | Paloma Peixoto e Júnior Costa (20/08 e 17/09) |
| **Apoio de IA** | — |
| **Origem** | Reunião 1 (20/08), Reunião 3 (17/09), daily de 22/09 |
| **Afeta** | Módulo `lgpd`; `integrations/ckan/writer.py`; US26 |

## Contexto
Em 20/08 a Paloma disse que o ideal seria identificar o dado pessoal para analisar e então tratar
(anonimizar). Em 17/09 o Júnior perguntou se a expectativa era só identificar ou também anonimizar
depois da revisão humana; a Paloma citou a regra interna para CPF (ocultar os três primeiros e os dois
últimos dígitos). O PGP previa a solução somente leitura.

## Critérios de decisão
1. Resolver o problema por inteiro, sem novo ciclo manual com o órgão.
2. Nenhuma alteração no portal sem decisão humana registrada.
3. Credenciais de escrita da GEDA, nunca dos residentes.

## Opções consideradas

### Só sinalizar e gerar relatório
- **Prós:** somente leitura; risco zero no portal.
- **Contras:** a correção continua manual e lenta.

### Anonimizar e devolver o arquivo à GEDA para publicar manualmente
- **Prós:** sem escrita automatizada no portal.
- **Contras:** passo manual sujeito a erro e atraso.

### Anonimizar e publicar no CKAN após aprovação do gestor
- **Prós:** tratamento completo; trilha de quem aprovou e quando; reversível com cópia do original.
- **Contras:** escrita em produção; exige credencial, autorização formal e cuidado com a cópia do original.

## Decisão
Publicar após aprovação, com prévia, cópia de segurança e reversão. A coleta e o monitoramento
continuam somente leitura; essa é a única escrita no CKAN.

## Consequências
- **Positivas:** fecha o ciclo identificar → revisar → corrigir.
- **Negativas e riscos:** recursos hospedados como link externo não podem ser corrigidos assim.
  Salvaguardas no código: escrita desligada por padrão (`GDA_CKAN_WRITE_ENABLED=false`), só para
  recursos `upload`, permissão `lgpd.aprovar_correcao`.

## Validação
Autorização formal CGE-GO/SECTI antes de ligar em produção (PBI-95).

## Revisões
| Data | Revisão | Autor |
|---|---|---|
| 30/09/2026 | Salvaguardas implementadas em `CkanWriter` e permissão `lgpd.aprovar_correcao` criada | Victor / Claude |
