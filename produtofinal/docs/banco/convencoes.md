# Convenções de modelagem do banco de dados

Instruções obrigatórias para qualquer pessoa ou agente de IA que crie ou altere tabelas.
Decisão e alternativas: [ADR-0013](../adr/0013-banco-de-dados-e-convencoes.md) ·
[ADR-0018](../adr/0018-chave-primaria-propria-e-id-ckan.md) · [ADR-0019](../adr/0019-dao-exclusao-logica-e-auditoria.md) · Estado atual:
[MER](mer.md) (gerado do código).

## 1. Nomenclatura

| Elemento | Regra | Exemplos |
|---|---|---|
| Idioma | Português, `snake_case`, sem acento. Termos do CKAN ficam em inglês. | `prazo_abertura`, `last_modified`, `url_type` |
| Tabela | Singular. **Tabela nova leva o prefixo do módulo dono.** | `lgpd_achado`, `ia_uso`, `pda_base_prevista` |
| Chave primária | `id` (inteiro) em **todas** as tabelas, inclusive associações e espelhadas do CKAN (ADR-0018, ADR-0019). Vem da `Base`: não declare. | `usuario.id`, `parametro.id` |
| Colunas comuns | `deleted`, `created`, `created_id`, `changed`, `changed_id` em **toda** tabela (`RegistroMixin`, ADR-0019). Não declare; quem preenche é o `Dao`. | — |
| ID no CKAN | `id_ckan` (`varchar(64)`, único, opcional) nas entidades espelhadas. | `dataset.id_ckan` |
| Chave estrangeira | `<entidade>_id`; quando houver duas para a mesma tabela, qualificar. | `recurso_id`, `perfil_fallback_id` |
| Booleano | Estado ou adjetivo; `eh_` quando for classificação. | `ativo`, `execucao_local`, `eh_dicionario_dados` |
| Data de evento | `<evento>_em`. | `iniciada_em`, `aprovado_em` |
| Constraints e índices | Nome automático pela `NAMING_CONVENTION` de `app/core/db.py`. Único: `unico_entre_ativos(tabela, *colunas)` gera `uq_<tabela>_<colunas>`. | `fk_recurso_dataset_id_dataset`, `uq_usuario_email` |
| Segredo cifrado | `<campo>_cifrada` + `<campo>_dica` (exibível). | `api_key_cifrada`, `api_key_dica` |

**Exceções existentes (mantidas, ver ADR-0013):** as tabelas do núcleo do inventário (`coleta`,
`organizacao`, `dataset`, `recurso`, `dataset_snapshot`), `usuario` e `parametro` não têm prefixo; e as
colunas comuns `deleted`, `created`, `created_id`, `changed`, `changed_id` estão em inglês por decisão
da coordenação (ADR-0019). Não crie novas exceções.

## 2. Chaves e relacionamentos

- Toda tabela usa `id` `int` autoincremento como PK, inclusive as espelhadas do CKAN (ADR-0018).
- Entidade espelhada do CKAN guarda o ID do CKAN em `id_ckan` (`varchar(64)`, único, opcional para
  registros que ainda não existem no portal). A coleta casa os registros por ele, **nunca pelo
  `name`**, que os órgãos podem editar. FKs apontam sempre para o `id` próprio.
- Relação N:N usa tabela de associação com `id` próprio e índice único entre ativos nas duas FKs
  (`acesso_usuario_papel`). Relação ORM sobre associação é só leitura (`viewonly`); quem grava é o DAO.
- **Toda referência ao estado atual tem chave estrangeira.**
- Referência **sem FK** só é permitida em tabela de histórico ou auditoria, para o registro
  sobreviver a exclusões. Toda referência desse tipo é declarada em `REFERENCIAS_LOGICAS`
  (`scripts/gerar_mer.py`) com a justificativa; o gerador falha se ela apontar para coluna inexistente.
- **Autoria** em trilha de auditoria é o e-mail do usuário, gravado como texto no momento da ação
  (`lgpd_decisao.usuario`, `lgpd_correcao.aprovado_por`, `*.alterado_por`).
- **Campo único** vale só entre os registros ativos: use `unico_entre_ativos` (índice parcial
  `WHERE NOT deleted`), nunca `unique=True`. Excluir libera o valor.
- `created_id`/`changed_id` são referências lógicas a `usuario.id` (sem FK; vazio = sistema).

## 3. Tipos

| Uso | Tipo | Observação |
|---|---|---|
| Data e hora | `DateTime(timezone=True)` | Sempre em UTC (`utcnow()`); o frontend converte para America/Sao_Paulo. |
| Texto curto | `String(n)` com tamanho explícito | |
| Texto livre | `Text` | |
| Enumeração | `String` | Valores listados em comentário no modelo. Não usar `ENUM` do banco (migração custosa, não portável para SQLite). |
| Estrutura vinda de fora | `JSON` | Só para dados cuja estrutura não controlamos ou que não são filtrados: `extras` do CKAN, `payload` de snapshot, `parametro.valor`. Se for filtrar por um campo, ele vira coluna. |

## 4. Integridade e histórico

- Registros espelhados do CKAN **não são apagados**: quem some do portal fica com `ativo_no_portal = false`.
- Tabelas de histórico são **somente inserção**: `dataset_snapshot`, `lgpd_decisao`, `ia_uso`.
- **Exclusão é sempre lógica** (`deleted = true`, via `Dao.delete_generic`): nada é apagado
  fisicamente, nem em cascata — o DAO do módulo exclui os dependentes (ex.: PDA → bases).
- `created`/`created_id` = criação; `changed`/`changed_id` = última alteração (a exclusão é uma
  alteração). Preenchidos pelo `Dao.save_generic` com o usuário que age.

## 4.1 Acesso ao banco (ADR-0019)

- **Só pelos DAOs.** `app/core/dao.py` (classe-pai `Dao`) é a única porta para a sessão; cada
  módulo tem `app/modules/<id>/dao.py` com uma classe que herda de `Dao` e define as consultas.
- Services, routers, jobs e a CLI **nunca** chamam `db.execute`, `db.scalar(s)`, `db.get`,
  `db.add`, `db.delete`, `db.commit`… (o teste `test_banco_so_e_acessado_pelos_daos` falha).
- As consultas do módulo montam o `select` e chamam as funções genéricas (`buscar_lista`,
  `buscar_um`, `buscar_valor`, `buscar_linhas`, `obter`), que acrescentam `deleted = false` a toda
  tabela da consulta, inclusive joins, subconsultas e relacionamentos carregados.
- Gravação: `save_generic`; exclusão: `delete_generic` / `delete_generic_lote`; lote: `update_generic`.
  Crie o DAO com o usuário que age (`XDao.de(db, user)`); `None` = sistema.

## 5. Privacidade (LGPD)

- **Nunca** armazenar o valor de um dado pessoal encontrado nos recursos: o achado guarda tabela,
  coluna, linha e tipo.
- **Nunca** armazenar prompt ou resposta de modelo de IA.
- Senha só como hash bcrypt; chaves de API só cifradas (Fernet, `GDA_ENCRYPTION_KEY`).

## 6. Migrações (Alembic)

1. Altere o modelo → `alembic revision --autogenerate -m "<modulo>: <mudança>"`.
2. **Revise o arquivo gerado** antes do commit (autogenerate não detecta tudo, como renomeações).
3. Uma migração por mudança lógica, no mesmo commit do modelo.
4. Nunca edite uma migração já aplicada em algum ambiente; corrija com uma nova.
5. Migração de dados fica separada da migração de estrutura.

## 7. Documentação obrigatória

Ao criar ou alterar tabela, no mesmo commit:
1. Docstring de uma linha na classe do modelo (vira a descrição no MER; o teste exige).
2. `python scripts/gerar_mer.py` (o hook e os testes falham se o MER estiver desatualizado).
3. Seção "Modelo de dados" do `docs/modulos/<modulo>.md` com linha no Histórico.

## Checklist de tabela nova

- [ ] Nome no singular com prefixo do módulo
- [ ] Herda de `Base` (PK `id` e colunas comuns vêm prontas); FKs para todo estado atual
- [ ] Únicos com `unico_entre_ativos`; consultas e gravações num `dao.py` do módulo
- [ ] Datas com fuso; enumerações como `String`
- [ ] Nenhum dado pessoal ou conteúdo de IA armazenado
- [ ] Docstring, migração revisada, MER regenerado, MODULO.md atualizado
