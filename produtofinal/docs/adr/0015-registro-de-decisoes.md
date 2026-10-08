# ADR-0015 — Registrar toda decisão técnica como ADR numa linha do tempo versionada

| | |
|---|---|
| **Status** | Aceita |
| **Tipo** | Processo |
| **Data da decisão** | 01/10/2026 |
| **Data do registro** | 07/10/2026 |
| **Decisores** | Victor Hugo Benatti |
| **Consultados** | Prof. Alessandro Cruvinel (01/10) |
| **Origem** | Reunião com o orientador (01/10) |
| **Afeta** | `docs/adr/`, `AGENTS.md`, `.githooks/pre-commit`, `scripts/checar_decisoes.py` |

## Contexto
Em 01/10 o orientador pediu que o time registre a jornada: as alternativas analisadas, prós e contras
e a escolha, porque isso será cobrado na avaliação da etapa de construção e dá segurança à CGE-GO. Ele
também pediu que as regras de trabalho do projeto fiquem documentadas, para demonstrar um processo
de engenharia de software disciplinado. O time reconheceu que a análise de
alternativas de setembro (extensão × aplicação, IA comercial × local) foi discutida mas não
registrada.

## Critérios de decisão
1. Rastrear quando e por que cada decisão foi tomada.
2. Mostrar alternativas e prós e contras, não só a escolha.
3. Ficar junto do código e mudar no mesmo commit.

## Opções consideradas

### Só as atas de reunião
- **Prós:** já existem.
- **Contras:** decisões técnicas do dia a dia não passam por reunião; difícil de consultar.

### Planilha de decisões (como D1–D5 no Backlog v2)
- **Prós:** visão tabular.
- **Contras:** pouco espaço para alternativas e justificativa; fora do repositório.

### ADRs em Markdown no repositório + linha do tempo
- **Prós:** formato consagrado; um arquivo por decisão; versionado; lido junto com o código.
- **Contras:** disciplina para escrever a cada decisão.

## Decisão
- Toda decisão técnica vira uma ADR no modelo `docs/adr/_MODELO.md` e entra na linha do tempo
  (`docs/adr/README.md`) no mesmo commit.
- Decisão aceita não é reescrita: fatos novos entram em Revisões; mudança de decisão gera ADR nova e
  marca a antiga como substituída.
- Decisões anteriores a 01/10 foram registradas retroativamente, com a data real e a fonte.
- Mudanças em dependências ou infraestrutura exigem ADR ou revisão no mesmo commit (hook).
- Cada ADR informa quem decidiu.

## Consequências
- **Positivas:** a jornada fica demonstrável na avaliação e para a CGE-GO.
- **Negativas e riscos:** registros retroativos dependem das atas; trechos ambíguos das transcrições
  ficam marcados como "a confirmar".

## Validação
Apresentar a linha do tempo ao orientador e repassar à Paloma as decisões tomadas pelo time sem a
participação dela (orientação de 01/10).

## Revisões
| Data | Revisão | Autor |
|---|---|---|
