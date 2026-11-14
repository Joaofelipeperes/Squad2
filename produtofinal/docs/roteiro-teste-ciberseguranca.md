# Roteiro de teste de cibersegurança — Monitor Dados Abertos GO

Roteiro para repetir antes de cada publicação do sistema na internet. Cada item tem o que fazer,
o resultado esperado e a situação encontrada na avaliação de 12/11/2026 (ambiente local:
`http://localhost:8080`, API `http://localhost:8000`, nginx de produção construído à parte).

Legenda da situação: **OK** = passou · **FALHA** = corrigir · **ATENÇÃO** = risco aceito ou a decidir ·
**NÃO TESTADO** = verificar à mão.

## 0. Preparação

1. Subir o ambiente local (`docker compose up -d`) e, para os itens da seção 7, a imagem de
   produção do front-end (`docker build ./frontend` e rodar na rede do compose, em outra porta).
2. Criar usuários de teste, um por perfil, com a mesma senha de teste:
   administrador · gerente (gerencia usuários) · analista sem órgão · analista vinculado a um órgão ·
   superintendência · usuário sem nenhum papel · usuário só com `acesso.gerenciar_papeis`.
3. Guardar o token de cada um (`POST /api/v1/acesso/login`).
4. Ao final, excluir os usuários e papéis de teste.

Nunca rodar este roteiro contra o servidor da UFG/CGE sem autorização formal e janela combinada.

## 1. Acesso sem login

| # | Teste | Esperado | Situação |
|---|-------|----------|----------|
| 1.1 | Chamar todas as rotas do `openapi.json`, em todos os métodos, sem token | 401 em tudo, exceto `/acesso/login` e `/saude` | OK (80 rotas) |
| 1.2 | `GET /api/v1/saude` | Só `{"status":"ok"}` | OK (corrigido em 12/11: responde só `{"status":"ok"}`) |
| 1.3 | `GET /api/v1/docs`, `/api/v1/openapi.json`, `/redoc` | 404 em produção | OK (corrigido: 404 fora de `dev`; `GDA_API_DOCS=true` liga) |
| 1.4 | Caminhos comuns: `/.env`, `/admin`, `/metrics`, `/static/` | 404 ou a tela inicial (sem conteúdo sensível) | OK |
| 1.5 | Variações de caminho: barra dupla, maiúsculas, `%2f`, `..` | 401/404, nunca dado | OK |
| 1.6 | Token inválido: lixo, `alg: none`, assinado com a chave de exemplo do repositório, com `sub` trocado | 401 | OK |
| 1.7 | Cabeçalhos alternativos (`Basic`, cookie, `X-Forwarded-User`) | 401 | OK |
| 1.8 | Subir a API fora de `dev` com chave JWT de exemplo ou curta | A API não inicia | OK (validado no código, `core/config.py`) |

## 2. Login e sessão

| # | Teste | Esperado | Situação |
|---|-------|----------|----------|
| 2.1 | 40 senhas erradas seguidas para o mesmo e-mail, direto na API | Bloqueio temporário da conta ou atraso crescente | OK (corrigido: 429 a partir da 11ª tentativa em 15 min, por e-mail) |
| 2.2 | Medir o tempo de resposta do login com e-mail existente e inexistente | Tempos iguais | OK (corrigido: ~224 ms contra ~222 ms) |
| 2.3 | Senha com mais de 72 caracteres | 401 ou 422 | OK (corrigido: 401) |
| 2.4 | Senha de 1 MB e corpo de 20 MB sem login | 413/422 | OK (corrigido: a API também responde 413 acima de 6 MB) |
| 2.5 | Injeção de SQL no e-mail e na senha; byte nulo; tipos errados | 401/422 | OK |
| 2.6 | Campos extras no corpo (`administrador: true`, `papel_ids`) | Ignorados | OK |
| 2.7 | Senha inicial do administrador no servidor | Senha aleatória ou troca obrigatória no 1º acesso | OK (corrigido: senha aleatória mostrada uma vez no log da API) |
| 2.8 | Política de senha ao criar usuário | Recusar senhas triviais | OK (corrigido: exige letras e números, recusa senhas comuns e o próprio e-mail) |
| 2.9 | Usuário comum trocar a própria senha | Tela/rota própria | OK (corrigido: botão da chave na barra lateral, `POST /acesso/me/senha`) |
| 2.10 | Usar o token antigo depois de trocar a senha | 401 | OK (corrigido: 401) |
| 2.11 | Usar o token depois de desativar o usuário | 401 | OK |
| 2.12 | Sair (logout) e reusar o token | 401 | **ATENÇÃO** — não há revogação no servidor |
| 2.13 | Onde o navegador guarda o token | Fora do alcance de scripts, ou `sessionStorage` com CSP forte | OK (`sessionStorage` + CSP) |

## 3. Permissões (quem pode o quê)

| # | Teste | Esperado | Situação |
|---|-------|----------|----------|
| 3.1 | Matriz: cada rota de leitura com cada perfil | 200 só com a permissão declarada; 403 no resto | OK |
| 3.2 | Rotas de escrita (POST/PUT/DELETE) com analista, superintendência e sem papel | 403 | OK |
| 3.3 | Quem gerencia usuários editar um administrador, ou dar a si o papel Administrador | 404 / 422 | OK |
| 3.4 | Quem gerencia usuários dar **a si mesmo** um papel com permissões que não tem | Recusar | OK (corrigido: 422; ninguém altera os próprios papéis) |
| 3.5 | Quem só gerencia papéis editar **o próprio papel** e marcar todas as permissões | Recusar | OK (corrigido: 422; ninguém altera um papel que possui nem inclui permissão que não tem) |
| 3.6 | Não administrador alterar papel do sistema (ex.: esvaziar `gerente_geda`) | Recusar | OK (corrigido: 422; papel do sistema só administrador altera) |
| 3.7 | Quem gerencia usuários trocar a senha de outro usuário e entrar como ele | Registrar e avisar, ou exigir troca no próximo acesso | **ATENÇÃO** — permitido só sobre usuários cujos papéis o gestor pode conceder; a sessão do usuário cai, mas ele não é avisado |
| 3.8 | Criar usuário com o e-mail de um administrador oculto | Mensagem neutra | **ATENÇÃO** — inerente ao e-mail único: a recusa indica que o e-mail já tem conta |
| 3.9 | Remover o último administrador ativo | Bloqueado | OK (validado no código) |
| 3.10 | `GET /inventario/coletas/ultima` com usuário sem papel | Sem dado de terceiros | OK (corrigido: o e-mail só aparece para quem vê o inventário) |

Regra implementada (ADR-0036): quem não é administrador não altera os próprios papéis, não
concede nem altera papel personalizado com permissão que não tem, e não altera papel do sistema
nem um papel que possui. Papéis do sistema continuam concedíveis por quem gerencia usuários.

## 4. Isolamento entre órgãos

Com o analista vinculado ao órgão A, comparar com o analista sem órgão.

| # | Teste | Esperado | Situação |
|---|-------|----------|----------|
| 4.1 | Listas: datasets, bases do PDA, atualizações, achados LGPD, varreduras, correções, eventos, organizações, relatórios | Só registros do órgão A | OK |
| 4.2 | Abrir por id um registro do órgão B: dataset, achado, base, diff de evento, correção | 404 | OK |
| 4.3 | Filtro `orgao=B` nas listas e relatório do órgão B (prévia e exportação) | Vazio / 404 | OK |
| 4.4 | Perguntar ao Assistente sobre outros órgãos | Só o órgão A no contexto | OK |
| 4.5 | Dashboard (indicadores) | Números só do órgão A | OK |

## 5. Dados entregues

| # | Teste | Esperado | Situação |
|---|-------|----------|----------|
| 5.1 | Listas de perfis de IA e de CKAN | Só a dica da chave (`••••1a2b`), nunca o segredo | OK |
| 5.2 | Respostas de usuário (`/me`, `/usuarios`) | Sem hash de senha | OK |
| 5.3 | Detalhe de achado LGPD | Sem o valor pessoal em claro para quem não deve ver | **NÃO TESTADO** — conferir exemplos e explicação com a GEDA |
| 5.4 | Arquivo original da anonimização | Nunca servido pela API | OK (só a prévia anonimizada, com permissão de aprovar) |
| 5.5 | Mensagens de erro | Sem pilha de execução nem SQL | OK (corrigido: `limite` inválido dá 422) |
| 5.6 | Log de acesso | Só para `acesso.ver_logs`; sem senha nem token | OK |

## 6. Entradas, arquivos e integrações

| # | Teste | Esperado | Situação |
|---|-------|----------|----------|
| 6.1 | Exportar para Excel/CSV uma célula que começa com `=`, `+`, `-` ou `@` | Gravada como texto | OK (corrigido: XLSX grava como texto; CSV antepõe apóstrofo) |
| 6.2 | `POST /relatorios/tabela/exportar` em PDF com 20.000 linhas × 30 colunas | Recusar ou responder rápido | OK (corrigido: 413/422 em menos de 1 s; o maior PDF aceito, 5.000 linhas, leva ~13 s) |
| 6.3 | Título da exportação com aspas e quebra de linha | Nome de arquivo limpo, sem cabeçalho injetado | OK (quebra de linha dá 500, sem injeção) |
| 6.4 | Planilha do PDA: extensão errada, mais de 5 MB, `.xlsx` "bomba" de compressão | 422 / 413 | OK (validado no código) |
| 6.5 | CORS com origem estranha | Sem `Access-Control-Allow-Origin` | OK |
| 6.6 | URL de provedor de IA, de perfil do CKAN e de recurso externo apontando para a rede interna | Recusar endereços internos e não devolver o corpo da resposta | OK (corrigido, verificado por teste automatizado: link de recurso para a rede interna não é baixado, redirecionamento é conferido, erro de IA não devolve o corpo) |
| 6.7 | Link de recurso com esquema `javascript:` vindo do CKAN | Só `http`/`https` viram link | OK (corrigido: só `http`/`https` viram link) |
| 6.8 | Nome com `<script>` em usuário, papel, PDA | Exibido como texto | OK (React, sem `dangerouslySetInnerHTML`) |
| 6.9 | Texto malicioso em descrição de dataset lido pelo Assistente | Não muda o comportamento nem vaza dados | **NÃO TESTADO** |

## 7. Servidor e publicação (nginx de produção)

| # | Teste | Esperado | Situação |
|---|-------|----------|----------|
| 7.1 | Cabeçalhos das telas | CSP, `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy`, `Permissions-Policy`, COOP | OK |
| 7.2 | `Server` | Sem versão | OK |
| 7.3 | 16 logins seguidos pelo nginx | 429 depois da rajada | OK (a partir do 13º) |
| 7.4 | Corpo de 8 MB | 413 | OK |
| 7.5 | Mapas de código (`.map`) no build | Nenhum | OK |
| 7.6 | HSTS e certificado | Presentes no proxy que faz o TLS | **NÃO TESTADO** (depende do proxy da UFG/CGE) |
| 7.7 | Porta 8080 (HTTP) aberta direto para a internet | Fechada; só o proxy alcança | **ATENÇÃO** — padrão `0.0.0.0`; definir `GDA_IP_PUBLICACAO` |
| 7.8 | `GDA_PROXY_CONFIAVEL` | IP do proxy informado | **ATENÇÃO** — sem ele, todos os usuários dividem o limite de login e o log grava o IP do proxy |
| 7.9 | API e banco sem porta publicada; containers sem root; segredos gerados | Conforme `docker-compose.prod.yml` | OK (validado no arquivo) |
| 7.10 | Dependências com falha conhecida (`pip-audit`, `npm audit`) | Sem alta/crítica | **NÃO TESTADO** |
| 7.11 | Backup: restaurar em ambiente de teste | Restaura e a chave de criptografia está guardada | **NÃO TESTADO** |

## 8. Situação depois das correções (12/11/2026)

As falhas marcadas acima como corrigidas estão registradas na ADR-0036 e cobertas por
`backend/tests/test_seguranca.py`. Continuam em aberto:

1. Sair (logout) não revoga o token no servidor; ele expira em 8 h (2.12).
2. Itens de implantação: HSTS e certificado no proxy (7.6), porta 8080 aberta para todas as
   interfaces por padrão (7.7), `GDA_PROXY_CONFIAVEL` (7.8).
3. Não testados: valor pessoal no detalhe de achado (5.3), texto malicioso lido pelo Assistente
   (6.9), dependências com falha conhecida (7.10), restauração de backup (7.11).
4. O bloqueio de login pode ser usado para travar a conta de outra pessoa por 15 minutos.

Ao repetir o roteiro: o teste 2.1 bloqueia o e-mail usado por 15 minutos; use um e-mail de teste.
