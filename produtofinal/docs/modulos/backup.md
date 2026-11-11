# Módulo `backup` — Backups internos do banco

| | |
|---|---|
| **Status** | Implementado (sem interface) |
| **Responsável** | João |
| **User stories** | — (infraestrutura; fora do Backlog v2, pedido da coordenação em 10/11/2026) |
| **Backend** | `backend/app/modules/backup/` |
| **Frontend** | — (sem tela por enquanto) |
| **Última atualização** | 10/11/2026 |

## Propósito
Cópia automática de todo o banco `gda` do ProdutoFinal (não o banco do CKAN), para recuperar dados
perdidos por erro lógico (dado apagado, migração ruim). Decisões e alternativas:
[ADR-0034](../adr/0034-backups-internos-do-banco-com-pg-dump.md).

## Telas
Nenhuma. A listagem e a restauração, por enquanto, são pela CLI (abaixo).

## API
Nenhuma rota (o módulo não declara `router`).

## Comandos (CLI, `python -m app.cli`)
| Comando | O que faz |
|---|---|
| `backups` | Lista os backups ativos (id, tipo, referência, situação, tamanho, validade) |
| `backup-agora diario\|mensal` | Gera o backup da referência de hoje, sem esperar o horário |
| `exportar-backup <id> <arquivo>` | Decifra, confere o `sha256` e grava o `.dump` (para `pg_restore`) ou o banco SQLite |
| `restaurar-backup <id> --banco <nome> [--sobrescrever]` | `pg_restore` num banco de destino já criado; no banco em uso exige `--sobrescrever` |

## Serviços e métodos
`service.py`:
- `executar_backup(tipo, hoje=None) -> BackupCopia` — gera o backup `diario` ou `mensal`. Idempotente por
  referência (já existe um ok → devolve ele). Falha do dump não levanta: grava `situacao="erro"` com a
  mensagem e a próxima execução da referência reaproveita a linha.
- `limpar_vencidos(agora=None) -> int` — libera o conteúdo e exclui logicamente os vencidos.
- `listar(tipo=None)`, `exportar(id, destino)`, `restaurar(id, banco_destino, sobrescrever=False)`.
- `job_diario`, `job_mensal`, `job_limpeza` — funções chamadas pelo worker.

`regras.py` (puras): `referencia_diaria`, `referencia_mensal`, `expira_em`, `sha256`, `dados_conexao`.
`gerador.py`: `gerar_dump` (`pg_dump -Fc` em PostgreSQL; `sqlite3.backup()` em SQLite), `restaurar_pg`,
`comando_pg_dump`, `comando_pg_restore`.

## Modelo de dados
`backup_copia` (única tabela): `tipo` (diario \| mensal), `referencia` (`AAAA-MM-DD` ou `AAAA-MM`),
`situacao` (ok \| erro), `formato` (`pg_dump_custom` \| `sqlite_gzip`), `iniciado_em`, `concluido_em`,
`expira_em`, `tamanho_bytes` e `sha256` (do dump sem cifra), `erro`, `conteudo` (dump cifrado com Fernet;
coluna carregada só sob demanda). Único entre ativos em (`tipo`, `referencia`). Os **dados** desta
tabela não entram no dump (`--exclude-table-data`); o resto do banco entra, inclusive os registros
excluídos logicamente.

## Permissões
Nenhuma: não há rota nem tela. Quando houver interface, a permissão nasce em `core/permissoes.py` e
a matriz de `acesso.md` é atualizada.

## Interações com outros módulos
| Direção | Módulo | O quê |
|---|---|---|
| consome | — | `core/crypto.py` (cifra), `core/config.py` (agenda e retenção), `core/db.py` (sessão) |
| é consumido por | worker | os três jobs abaixo, via `JobSpec` |

## Jobs agendados
Fuso `America/Sao_Paulo`; variáveis `GDA_BACKUP_*` (padrões abaixo).
| Job | Cron | O que faz |
|---|---|---|
| `backup.diario` | `0 0 * * *` | Backup de todo dia à 00:00; guardado por 7 dias (`GDA_BACKUP_RETENCAO_DIARIA_DIAS`) |
| `backup.mensal` | `0 0 1 * *` | À 00:00 do dia 1, cobre o mês que terminou (referência `AAAA-MM` do mês anterior); guardado por 365 dias (`GDA_BACKUP_RETENCAO_MENSAL_DIAS`) |
| `backup.limpeza` | `0 1 * * *` | Libera o conteúdo dos vencidos (exclusão lógica, nunca física) |

## Regras de negócio e decisões
- O backup é do banco inteiro do ProdutoFinal; nunca do CKAN.
- Cifrado com a `GDA_ENCRYPTION_KEY`: sem a chave do volume `gda_segredos` a cópia não abre.
- **Limite:** o backup mora no mesmo PostgreSQL. Não protege da perda do volume `pgdata`; o backup
  externo do `deploy/README.md` continua necessário.
- A imagem do backend traz `postgresql-client-16` (`backend/Dockerfile`), igual ao servidor.

## Pendências
- Interface (listar e restaurar) quando a GEDA pedir.
- Destino externo e retenção a validar com a SECTI/CGE-GO (decisão em aberto, ADR-0034).
- Teste do `pg_dump`/`pg_restore` ponta a ponta em PostgreSQL real (a suíte automática usa SQLite e
  simula o cliente do PostgreSQL).

## Histórico de alterações
| Data | Alteração | Autor |
|---|---|---|
| 10/11/2026 | Módulo criado: backups diário (00:00, 7 dias) e mensal (00:00 do dia 1, 1 ano) com `pg_dump`, guardados cifrados em `backup_copia`; limpeza; CLI (ADR-0034) | João |
