# Módulo `acesso` — Login, usuários, papéis e permissões

| | |
|---|---|
| **Status** | Implementado |
| **Responsável** | João (base comum) |
| **User stories** | US24 (PBI-73) |
| **Backend** | `backend/app/modules/acesso/` · catálogo em `backend/app/core/permissoes.py` · portão em `backend/app/core/deps.py` |
| **Frontend** | `frontend/src/app/auth/` · `frontend/src/modules/usuarios/` · `frontend/src/shared/acesso/` |
| **Última atualização** | 07/10/2026 |

## Propósito
Garante que cada pessoa veja apenas as telas e execute apenas as ações liberadas para ela, e que
usuários de órgãos estaduais enxerguem somente dados do próprio órgão.

## Modelo de acesso
```
Usuário ──< papéis >── Papel ──< permissões >── código do catálogo (ex.: inventario.coletar)
   └── orgao_id (opcional) → escopo: só dados daquele órgão
```
- **Permissão** `<modulo>.<acao>`. `<modulo>.acessar` libera ver o módulo (menu + rota); as demais
  liberam ações. Existe só no catálogo `app/core/permissoes.py` (enum `P`).
- **Papel** agrupa permissões. Papéis do sistema são criados na subida da API
  (`sincronizar_papeis_padrao`); papéis personalizados são criados na tela.
- **Escopo de órgão**: `usuario.orgao_id` preenchido restringe as consultas via
  `filtrar_por_orgao(...)` e as ações via `exigir_mesmo_orgao(...)`.
- Permissões são lidas do banco **a cada requisição**: revogar um papel ou desativar o usuário vale
  na hora, sem esperar o token expirar.

## Telas
| Tela | Rota | Permissão para ver | Ações na tela (permissão) |
|---|---|---|---|
| Login | `/login` | pública | — |
| Sem acesso | qualquer rota, se o usuário não tem nenhuma tela | autenticado | Sair |
| Usuários e papéis | `/admin/usuarios` | `acesso.gerenciar_usuarios` | Criar/editar usuário (`acesso.gerenciar_usuarios`); criar/editar/excluir papel (`acesso.gerenciar_papeis` — sem ela, papéis aparecem só para leitura) |

Após o login o usuário cai na **primeira tela permitida** (órgão publicador → `/envio`).

## API
| Método | Rota (`/api/v1/acesso`) | Permissão | Descrição |
|---|---|---|---|
| POST | `/login` | pública | E-mail + senha → token JWT + sessão (usuário e permissões) |
| GET | `/me` | autenticado | Sessão atual; o frontend monta menu e botões a partir dela |
| GET | `/catalogo` | `gerenciar_usuarios` **ou** `gerenciar_papeis` | Permissões agrupadas por módulo |
| GET | `/orgaos` | `acesso.gerenciar_usuarios` | Órgãos para o vínculo do usuário (lê `inventario`) |
| GET | `/usuarios` | `acesso.gerenciar_usuarios` | Lista usuários |
| POST | `/usuarios` | `acesso.gerenciar_usuarios` | Cria usuário |
| PUT | `/usuarios/{id}` | `acesso.gerenciar_usuarios` | Edita nome, senha, ativo, órgão e papéis |
| GET | `/papeis` | `gerenciar_usuarios` **ou** `gerenciar_papeis` | Lista papéis com total de usuários |
| POST | `/papeis` | `acesso.gerenciar_papeis` | Cria papel personalizado |
| PUT | `/papeis/{id}` | `acesso.gerenciar_papeis` | Edita papel (exceto Administrador) |
| DELETE | `/papeis/{id}` | `acesso.gerenciar_papeis` | Exclui papel personalizado sem usuários |

## Serviços e métodos
Portão (`app/core/deps.py`) — usado por **todos** os módulos:
- `publico`, `autenticado`, `require(*P)`, `require_qualquer(*P)` — dependências FastAPI; toda rota
  declara uma. O `main.py` recusa subir se alguma rota não tiver (`verificar_controle_de_acesso`).
- `UsuarioAtual.pode(p)`, `.restrito_a_orgao`.
- `filtrar_por_orgao(stmt, coluna_orgao, user)` · `exigir_mesmo_orgao(user, orgao_id)`.

Serviço (`modules/acesso/service.py`):
- `permissoes_de(usuario) -> frozenset[str]` — une as permissões dos papéis; papel com `todas`
  recebe o catálogo inteiro; códigos fora do catálogo são ignorados.
- `carregar_usuario_atual(db, id) -> UsuarioAtual | None` — chamado pelo portão em cada requisição.
- `autenticar(db, email, senha)` — valida e registra `ultimo_acesso`.
- `sincronizar_papeis_padrao(db)` — cria papéis do catálogo que faltam e remove permissões órfãs;
  não sobrescreve ajustes feitos na tela. Roda na subida da API.
- `salvar_usuario(db, dados, usuario=None, editor=None)` · `criar_usuario(...)` (CLI/testes).
- `salvar_papel(db, dados, papel=None)` · `excluir_papel(db, papel)`.

Frontend:
- `useAuth().pode(permissao)` — ponto único de checagem na interface.
- `<Pode permissao="...">` — esconde botões/ações sem permissão.
- `permissoes.gen.ts` — tipos gerados do catálogo; manifesto de tela sem `permissao` válida não compila.

## Modelo de dados
| Tabela | Colunas relevantes |
|---|---|
| `usuario` | email (único), nome, senha_hash (bcrypt), ativo, `orgao_id` → `organizacao`, ultimo_acesso |
| `acesso_papel` | codigo (único), nome, descricao, sistema, exige_orgao, todas |
| `acesso_papel_permissao` | papel_id, permissao (código do catálogo) |
| `acesso_usuario_papel` | usuario_id, papel_id |

## Permissões
Catálogo completo (`app/core/permissoes.py`) e papéis padrão:

| Permissão | Admin | Gerência GEDA | Equipe GEDA | Superintendência | Órgão publicador |
|---|:-:|:-:|:-:|:-:|:-:|
| painel.acessar | ✓ | ✓ | ✓ | ✓ | |
| inventario.acessar | ✓ | ✓ | ✓ | | |
| inventario.coletar | ✓ | ✓ | | | |
| pda.acessar | ✓ | ✓ | ✓ | | |
| pda.editar_vinculos | ✓ | ✓ | | | |
| pda.gerenciar_planos | ✓ | ✓ | | | |
| atualizacoes.acessar | ✓ | ✓ | ✓ | | |
| rastreabilidade.acessar | ✓ | ✓ | ✓ | | |
| lgpd.acessar | ✓ | ✓ | ✓ | | |
| lgpd.triar | ✓ | ✓ | | | |
| lgpd.aprovar_correcao | ✓ | ✓ | | | |
| metadados.acessar | ✓ | ✓ | ✓ | | |
| relatorios.acessar | ✓ | ✓ | ✓ | ✓ | |
| relatorios.exportar | ✓ | ✓ | ✓ | ✓ | |
| assistente.usar | ✓ | ✓ | ✓ | ✓ | |
| envio.acessar | ✓ | | | | ✓ |
| envio.enviar_recurso | ✓ | | | | ✓ |
| parametros.acessar | ✓ | ✓ | ✓ | | |
| parametros.editar | ✓ | ✓ | | | |
| ia.configurar | ✓ | | | | |
| acesso.gerenciar_usuarios | ✓ | ✓ | | | |
| acesso.gerenciar_papeis | ✓ | | | | |

Órgão publicador **exige órgão** vinculado. Os ajustes feitos na tela prevalecem sobre esta tabela.

**Permissão nova em banco já existente:** o Administrador a recebe sozinho (`todas`); os demais
papéis do sistema não mudam, porque `sincronizar_papeis_padrao` só cria papéis que faltam e não
sobrescreve ajustes. Conceda pela tela Usuários e papéis (ex.: `pda.gerenciar_planos`, criada em
07/10/2026, para a Gerência GEDA). A tabela acima vale para bancos novos.

## Interações com outros módulos
| Direção | Módulo | O quê |
|---|---|---|
| consome | inventario | `Organizacao` para o vínculo `usuario.orgao_id` e a lista de órgãos |
| é consumido por | todos | portão de permissões em toda rota (`require`, `autenticado`) |
| é consumido por | assistente, envio, pda | escopo de órgão (`filtrar_por_orgao`, `exigir_mesmo_orgao`) |
| é consumido por | frontend (shell) | `/acesso/me` define menu, rotas, widgets e botões |

## Jobs agendados
Nenhum. A sincronização de papéis roda na subida da API (`lifespan` em `main.py`).

## Regras de negócio e decisões
- Toda rota declara controle de acesso; a API não sobe sem isso.
- O sistema nunca fica sem administrador ativo (bloqueio ao remover/desativar o último).
- Só quem tem `acesso.gerenciar_papeis` concede o papel Administrador.
- Papel com `exige_orgao` obriga o usuário a ter órgão.
- Papéis do sistema não são excluídos e não mudam de código; o Administrador não é editável.
- O token JWT carrega só a identidade (expira em `GDA_JWT_EXPIRE_MINUTES`, padrão 8 h).
- Esconder um botão no frontend é conveniência; a verificação que vale é a do backend.

## Pendências
- Vincular usuário a órgão exige ao menos uma coleta (os órgãos vêm do inventário).
- Recuperação de senha por e-mail e login institucional (SSO do Estado) não estão no escopo.
- Trilha de auditoria de quem alterou papéis/usuários (hoje só `updated_at`).

## Histórico de alterações
| Data | Alteração | Autor |
|---|---|---|
| 30/09/2026 | Módulo `auth` com três perfis fixos substituído por RBAC: catálogo central, papéis, escopo de órgão, guarda de subida e tela Usuários e papéis | Claude / Victor |
| 07/10/2026 | Catálogo: `pda.gerenciar_planos` (importar PDA, definir o vigente e excluir PDA) para Administrador e Gerência GEDA; nota sobre permissão nova em banco existente | Claude / Humberto |
