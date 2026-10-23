# ADR-0009 — Definir a fonte técnica da rastreabilidade de mudanças (US29)

| | |
|---|---|
| **Status** | Aceita (opção A) |
| **Tipo** | Técnica |
| **Data da decisão** | 21/10/2026 (aberta em 22/09/2026; PBI-70) |
| **Data do registro** | 07/10/2026; decisão registrada em 21/10/2026 |
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
**Opção A — extensão de auditoria no CKAN.** A extensão `ckanext-dsaudit`, adaptada ao CKAN 2.9.5
neste repositório (pasta `ckanext-dsaudit/` na raiz, pacote para a SECTI em
`instalacao-ckan-producao/`), grava no próprio CKAN cada alteração de metadados do dataset e dos
recursos, cada troca de arquivo (com diff linha a linha) e cada alteração no DataStore, com autor e
data. O módulo `rastreabilidade` lê essas atividades pela API `dsaudit_activity_list`, ao fim de
cada coleta, e monta a linha do tempo.

Critérios atendidos: (1) funciona no CKAN 2.9.5 — testada no CKAN local do repositório com dados
reais do portal; (2) registra inclusão, alteração, privação e exclusão com data e autor; (3) já
implementada. A Opção C (diff entre coletas) fica como complemento para quando a extensão não
estiver instalada (contrato `diff_coletas`, PBI-43).

## Consequências
- A solução continua externa ao CKAN: só **lê** a auditoria, por um token configurado em
  `GDA_CKAN_AUDITORIA_API_TOKEN`.
- A API da extensão exige permissão de **editor** em cada dataset (não precisa de sysadmin). Em
  produção, o token deve ser de um usuário editor das organizações monitoradas; datasets sem
  permissão são pulados e contados na sincronização.
- No portal oficial, a rastreabilidade depende de a SECTI instalar a extensão. Antes disso, a tela
  mostra que a leitura não foi concluída.
- A US15 (histórico com autor) passa a ser viável: cada evento traz o usuário do CKAN.
- Valores de linhas de arquivos e do DataStore não são copiados para a solução (LGPD): ficam no
  CKAN; a solução guarda contagens e nomes de colunas.
- A leitura é por dataset (a API não tem listagem global): uma chamada por dataset do inventário a
  cada coleta, incremental (para no primeiro evento já conhecido).

## Validação
Decisão do João com o time; confirmação de acesso com Wagner (SECTI).

## Revisões
| Data | Revisão | Autor |
|---|---|---|
| 01/10/2026 | Na reunião com o orientador, o time relatou que a SECTI poderia liberar a extensão. Confirmar formalmente qual extensão e em que prazo antes de decidir | Victor |
| 21/10/2026 | Decidida a opção A: `ckanext-dsaudit` adaptada ao CKAN 2.9.5 como fonte; módulo `rastreabilidade` lê `dsaudit_activity_list` com token de editor (`GDA_CKAN_AUDITORIA_API_TOKEN`) ao fim de cada coleta; `docker-compose.ckan-local.yml` repassa o token no ambiente local. Instalação no portal oficial depende da SECTI | João |
| 22/10/2026 | Diff linha a linha de arquivos e do DataStore exibido na tela lendo a auditoria do CKAN no momento da consulta (`GET /eventos/{id}/diff`), sem gravar os valores na solução (LGPD, AGENTS.md regra 4). Alternativa descartada: copiar o diff para o banco da solução (duplicaria valores possivelmente pessoais). Privação passa a ser evento próprio, separado das demais mudanças da mesma gravação | João |
| 23/10/2026 | A extensão não audita o cadastro dos órgãos (descrição, imagem, campos extras); o CKAN 2.9 grava "changed organization", mas sem os campos extras e com conteúdo acessível só ao administrador. Decidido aplicar a opção C aos órgãos: fotografia do cadastro a cada coleta e evento quando muda, sem autor e com a data da coleta. Alternativa avaliada: estender a extensão para auditar órgãos (autor e data exatos), que exige alterar a extensão e nova instalação pela SECTI — fica como evolução | João |
| 23/10/2026 | Autoria das mudanças em órgãos: a comparação entre coletas continua dizendo o que mudou; quem alterou e quando passam a vir das atividades nativas do CKAN (`organization_activity_list`, lida com o token de editor) no intervalo entre as duas fotografias. Limite aceito: com mais de um autor no intervalo, não se sabe qual campo cada um mudou | João |
| 23/10/2026 | Ações em dataset que não passam pelo `package_update` (Make public/Make private/Delete em lote na organização, package_patch) não são auditadas pela extensão. Decidido (opção B, sem alterar a extensão): ler as atividades nativas do CKAN e gravar as que não têm atividade da extensão do mesmo dataset a menos de 2 s (critério medido: na edição comum as duas ficam a centésimos de segundo); o que mudou vem das versões completas guardadas pelo CKAN nas atividades nativas (`activity_data_show`, permitido ao editor). Alternativa avaliada: interceptar as ações em lote na extensão (registro na origem, exige alterar a extensão e nova instalação pela SECTI) | João |
