# ADR-0034 — Backups internos do banco gerados pelo `pg_dump` e guardados cifrados numa tabela do próprio banco

| | |
|---|---|
| **Status** | Aceita |
| **Tipo** | Técnica |
| **Data da decisão** | 10/11/2026 |
| **Data do registro** | 10/11/2026 |
| **Decisores** | João (Base comum), que pediu a funcionalidade e escolheu as opções abaixo |
| **Consultados** | — (SECTI/CGE-GO ainda não opinaram sobre a política de backup; ver Validação) |
| **Origem** | Sessão de trabalho de 10/11/2026 |
| **Afeta** | Novo módulo `backup`; `backend/Dockerfile`; `core/crypto.py`; `core/config.py`; `app/cli.py`; `deploy/README.md` |

## Contexto
O banco `gda` da aplicação (inventário, achados LGPD, decisões humanas, PDA, usuários, log de acesso)
não tinha rotina automática de backup: o `deploy/README.md` só descrevia um `pg_dump` manual. Foi
pedido um backup interno de **todo o banco do ProdutoFinal** (não o banco do CKAN, que o projeto não
toca), ainda sem tela, em duas categorias:

- **Diário** — à 00:00 todos os dias, guardado por até 7 dias.
- **Mensal** — à 00:00 do **dia 1** de cada mês, cobrindo o mês inteiro que terminou, guardado por 1 ano
  (365 dias).

Os backups ficam "no banco". O agendamento segue a [ADR-0012](0012-agendamento-em-worker-proprio.md)
(worker próprio), e o acesso ao banco segue a [ADR-0019](0019-dao-exclusao-logica-e-auditoria.md).

## Critérios de decisão
1. Confiabilidade da restauração: um backup só vale se restaurar.
2. Atender o pedido (guardado no banco) com o mínimo de infraestrutura nova.
3. Respeitar as regras do projeto: banco só por DAO, exclusão lógica, tudo documentado.
4. Proteger o conteúdo (hashes de senha, dados de acesso, achados): backup é cópia de dado sensível.
5. Manter a possibilidade de, depois, guardar também fora do banco, sem refatorar.

## Opções consideradas — onde guardar

### A — Só na tabela `backup_copia`, no mesmo PostgreSQL (escolhida)
- **Prós:** atende o pedido literal; zero infraestrutura nova; gravação e consulta pelo DAO como o resto;
  nenhum volume ou credencial a mais.
- **Contras:** não protege da perda do volume `pgdata` nem de corrupção do banco inteiro, porque o
  backup mora junto com os dados; cada cópia ocupa espaço no banco (até 19 simultâneas: 7 diárias + 12
  mensais); um backup do volume por fora carrega as cópias internas dentro dele.

### B — Tabela + cópia em volume separado (`backups` no compose)
- **Prós:** cobre melhor a perda do `pgdata` se o volume ficar em outro disco.
- **Contras:** infraestrutura nova no `docker-compose.prod.yml`; o ganho só existe se o volume estiver
  mesmo em outro disco, o que o projeto não controla (servidor da UFG/SECTI).

### C — Envio para destino externo (rede da SECTI, armazenamento de objetos)
- **Prós:** protege de verdade contra perda do servidor.
- **Contras:** depende de decisão, destino e credenciais da SECTI/CGE-GO, que ainda não existem.

## Opções consideradas — como gerar

### 1 — `pg_dump -Fc` (PostgreSQL) e `sqlite3.backup()` (dev/testes) (escolhida)
- **Prós:** snapshot consistente nativo, com estrutura, dados, sequences e constraints; já sai
  compactado; restauração padrão com `pg_restore`, conhecida pela SECTI; menos código nosso para
  errar e só descobrir na hora de restaurar.
- **Contras:** exige o cliente do PostgreSQL 16 na imagem do backend (acréscimo no `Dockerfile`, pelo
  repositório oficial PGDG, para a versão casar com o servidor `postgres:16`); o caminho do PostgreSQL
  só é exercitado de ponta a ponta num ambiente com PostgreSQL (os testes automáticos cobrem a montagem
  do comando, o tratamento de erro e a agenda; o dump em si é testado em SQLite).

### 2 — Dump lógico escrito em Python (leitura de todas as tabelas e serialização)
- **Prós:** sem mudar o `Dockerfile`; igual em SQLite e PostgreSQL; fácil de testar.
- **Contras:** só dados (a estrutura dependeria do Alembic); ordem de chaves estrangeiras, sequences,
  tipos e consistência de leitura ficam por nossa conta; bug sutil só aparece na restauração.

## Decisão
- **Armazenamento: opção A.** Tabela `backup_copia`, uma linha por tipo e referência, com o dump
  **cifrado** (Fernet, `GDA_ENCRYPTION_KEY`) em coluna binária carregada só sob demanda, tamanho e
  `sha256` do dump, formato, datas e, se falhar, o erro. A gravação passa só pelo `BackupDao`.
  A decisão deixa claro o limite: **não substitui** o backup externo do `deploy/README.md`.
- **Geração: opção 1.** `pg_dump -Fc` com `--exclude-table-data=backup_copia` (os backups não entram
  uns nos outros; a estrutura da tabela entra), senha por `PGPASSWORD`, nunca na linha de comando.
  Em SQLite, `sqlite3.backup()` compactado, limpando `backup_copia` na cópia. O backup inclui os
  registros excluídos logicamente: é o banco inteiro.
- **Agenda (no worker, fuso `America/Sao_Paulo`):** `backup.diario` `0 0 * * *`; `backup.mensal`
  `0 0 1 * *` (à 00:00 do dia 1, referência = mês que terminou, `AAAA-MM`); `backup.limpeza` `0 1 * * *`.
  Cada tipo é idempotente por referência: repetir a execução não duplica, e uma referência com erro é
  reaproveitada na tentativa seguinte. Falha vira registro `situacao="erro"` e log, nunca derruba o
  worker.
- **Retenção:** diário 7 dias, mensal 365 dias (`GDA_BACKUP_RETENCAO_*`). Vencido = **exclusão lógica**
  (regra da ADR-0019 mantida, nada é apagado fisicamente) com liberação do `conteudo`, que é o que ocupa
  espaço; a linha de metadados permanece como histórico.
- **Sem interface por enquanto:** o módulo `backup` não tem rota nem tela. Para operar, a CLI:
  `backups`, `backup-agora`, `exportar-backup` e `restaurar-backup` (este só no PostgreSQL, num banco
  de destino já criado; restaurar no banco em uso exige `--sobrescrever`).
- `core/crypto.py` ganha `encrypt_bytes`/`decrypt_bytes` (mesma chave mestra, sem nova configuração).

## Consequências
- **Positivas:** backups automáticos e conferíveis (`sha256`), cifrados, sem infraestrutura nova além do
  cliente do PostgreSQL; restauração com a ferramenta padrão; evolução para volume ou destino externo
  sem mexer no agendamento.
- **Negativas e riscos:**
  - Perda do volume `pgdata` leva os backups junto — tratado mantendo o backup externo documentado no
    `deploy/README.md` e registrando o limite aqui; destino externo fica para decisão da SECTI/CGE-GO.
  - Abrir um backup exige a `GDA_ENCRYPTION_KEY` (volume `gda_segredos`); sem ela a cópia é ilegível.
    O backup do volume de segredos já era exigido pelo `deploy/README.md`.
  - A Fernet cifra em memória: adequado ao tamanho atual do banco (poucas dezenas de MB). Se o banco
    crescer a ponto de pesar, trocar para cifra em fluxo ou mover o armazenamento (opções B/C).
  - A imagem do backend fica maior e o *build* passa a depender do repositório PGDG.
  - Se o worker ficar parado em toda a janela da 00:00, o backup daquela referência não é gerado
    (o worker tolera até 1 h de atraso, `misfire_grace_time`).

## Validação
Validar com a SECTI/CGE-GO (Paloma, Wagner): retenção (7 dias / 1 ano), necessidade de destino externo
e quem acessa os backups. Testar o `pg_dump`/`pg_restore` ponta a ponta em PostgreSQL no primeiro
ambiente com Docker (homologação ou servidor da UFG), antes de contar com ele.

## Revisões
| Data | Revisão | Autor |
|---|---|---|
| 10/11/2026 | Decisão inicial (o mensal é gerado à 00:00 do dia 1 para cobrir o mês inteiro) | João |
