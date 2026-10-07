# Convenções de modelagem do banco de dados

Instruções obrigatórias para qualquer pessoa ou agente de IA que crie ou altere tabelas.
Decisão e alternativas: [ADR-0013](../adr/0013-banco-de-dados-e-convencoes.md) · Estado atual:
[MER](mer.md) (gerado do código).

## 1. Nomenclatura

| Elemento | Regra | Exemplos |
|---|---|---|
| Idioma | Português, `snake_case`, sem acento. Termos do CKAN ficam em inglês. | `prazo_abertura`, `last_modified`, `url_type` |
| Tabela | Singular. **Tabela nova leva o prefixo do módulo dono.** | `lgpd_achado`, `ia_uso`, `pda_base_prevista` |
| Chave primária | `id` (inteiro) para entidades próprias; `ckan_id` para entidades espelhadas do CKAN. | `usuario.id`, `dataset.ckan_id` |
| Chave estrangeira | `<entidade>_id`; quando houver duas para a mesma tabela, qualificar. | `recurso_id`, `perfil_fallback_id` |
| Booleano | Estado ou adjetivo; `eh_` quando for classificação. | `ativo`, `execucao_local`, `eh_dicionario_dados` |
| Data de evento | `<evento>_em`. | `iniciada_em`, `aprovado_em` |
| Constraints e índices | Nome automático pela `NAMING_CONVENTION` de `app/core/db.py`. Nunca nomear à mão. | `fk_recurso_dataset_id_dataset`, `ix_usuario_email` |
| Segredo cifrado | `<campo>_cifrada` + `<campo>_dica` (exibível). | `api_key_cifrada`, `api_key_dica` |

**Exceções existentes (mantidas, ver ADR-0013):** as tabelas do núcleo do inventário (`coleta`,
`organizacao`, `dataset`, `recurso`, `dataset_snapshot`), `usuario` e `parametro` não têm prefixo; e as
colunas `created_at`/`updated_at` do `TimestampMixin` estão em inglês. Não crie novas exceções.

## 2. Chaves e relacionamentos

- Entidade espelhada do CKAN usa o **ID do CKAN como PK** (`varchar(64)`), nunca o `name`, que os
  órgãos podem editar.
- Entidade própria usa `int` autoincremento.
- Relação N:N usa tabela de associação com PK composta pelas duas FKs (`acesso_usuario_papel`).
- **Toda referência ao estado atual tem chave estrangeira.**
- Referência **sem FK** só é permitida em tabela de histórico ou auditoria, para o registro
  sobreviver a exclusões. Toda referência desse tipo é declarada em `REFERENCIAS_LOGICAS`
  (`scripts/gerar_mer.py`) com a justificativa; o gerador falha se ela apontar para coluna inexistente.
- **Autoria** em trilha de auditoria é o e-mail do usuário, gravado como texto no momento da ação
  (`lgpd_decisao.usuario`, `lgpd_correcao.aprovado_por`, `*.alterado_por`).

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
- Entidades editáveis herdam `TimestampMixin` (`created_at`, `updated_at`).

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
- [ ] PK conforme a seção 2; FKs para todo estado atual
- [ ] Datas com fuso; enumerações como `String`
- [ ] Nenhum dado pessoal ou conteúdo de IA armazenado
- [ ] Docstring, migração revisada, MER regenerado, MODULO.md atualizado
