# ADR-0009 — Definir a fonte técnica da rastreabilidade de mudanças (US29)

| | |
|---|---|
| **Status** | Em análise |
| **Tipo** | Técnica |
| **Data da decisão** | aberta em 22/09/2026; decisão prevista no PBI-70 |
| **Data do registro** | 07/10/2026 |
| **Decisores** | João Felipe Peres Lima (responsável pela US29) |
| **Consultados** | SECTI (31/08) |
| **Origem** | Respostas da SECTI (31/08); daily de 22/09; reunião com o orientador (01/10) |
| **Afeta** | Módulos `rastreabilidade`, `inventario`; US14, US15, US29 |

## Contexto
Hoje uma exclusão ou alteração no portal não deixa rastro para a GEDA. A SECTI informou em 31/08 que
o CKAN registra log de tudo que altera seu banco, mantido desde o início, mas que o log não guarda o
diff completo e que o acesso exige permissão alta (superusuário); os arquivos substituídos são
sobrescritos, e há um repositório não oficial com histórico (Airflow). Em 22/09 o João relatou que a
extensão de auditoria escolhida era incompatível com o CKAN 2.9.5 e que outra testada não registrava
as alterações de linha e coluna.

## Critérios de decisão
1. Funcionar no CKAN 2.9.5 sem depender de alteração não autorizada.
2. Registrar inclusão, alteração, privação e exclusão com data.
3. Prazo.

## Opções consideradas

### Opção A — Extensão de auditoria no CKAN
- **Prós:** registro na origem, inclusive de alterações finas.
- **Contras:** a primeira testada é incompatível com o CKAN 2.9.5; depende de instalação pela SECTI.

### Opção B — Activity stream da API do CKAN
- **Prós:** histórico oficial, com autor e data.
- **Contras:** exige permissão de superusuário; não traz o diff completo do conteúdo.

### Opção C — Diff entre coletas diárias (fotografias da solução)
- **Prós:** independe da SECTI; já viável (`dataset_snapshot` gravado a cada coleta).
- **Contras:** granularidade diária; não sabe quem alterou; não vê mudanças desfeitas no mesmo dia.

## Decisão
Pendente. A Opção C está implementável hoje e pode ser a base, com A ou B como complemento se a SECTI
liberar acesso.

## Consequências
A US15 (histórico com autor) só é viável com A ou B.

## Validação
Decisão do João com o time; confirmação de acesso com Wagner (SECTI).

## Revisões
| Data | Revisão | Autor |
|---|---|---|
| 01/10/2026 | Na reunião com o orientador, o time relatou que a SECTI poderia liberar a extensão. Confirmar formalmente qual extensão e em que prazo antes de decidir | Victor |
