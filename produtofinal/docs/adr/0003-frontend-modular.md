# ADR-0003 — Construir o frontend em React reaproveitando o CSS do Protótipo V1

| | |
|---|---|
| **Status** | Aceita |
| **Tipo** | Técnica |
| **Data da decisão** | 30/09/2026 |
| **Data do registro** | 30/09/2026 |
| **Decisores** | Victor Hugo Benatti |
| **Consultados** | CGE-GO validou o visual do protótipo em 17/09 (ver ADR-0007) |
| **Origem** | Sessão de 30/09 |
| **Afeta** | `frontend/`; PBI-66, PBI-100 |

## Contexto
O protótipo HTML estático foi aprovado pela CGE-GO e é a referência oficial das telas. Era preciso
transformá-lo em aplicação com rotas, login e dados reais sem perder o visual aprovado.

## Critérios de decisão
1. Fidelidade ao visual validado.
2. Telas como módulos independentes, com controle de acesso.
3. Funcionar em rede do Estado com saída restrita.

## Opções consideradas

### Opção A — React + TypeScript + Vite, importando o CSS do protótipo sem alteração
- **Prós:** fidelidade total; componentes reproduzem a mesma marcação; TypeScript estrito pega erros
  cedo; fontes e ícones empacotados no build (sem CDN).
- **Contras:** o CSS do protótipo não foi escrito como design system (classes globais).

### Opção B — React + biblioteca de componentes (MUI, shadcn/ui)
- **Prós:** componentes prontos e acessíveis.
- **Contras:** refazer o visual aprovado, com risco de divergência; mais dependências.

### Opção C — Evoluir o HTML estático com JavaScript puro
- **Prós:** nenhuma ferramenta de build.
- **Contras:** um arquivo de 2.200 linhas não escala para 12 telas, perfis e dados reais.

### Opção D — Renderização no servidor (templates Jinja/HTMX)
- **Prós:** uma linguagem só.
- **Contras:** gráficos e interações do protótipo ficam mais trabalhosos; mistura front e back.

## Decisão
Opção A. Cada tela é uma pasta com manifesto (`index.ts`); `registry.ts` monta menu e rotas; ajustes
visuais ficam em `overrides.css`, e o CSS do protótipo não é editado.

## Consequências
- **Positivas:** a conferência final contra o protótipo (PBI-100) é direta.
- **Negativas e riscos:** classes globais exigem cuidado com conflitos; mitigado por `overrides.css`.

## Validação
Visual validado pela CGE-GO em 17/09; implementação a validar pelo time.

## Revisões
| Data | Revisão | Autor |
|---|---|---|
| 30/09/2026 | Manifesto de tela passa a exigir `permissao` e `modulo` (ADR-0005) | Victor |
| 07/10/2026 | Reescrita no modelo de ADR com prós e contras por opção | Victor |
