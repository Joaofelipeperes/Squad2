# MER — Modelo Entidade-Relacionamento

> **Arquivo gerado** por `scripts/gerar_mer.py` a partir dos modelos SQLAlchemy.
> Não edite à mão: altere o modelo (ou sua docstring), crie a migração e rode o script.
> Convenções de modelagem: [convencoes.md](convencoes.md) · Decisão: [ADR-0013](../adr/0013-banco-de-dados-e-convencoes.md) · [ADR-0019](../adr/0019-dao-exclusao-logica-e-auditoria.md).

20 tabelas · linhas contínuas = chave estrangeira · linhas tracejadas = referência lógica sem FK (ver tabela ao final). Toda tabela tem ainda `deleted`, `created`, `created_id`, `changed` e `changed_id` (exclusão lógica e auditoria), omitidas do diagrama e listadas no dicionário de dados.

## Diagrama

```mermaid
erDiagram
    acesso_log {
        int id PK
        datetime ocorrido_em
        varchar usuario
        varchar metodo
        varchar caminho
        varchar rota
        varchar acao
        int status_http
        varchar ip
        varchar user_agent
    }
    acesso_papel {
        int id PK
        varchar codigo UK
        varchar nome
        text descricao
        bool sistema
        bool exige_orgao
        bool todas
    }
    acesso_papel_permissao {
        int id PK
        int papel_id FK
        varchar permissao
    }
    acesso_usuario_papel {
        int id PK
        int usuario_id FK
        int papel_id FK
    }
    usuario {
        int id PK
        varchar email UK
        varchar nome
        varchar senha_hash
        bool ativo
        int orgao_id FK
        datetime ultimo_acesso
    }
    coleta {
        int id PK
        datetime iniciada_em
        datetime finalizada_em
        varchar status
        varchar origem
        varchar solicitada_por
        int total_organizacoes
        int total_datasets
        int total_recursos
        text erro
    }
    dataset {
        int id PK
        varchar id_ckan UK
        varchar name
        varchar titulo
        text descricao
        int organizacao_id FK
        varchar autor
        varchar autor_email
        varchar licenca
        varchar periodicidade_declarada
        datetime metadata_created
        datetime metadata_modified
        json extras
        bool ativo_no_portal
        int ultima_coleta_id FK
    }
    dataset_snapshot {
        int id PK
        int coleta_id FK
        int dataset_id
        varchar hash_conteudo
        json payload
    }
    organizacao {
        int id PK
        varchar id_ckan UK
        varchar name
        varchar titulo
        varchar sigla
        int ultima_coleta_id FK
    }
    recurso {
        int id PK
        varchar id_ckan UK
        int dataset_id FK
        varchar nome
        varchar formato
        text url
        varchar url_type
        datetime created_ckan
        datetime last_modified
        bool datastore_active
        bool eh_dicionario_dados
        int ultima_coleta_id FK
    }
    pda_base_prevista {
        int id PK
        int plano_id FK
        varchar orgao_sigla
        int organizacao_id FK
        varchar nome_previsto
        text descricao
        varchar unidade_responsavel
        date prazo_abertura
        varchar periodicidade
        varchar periodicidade_original
        varchar politicas_publicas
        bool possui_conteudo_sigiloso
        int dataset_id FK
        varchar dataset_name_planilha
        int linha_planilha
        varchar classificacao
    }
    pda_plano {
        int id PK
        varchar nome UK
        date vigencia_inicio
        date vigencia_fim
        bool vigente UK
        varchar arquivo_nome
        varchar importado_por
        datetime importado_em
        int total_bases
    }
    lgpd_achado {
        int id PK
        int recurso_id FK
        varchar coluna
        int linha
        int ocorrencias
        varchar tipo
        varchar metodo
        int confianca
        varchar prioridade
        varchar status
        varchar impressao_digital
        text explicacao
    }
    lgpd_correcao {
        int id PK
        int recurso_id FK
        varchar status
        varchar solicitada_por
        json itens
        int celulas_alteradas
        varchar nome_arquivo
        varchar formato
        varchar hash_original
        varchar caminho_backup
        varchar caminho_previa
        varchar aprovado_por
        datetime aprovado_em
        text justificativa
        datetime publicada_em
        varchar revertida_por
        datetime revertida_em
        text motivo_reversao
        text erro
    }
    lgpd_decisao {
        int id PK
        int achado_id FK
        varchar decisao
        text justificativa
        varchar usuario
        datetime momento
    }
    lgpd_varredura {
        int id PK
        int recurso_id FK
        varchar status
        varchar origem
        varchar solicitada_por
        datetime solicitada_em
        datetime iniciada_em
        datetime finalizada_em
        int linhas_analisadas
        int chamadas_ia
        int achados
        varchar modelo
        text aviso
        text erro
    }
    ia_perfil_provedor {
        int id PK
        varchar nome UK
        varchar tipo
        varchar modelo
        varchar base_url
        text api_key_cifrada
        varchar api_key_dica
        bool execucao_local
        float temperatura
        int max_tokens
        float timeout_s
        json extra
        bool ativo
    }
    ia_uso {
        int id PK
        datetime momento
        varchar tarefa
        int perfil_id
        varchar perfil_nome
        varchar modelo
        bool sucesso
        bool usou_fallback
        int latencia_ms
        int tokens_entrada
        int tokens_saida
        varchar erro
    }
    ia_vinculo_tarefa {
        int id PK
        varchar tarefa UK
        int perfil_id FK
        int perfil_fallback_id FK
        varchar alterado_por
    }
    parametro {
        int id PK
        varchar chave UK
        json valor
        varchar alterado_por
    }
    acesso_papel ||--o{ acesso_papel_permissao : "papel_id"
    usuario ||--o{ acesso_usuario_papel : "usuario_id"
    acesso_papel ||--o{ acesso_usuario_papel : "papel_id"
    organizacao |o--o{ usuario : "orgao_id"
    organizacao |o--o{ dataset : "organizacao_id"
    coleta |o--o{ dataset : "ultima_coleta_id"
    coleta ||--o{ dataset_snapshot : "coleta_id"
    coleta |o--o{ organizacao : "ultima_coleta_id"
    dataset ||--o{ recurso : "dataset_id"
    coleta |o--o{ recurso : "ultima_coleta_id"
    pda_plano ||--o{ pda_base_prevista : "plano_id"
    organizacao |o--o{ pda_base_prevista : "organizacao_id"
    dataset |o--o{ pda_base_prevista : "dataset_id"
    recurso ||--o{ lgpd_achado : "recurso_id"
    recurso ||--o{ lgpd_correcao : "recurso_id"
    lgpd_achado ||--o{ lgpd_decisao : "achado_id"
    recurso ||--o{ lgpd_varredura : "recurso_id"
    ia_perfil_provedor |o--o{ ia_vinculo_tarefa : "perfil_id"
    ia_perfil_provedor |o--o{ ia_vinculo_tarefa : "perfil_fallback_id"
    dataset |o..o{ dataset_snapshot : "dataset_id (lógica)"
    ia_perfil_provedor |o..o{ ia_uso : "perfil_id (lógica)"
```

## Relacionamentos

| Origem | Destino | Cardinalidade (pai : filhos) | Tipo | Observação |
|---|---|---|---|---|
| `acesso_papel_permissao.papel_id` | `acesso_papel.id` | 1 : N | FK |  |
| `acesso_usuario_papel.usuario_id` | `usuario.id` | 1 : N | FK |  |
| `acesso_usuario_papel.papel_id` | `acesso_papel.id` | 1 : N | FK |  |
| `usuario.orgao_id` | `organizacao.id` | 0..1 : N | FK |  |
| `dataset.organizacao_id` | `organizacao.id` | 0..1 : N | FK |  |
| `dataset.ultima_coleta_id` | `coleta.id` | 0..1 : N | FK |  |
| `dataset_snapshot.coleta_id` | `coleta.id` | 1 : N | FK |  |
| `organizacao.ultima_coleta_id` | `coleta.id` | 0..1 : N | FK |  |
| `recurso.dataset_id` | `dataset.id` | 1 : N | FK |  |
| `recurso.ultima_coleta_id` | `coleta.id` | 0..1 : N | FK |  |
| `pda_base_prevista.plano_id` | `pda_plano.id` | 1 : N | FK |  |
| `pda_base_prevista.organizacao_id` | `organizacao.id` | 0..1 : N | FK |  |
| `pda_base_prevista.dataset_id` | `dataset.id` | 0..1 : N | FK |  |
| `lgpd_achado.recurso_id` | `recurso.id` | 1 : N | FK |  |
| `lgpd_correcao.recurso_id` | `recurso.id` | 1 : N | FK |  |
| `lgpd_decisao.achado_id` | `lgpd_achado.id` | 1 : N | FK |  |
| `lgpd_varredura.recurso_id` | `recurso.id` | 1 : N | FK |  |
| `ia_vinculo_tarefa.perfil_id` | `ia_perfil_provedor.id` | 0..1 : N | FK |  |
| `ia_vinculo_tarefa.perfil_fallback_id` | `ia_perfil_provedor.id` | 0..1 : N | FK |  |
| `dataset_snapshot.dataset_id` | `dataset.id` | — | referência lógica | Fotografia histórica: sem FK para não depender do estado atual do dataset. |
| `ia_uso.perfil_id` | `ia_perfil_provedor.id` | — | referência lógica | Registro de uso sobrevive à exclusão do perfil (o nome fica em perfil_nome). |
| `coleta.solicitada_por` | `usuario.email` | — | referência lógica | Autoria congelada como e-mail. |
| `lgpd_decisao.usuario` | `usuario.email` | — | referência lógica | Autoria congelada como e-mail. |
| `lgpd_correcao.aprovado_por` | `usuario.email` | — | referência lógica | Autoria congelada como e-mail. |
| `lgpd_correcao.solicitada_por` | `usuario.email` | — | referência lógica | Autoria congelada como e-mail. |
| `lgpd_correcao.revertida_por` | `usuario.email` | — | referência lógica | Autoria congelada como e-mail. |
| `lgpd_varredura.solicitada_por` | `usuario.email` | — | referência lógica | Autoria congelada como e-mail. |
| `ia_vinculo_tarefa.alterado_por` | `usuario.email` | — | referência lógica | Autoria congelada como e-mail. |
| `parametro.alterado_por` | `usuario.email` | — | referência lógica | Autoria congelada como e-mail. |
| `acesso_log.usuario` | `usuario.email` | — | referência lógica | Autoria congelada como e-mail. |
| `<toda tabela>.created_id / changed_id` | `usuario.id` | — | referência lógica | Auditoria (ADR-0019): quem criou / alterou por último; vazio = sistema. Sem FK para não criar ciclos. |

## Dicionário de dados

### Módulo `acesso` — Acesso (usuários e papéis)
Documentação do módulo: [docs/modulos/acesso.md](../modulos/acesso.md)

#### `acesso_log`

Log de acesso: uma linha por requisição à API (quem, de onde, o quê, resultado). Só inserção.

| Coluna | Tipo | Nulo | Chave | Referência | Padrão |
|---|---|:-:|---|---|---|
| `id` | int | não | PK |  |  |
| `ocorrido_em` | datetime | não |  |  | função |
| `usuario` | varchar(200) | sim |  |  |  |
| `metodo` | varchar(10) | não |  |  |  |
| `caminho` | varchar(500) | não |  |  |  |
| `rota` | varchar(200) | sim |  |  |  |
| `acao` | varchar(100) | sim |  |  |  |
| `status_http` | int | não |  |  |  |
| `ip` | varchar(45) | sim |  |  |  |
| `user_agent` | varchar(500) | sim |  |  |  |
| `deleted` | bool | não |  |  | `False` |
| `created` | datetime | não |  |  | função |
| `created_id` | int | sim |  |  |  |
| `changed` | datetime | não |  |  | função |
| `changed_id` | int | sim |  |  |  |

Índices: `ix_acesso_log_ocorrido_em`, `ix_acesso_log_usuario`

#### `acesso_papel`

Conjunto nomeado de permissões atribuível a usuários (ex.: Gerência GEDA).

| Coluna | Tipo | Nulo | Chave | Referência | Padrão |
|---|---|:-:|---|---|---|
| `id` | int | não | PK |  |  |
| `codigo` | varchar(60) | não | UK |  |  |
| `nome` | varchar(120) | não |  |  |  |
| `descricao` | text | sim |  |  |  |
| `sistema` | bool | não |  |  | `False` |
| `exige_orgao` | bool | não |  |  | `False` |
| `todas` | bool | não |  |  | `False` |
| `deleted` | bool | não |  |  | `False` |
| `created` | datetime | não |  |  | função |
| `created_id` | int | sim |  |  |  |
| `changed` | datetime | não |  |  | função |
| `changed_id` | int | sim |  |  |  |

Índices: `uq_acesso_papel_codigo`

#### `acesso_papel_permissao`

Código de permissão do catálogo (app/core/permissoes.py) concedido a um papel.

| Coluna | Tipo | Nulo | Chave | Referência | Padrão |
|---|---|:-:|---|---|---|
| `id` | int | não | PK |  |  |
| `papel_id` | int | não | FK | `acesso_papel.id` |  |
| `permissao` | varchar(80) | não |  |  |  |
| `deleted` | bool | não |  |  | `False` |
| `created` | datetime | não |  |  | função |
| `created_id` | int | sim |  |  |  |
| `changed` | datetime | não |  |  | função |
| `changed_id` | int | sim |  |  |  |

Índices: `ix_acesso_papel_permissao_papel_id`, `uq_acesso_papel_permissao_papel_id_permissao`

#### `acesso_usuario_papel`

Papel atribuído a um usuário.

| Coluna | Tipo | Nulo | Chave | Referência | Padrão |
|---|---|:-:|---|---|---|
| `id` | int | não | PK |  |  |
| `usuario_id` | int | não | FK | `usuario.id` |  |
| `papel_id` | int | não | FK | `acesso_papel.id` |  |
| `deleted` | bool | não |  |  | `False` |
| `created` | datetime | não |  |  | função |
| `created_id` | int | sim |  |  |  |
| `changed` | datetime | não |  |  | função |
| `changed_id` | int | sim |  |  |  |

Índices: `ix_acesso_usuario_papel_papel_id`, `ix_acesso_usuario_papel_usuario_id`, `uq_acesso_usuario_papel_usuario_id_papel_id`

#### `usuario`

Pessoa com acesso à solução; com órgão vinculado, fica restrita aos dados dele.

| Coluna | Tipo | Nulo | Chave | Referência | Padrão |
|---|---|:-:|---|---|---|
| `id` | int | não | PK |  |  |
| `email` | varchar(200) | não | UK |  |  |
| `nome` | varchar(200) | não |  |  |  |
| `senha_hash` | varchar(200) | não |  |  |  |
| `ativo` | bool | não |  |  | `True` |
| `orgao_id` | int | sim | FK | `organizacao.id` |  |
| `ultimo_acesso` | datetime | sim |  |  |  |
| `deleted` | bool | não |  |  | `False` |
| `created` | datetime | não |  |  | função |
| `created_id` | int | sim |  |  |  |
| `changed` | datetime | não |  |  | função |
| `changed_id` | int | sim |  |  |  |

Índices: `uq_usuario_email`

### Módulo `inventario` — Inventário CKAN
Documentação do módulo: [docs/modulos/inventario.md](../modulos/inventario.md)

#### `coleta`

Execução da coleta do CKAN (agendada ou manual), com totais e eventual erro.

| Coluna | Tipo | Nulo | Chave | Referência | Padrão |
|---|---|:-:|---|---|---|
| `id` | int | não | PK |  |  |
| `iniciada_em` | datetime | não |  |  | função |
| `finalizada_em` | datetime | sim |  |  |  |
| `status` | varchar(20) | não |  |  | `'executando'` |
| `origem` | varchar(20) | não |  |  | `'agendada'` |
| `solicitada_por` | varchar(200) | sim |  |  |  |
| `total_organizacoes` | int | não |  |  | `0` |
| `total_datasets` | int | não |  |  | `0` |
| `total_recursos` | int | não |  |  | `0` |
| `erro` | text | sim |  |  |  |
| `deleted` | bool | não |  |  | `False` |
| `created` | datetime | não |  |  | função |
| `created_id` | int | sim |  |  |  |
| `changed` | datetime | não |  |  | função |
| `changed_id` | int | sim |  |  |  |

#### `dataset`

Conjunto de dados espelhado do CKAN (package), no estado da última coleta.

| Coluna | Tipo | Nulo | Chave | Referência | Padrão |
|---|---|:-:|---|---|---|
| `id` | int | não | PK |  |  |
| `id_ckan` | varchar(64) | sim | UK |  |  |
| `name` | varchar(200) | não |  |  |  |
| `titulo` | varchar(500) | não |  |  |  |
| `descricao` | text | sim |  |  |  |
| `organizacao_id` | int | sim | FK | `organizacao.id` |  |
| `autor` | varchar(300) | sim |  |  |  |
| `autor_email` | varchar(300) | sim |  |  |  |
| `licenca` | varchar(100) | sim |  |  |  |
| `periodicidade_declarada` | varchar(100) | sim |  |  |  |
| `metadata_created` | datetime | sim |  |  |  |
| `metadata_modified` | datetime | sim |  |  |  |
| `extras` | json | não |  |  | função |
| `ativo_no_portal` | bool | não |  |  | `True` |
| `ultima_coleta_id` | int | sim | FK | `coleta.id` |  |
| `deleted` | bool | não |  |  | `False` |
| `created` | datetime | não |  |  | função |
| `created_id` | int | sim |  |  |  |
| `changed` | datetime | não |  |  | função |
| `changed_id` | int | sim |  |  |  |

Índices: `ix_dataset_name`, `ix_dataset_organizacao_id`, `uq_dataset_id_ckan`

#### `dataset_snapshot`

Fotografia compacta de um dataset em uma coleta — insumo do diff entre coletas.

| Coluna | Tipo | Nulo | Chave | Referência | Padrão |
|---|---|:-:|---|---|---|
| `id` | int | não | PK |  |  |
| `coleta_id` | int | não | FK | `coleta.id` |  |
| `dataset_id` | int | não |  |  |  |
| `hash_conteudo` | varchar(64) | não |  |  |  |
| `payload` | json | não |  |  |  |
| `deleted` | bool | não |  |  | `False` |
| `created` | datetime | não |  |  | função |
| `created_id` | int | sim |  |  |  |
| `changed` | datetime | não |  |  | função |
| `changed_id` | int | sim |  |  |  |

Índices: `ix_dataset_snapshot_coleta_id`, `ix_dataset_snapshot_dataset_id`

#### `organizacao`

Órgão publicador espelhado do CKAN (organization).

| Coluna | Tipo | Nulo | Chave | Referência | Padrão |
|---|---|:-:|---|---|---|
| `id` | int | não | PK |  |  |
| `id_ckan` | varchar(64) | sim | UK |  |  |
| `name` | varchar(200) | não |  |  |  |
| `titulo` | varchar(300) | não |  |  |  |
| `sigla` | varchar(40) | sim |  |  |  |
| `ultima_coleta_id` | int | sim | FK | `coleta.id` |  |
| `deleted` | bool | não |  |  | `False` |
| `created` | datetime | não |  |  | função |
| `created_id` | int | sim |  |  |  |
| `changed` | datetime | não |  |  | função |
| `changed_id` | int | sim |  |  |  |

Índices: `ix_organizacao_name`, `uq_organizacao_id_ckan`

#### `recurso`

Arquivo ou link de um dataset (resource); last_modified é o indicador de atualização.

| Coluna | Tipo | Nulo | Chave | Referência | Padrão |
|---|---|:-:|---|---|---|
| `id` | int | não | PK |  |  |
| `id_ckan` | varchar(64) | sim | UK |  |  |
| `dataset_id` | int | não | FK | `dataset.id` |  |
| `nome` | varchar(500) | sim |  |  |  |
| `formato` | varchar(40) | sim |  |  |  |
| `url` | text | sim |  |  |  |
| `url_type` | varchar(20) | sim |  |  |  |
| `created_ckan` | datetime | sim |  |  |  |
| `last_modified` | datetime | sim |  |  |  |
| `datastore_active` | bool | não |  |  | `False` |
| `eh_dicionario_dados` | bool | não |  |  | `False` |
| `ultima_coleta_id` | int | sim | FK | `coleta.id` |  |
| `deleted` | bool | não |  |  | `False` |
| `created` | datetime | não |  |  | função |
| `created_id` | int | sim |  |  |  |
| `changed` | datetime | não |  |  | função |
| `changed_id` | int | sim |  |  |  |

Índices: `ix_recurso_dataset_id`, `uq_recurso_id_ckan`

### Módulo `pda` — PDA
Documentação do módulo: [docs/modulos/pda.md](../modulos/pda.md)

#### `pda_base_prevista`

Linha do PDA. O vínculo com o CKAN é SEMPRE pelo ID do dataset (PBI-13): FK para `dataset.id`, que guarda o `id_ckan`. O `name` lido da planilha fica em `dataset_name_planilha` apenas para auditoria e para resolver vínculos.

| Coluna | Tipo | Nulo | Chave | Referência | Padrão |
|---|---|:-:|---|---|---|
| `id` | int | não | PK |  |  |
| `plano_id` | int | não | FK | `pda_plano.id` |  |
| `orgao_sigla` | varchar(100) | não |  |  |  |
| `organizacao_id` | int | sim | FK | `organizacao.id` |  |
| `nome_previsto` | varchar(500) | não |  |  |  |
| `descricao` | text | sim |  |  |  |
| `unidade_responsavel` | varchar(500) | sim |  |  |  |
| `prazo_abertura` | date | sim |  |  |  |
| `periodicidade` | varchar(40) | não |  |  | `'Sem informação'` |
| `periodicidade_original` | varchar(100) | sim |  |  |  |
| `politicas_publicas` | varchar(500) | sim |  |  |  |
| `possui_conteudo_sigiloso` | bool | sim |  |  |  |
| `dataset_id` | int | sim | FK | `dataset.id` |  |
| `dataset_name_planilha` | varchar(200) | sim |  |  |  |
| `linha_planilha` | int | sim |  |  |  |
| `classificacao` | varchar(20) | não |  |  | `'pda'` |
| `deleted` | bool | não |  |  | `False` |
| `created` | datetime | não |  |  | função |
| `created_id` | int | sim |  |  |  |
| `changed` | datetime | não |  |  | função |
| `changed_id` | int | sim |  |  |  |

Índices: `ix_pda_base_prevista_dataset_id`, `ix_pda_base_prevista_organizacao_id`, `ix_pda_base_prevista_orgao_sigla`, `ix_pda_base_prevista_plano_id`

#### `pda_plano`

Um Plano de Dados Abertos importado (ex.: "PDA 2025-2027").

| Coluna | Tipo | Nulo | Chave | Referência | Padrão |
|---|---|:-:|---|---|---|
| `id` | int | não | PK |  |  |
| `nome` | varchar(200) | não | UK |  |  |
| `vigencia_inicio` | date | sim |  |  |  |
| `vigencia_fim` | date | sim |  |  |  |
| `vigente` | bool | não | UK |  | `False` |
| `arquivo_nome` | varchar(300) | sim |  |  |  |
| `importado_por` | varchar(200) | sim |  |  |  |
| `importado_em` | datetime | não |  |  | função |
| `total_bases` | int | não |  |  | `0` |
| `deleted` | bool | não |  |  | `False` |
| `created` | datetime | não |  |  | função |
| `created_id` | int | sim |  |  |  |
| `changed` | datetime | não |  |  | função |
| `changed_id` | int | sim |  |  |  |

Índices: `uq_pda_plano_nome`, `uq_pda_plano_nome_ci`, `uq_pda_plano_vigente`

### Módulo `lgpd` — LGPD
Documentação do módulo: [docs/modulos/lgpd.md](../modulos/lgpd.md)

#### `lgpd_achado`

Possível dado pessoal localizado num recurso (local e tipo, nunca o valor).

| Coluna | Tipo | Nulo | Chave | Referência | Padrão |
|---|---|:-:|---|---|---|
| `id` | int | não | PK |  |  |
| `recurso_id` | int | não | FK | `recurso.id` |  |
| `coluna` | varchar(300) | não |  |  |  |
| `linha` | int | sim |  |  |  |
| `ocorrencias` | int | não |  |  | `1` |
| `tipo` | varchar(40) | não |  |  |  |
| `metodo` | varchar(20) | não |  |  |  |
| `confianca` | int | não |  |  |  |
| `prioridade` | varchar(10) | não |  |  |  |
| `status` | varchar(20) | não |  |  | `'revisar'` |
| `impressao_digital` | varchar(64) | não |  |  |  |
| `explicacao` | text | sim |  |  |  |
| `deleted` | bool | não |  |  | `False` |
| `created` | datetime | não |  |  | função |
| `created_id` | int | sim |  |  |  |
| `changed` | datetime | não |  |  | função |
| `changed_id` | int | sim |  |  |  |

Índices: `ix_lgpd_achado_impressao_digital`, `ix_lgpd_achado_recurso_id`

#### `lgpd_correcao`

Anonimização de um recurso (US26, PBI-91 a PBI-94): prévia, aprovação, publicação e reversão. Os arquivos (cópia do original e versão anonimizada) ficam FORA do banco, em `GDA_LGPD_ARQUIVOS_DIR`, pela política de retenção da GEDA; aqui só os caminhos e o hash.

| Coluna | Tipo | Nulo | Chave | Referência | Padrão |
|---|---|:-:|---|---|---|
| `id` | int | não | PK |  |  |
| `recurso_id` | int | não | FK | `recurso.id` |  |
| `status` | varchar(20) | não |  |  | `'gerando_previa'` |
| `solicitada_por` | varchar(200) | sim |  |  |  |
| `itens` | json | não |  |  | função |
| `celulas_alteradas` | int | não |  |  | `0` |
| `nome_arquivo` | varchar(500) | sim |  |  |  |
| `formato` | varchar(20) | sim |  |  |  |
| `hash_original` | varchar(64) | sim |  |  |  |
| `caminho_backup` | varchar(500) | sim |  |  |  |
| `caminho_previa` | varchar(500) | sim |  |  |  |
| `aprovado_por` | varchar(200) | sim |  |  |  |
| `aprovado_em` | datetime | sim |  |  |  |
| `justificativa` | text | sim |  |  |  |
| `publicada_em` | datetime | sim |  |  |  |
| `revertida_por` | varchar(200) | sim |  |  |  |
| `revertida_em` | datetime | sim |  |  |  |
| `motivo_reversao` | text | sim |  |  |  |
| `erro` | text | sim |  |  |  |
| `deleted` | bool | não |  |  | `False` |
| `created` | datetime | não |  |  | função |
| `created_id` | int | sim |  |  |  |
| `changed` | datetime | não |  |  | função |
| `changed_id` | int | sim |  |  |  |

Índices: `ix_lgpd_correcao_recurso_id`

#### `lgpd_decisao`

Histórico imutável das decisões humanas (PBI-42).

| Coluna | Tipo | Nulo | Chave | Referência | Padrão |
|---|---|:-:|---|---|---|
| `id` | int | não | PK |  |  |
| `achado_id` | int | não | FK | `lgpd_achado.id` |  |
| `decisao` | varchar(20) | não |  |  |  |
| `justificativa` | text | sim |  |  |  |
| `usuario` | varchar(200) | não |  |  |  |
| `momento` | datetime | não |  |  |  |
| `deleted` | bool | não |  |  | `False` |
| `created` | datetime | não |  |  | função |
| `created_id` | int | sim |  |  |  |
| `changed` | datetime | não |  |  | função |
| `changed_id` | int | sim |  |  |  |

Índices: `ix_lgpd_decisao_achado_id`

#### `lgpd_varredura`

Execução da varredura LGPD em um recurso (pedida na tela ou pelo job), com totais e erro.

| Coluna | Tipo | Nulo | Chave | Referência | Padrão |
|---|---|:-:|---|---|---|
| `id` | int | não | PK |  |  |
| `recurso_id` | int | não | FK | `recurso.id` |  |
| `status` | varchar(20) | não |  |  | `'pendente'` |
| `origem` | varchar(20) | não |  |  | `'manual'` |
| `solicitada_por` | varchar(200) | sim |  |  |  |
| `solicitada_em` | datetime | não |  |  | função |
| `iniciada_em` | datetime | sim |  |  |  |
| `finalizada_em` | datetime | sim |  |  |  |
| `linhas_analisadas` | int | não |  |  | `0` |
| `chamadas_ia` | int | não |  |  | `0` |
| `achados` | int | não |  |  | `0` |
| `modelo` | varchar(300) | sim |  |  |  |
| `aviso` | text | sim |  |  |  |
| `erro` | text | sim |  |  |  |
| `deleted` | bool | não |  |  | `False` |
| `created` | datetime | não |  |  | função |
| `created_id` | int | sim |  |  |  |
| `changed` | datetime | não |  |  | função |
| `changed_id` | int | sim |  |  |  |

Índices: `ix_lgpd_varredura_recurso_id`

### Módulo `ia` — Modelos de IA
Documentação do módulo: [docs/modulos/ia.md](../modulos/ia.md)

#### `ia_perfil_provedor`

Uma configuração nomeada de provedor+modelo. Ex.: 'Gemini SECTI', 'Qwen local'.

| Coluna | Tipo | Nulo | Chave | Referência | Padrão |
|---|---|:-:|---|---|---|
| `id` | int | não | PK |  |  |
| `nome` | varchar(120) | não | UK |  |  |
| `tipo` | varchar(40) | não |  |  |  |
| `modelo` | varchar(200) | não |  |  |  |
| `base_url` | varchar(500) | sim |  |  |  |
| `api_key_cifrada` | text | sim |  |  |  |
| `api_key_dica` | varchar(20) | sim |  |  |  |
| `execucao_local` | bool | não |  |  | `False` |
| `temperatura` | float | não |  |  | `0.2` |
| `max_tokens` | int | não |  |  | `1024` |
| `timeout_s` | float | não |  |  | `60.0` |
| `extra` | json | não |  |  | função |
| `ativo` | bool | não |  |  | `True` |
| `deleted` | bool | não |  |  | `False` |
| `created` | datetime | não |  |  | função |
| `created_id` | int | sim |  |  |  |
| `changed` | datetime | não |  |  | função |
| `changed_id` | int | sim |  |  |  |

Índices: `uq_ia_perfil_provedor_nome`

#### `ia_uso`

Uma linha por chamada. NÃO guarda prompt nem resposta (PBI-35 — não retenção).

| Coluna | Tipo | Nulo | Chave | Referência | Padrão |
|---|---|:-:|---|---|---|
| `id` | int | não | PK |  |  |
| `momento` | datetime | não |  |  | função |
| `tarefa` | varchar(40) | não |  |  |  |
| `perfil_id` | int | sim |  |  |  |
| `perfil_nome` | varchar(120) | não |  |  |  |
| `modelo` | varchar(200) | não |  |  |  |
| `sucesso` | bool | não |  |  |  |
| `usou_fallback` | bool | não |  |  | `False` |
| `latencia_ms` | int | sim |  |  |  |
| `tokens_entrada` | int | sim |  |  |  |
| `tokens_saida` | int | sim |  |  |  |
| `erro` | varchar(500) | sim |  |  |  |
| `deleted` | bool | não |  |  | `False` |
| `created` | datetime | não |  |  | função |
| `created_id` | int | sim |  |  |  |
| `changed` | datetime | não |  |  | função |
| `changed_id` | int | sim |  |  |  |

Índices: `ix_ia_uso_momento`

#### `ia_vinculo_tarefa`

Qual perfil atende cada tarefa de IA (e qual assume se o principal falhar).

| Coluna | Tipo | Nulo | Chave | Referência | Padrão |
|---|---|:-:|---|---|---|
| `id` | int | não | PK |  |  |
| `tarefa` | varchar(40) | não | UK |  |  |
| `perfil_id` | int | sim | FK | `ia_perfil_provedor.id` |  |
| `perfil_fallback_id` | int | sim | FK | `ia_perfil_provedor.id` |  |
| `alterado_por` | varchar(200) | sim |  |  |  |
| `deleted` | bool | não |  |  | `False` |
| `created` | datetime | não |  |  | função |
| `created_id` | int | sim |  |  |  |
| `changed` | datetime | não |  |  | função |
| `changed_id` | int | sim |  |  |  |

Índices: `uq_ia_vinculo_tarefa_tarefa`

### Módulo `parametros` — Parâmetros
Documentação do módulo: [docs/modulos/parametros.md](../modulos/parametros.md)

#### `parametro`

Valor de negócio editável pela GEDA; ausente no banco = vale o padrão do catálogo.

| Coluna | Tipo | Nulo | Chave | Referência | Padrão |
|---|---|:-:|---|---|---|
| `id` | int | não | PK |  |  |
| `chave` | varchar(80) | não | UK |  |  |
| `valor` | json | não |  |  |  |
| `alterado_por` | varchar(200) | sim |  |  |  |
| `deleted` | bool | não |  |  | `False` |
| `created` | datetime | não |  |  | função |
| `created_id` | int | sim |  |  |  |
| `changed` | datetime | não |  |  | função |
| `changed_id` | int | sim |  |  |  |

Índices: `uq_parametro_chave`
