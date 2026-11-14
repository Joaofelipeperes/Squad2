# ADR-0036 — Endurecer login, senhas, gestão de acesso, exportações e chamadas de saída antes de publicar na internet

| | |
|---|---|
| **Status** | Aceita |
| **Tipo** | Técnica |
| **Data da decisão** | 12/11/2026 |
| **Data do registro** | 12/11/2026 |
| **Decisores** | Victor Hugo Benatti (coordenação) |
| **Consultados** | — (repassar à Paloma os pontos que mudam o uso: senha inicial, regra de senha, bloqueio do login e limites de quem gerencia usuários e papéis) |
| **Origem** | Sessão de trabalho de 12/11/2026: avaliação de segurança no ambiente local e pedido de correção de todas as falhas (`docs/roteiro-teste-ciberseguranca.md`) |
| **Afeta** | `core/security.py`, `core/deps.py`, `core/config.py`, `core/rede.py` (novo), `core/exportacao.py` (novo), `main.py`; módulos `acesso`, `inventario`, `relatorios`, `rastreabilidade`, `ia`, `ckan_config`, `lgpd`; `docker-compose.prod.yml`, `deploy/`; revisa a ADR-0032 (senha inicial) |

## Contexto
A avaliação de segurança feita antes de o sistema ir para a internet mostrou que, sem login, nada
é entregue além de `/login` e `/saude`, e que o isolamento entre órgãos funciona. Mostrou também
falhas que um invasor ou um usuário interno poderia explorar:

- administrador inicial criado com a senha `12345` (ADR-0032 aceitava o risco até a primeira troca);
- quem gerencia usuários dava a si mesmo um papel mais forte; quem gerencia papéis marcava todas as
  permissões no próprio papel; um não administrador alterava papéis do sistema;
- a API não bloqueava tentativas de senha (só o nginx, por IP), o tempo de resposta revelava quais
  e-mails têm conta, senha com mais de 72 bytes dava erro 500 e senhas triviais eram aceitas;
- não havia troca da própria senha, e o token continuava valendo depois de a senha mudar;
- `/api/v1/docs`, `/api/v1/openapi.json` e `/redoc` ficavam abertos no servidor, e `/saude` descrevia
  o ambiente;
- a exportação de tabela em PDF ocupava a API por minutos com um único pedido grande;
- texto começando com `=` virava fórmula nas planilhas exportadas (os títulos vêm do CKAN);
- as chamadas para fora (provedor de IA, perfil do CKAN, link de recurso baixado na varredura LGPD)
  não tinham restrição de destino, e o erro do provedor de IA devolvia o corpo da resposta.

Restrições: sem serviço novo (ADR-0001, infraestrutura leve), sem mudança de tabela a duas semanas
da entrega, e a GEDA (papel Gerência de Dados Abertos) precisa continuar cadastrando usuários.

## Critérios de decisão
1. Fechar o que é explorável pela internet ou por um usuário comum.
2. Não quebrar o uso atual da GEDA nem exigir migração de banco.
3. Código pequeno, testável, sem dependência nova.

## Opções consideradas

### Senha inicial do administrador
- **A — senha aleatória gerada na primeira subida e mostrada uma vez no log** (escolhida). **Prós:**
  nenhuma instalação nasce com senha conhecida; não precisa de `.env`. **Contras:** a senha fica no log
  do container até ele girar; quem instala precisa ler o log.
- **B — exigir `GDA_ADMIN_INICIAL_SENHA` e não subir sem ela.** Prós: nada no log. **Contras:** quebra o
  "sobe sem `.env`" da ADR-0032.
- **C — manter `12345` com aviso.** **Contras:** é o risco que motivou esta ADR.

### Limites de quem gerencia usuários e papéis sem ser administrador
- **A — "ninguém concede o que não tem", sem exceção.** Prós: regra simples. **Contras:** a Gerência de
  Dados Abertos não conseguiria mais cadastrar o Órgão publicador nem a Equipe GEDA (papéis com
  permissões que ela não tem).
- **B — papéis do sistema são concedíveis por qualquer gestor de usuários e só alteráveis por
  administrador; papel personalizado só é concedido, alterado ou excluído por quem tem todas as
  permissões dele; ninguém altera os próprios papéis nem um papel que possui** (escolhida). **Prós:**
  fecha os três caminhos de escalada e mantém o fluxo da GEDA. **Contras:** regra com mais casos.
- **C — só administrador gerencia usuários e papéis.** **Contras:** tira da GEDA uma atribuição dela.

### Tentativas de login
- **A — bloqueio por e-mail contando as recusas no log de acesso** (escolhida): 10 senhas erradas
  em 15 minutos → 429 até a janela passar; login certo zera. **Prós:** sem tabela nova, vale também
  para quem chega sem passar pelo nginx. **Contras:** alguém pode travar de propósito a conta de outra
  pessoa por até 15 minutos.
- **B — só o limite por IP do nginx (como estava).** **Contras:** não protege uma conta de tentativas
  vindas de muitos endereços.
- **C — CAPTCHA.** **Contras:** serviço externo, fora do escopo.

### Sessão depois da troca de senha
- **A — marca da senha no token** (escolhida): o token leva um resumo do hash da senha; mudou a
  senha, os tokens antigos caem. **Prós:** sem tabela nem coluna nova. **Contras:** sair (logout) continua
  sem revogar o token no servidor.
- **B — tabela de sessões ou versão de sessão no usuário.** Prós: revoga também no logout. **Contras:**
  migração e leitura extra a cada requisição; fica como evolução.

### Chamadas para fora
- **A — dois níveis** (escolhida): endereço digitado por administrador (IA, CKAN) aceita rede
  interna (o Ollama e o CKAN local são internos), mas só `http`/`https` e fora da faixa link-local;
  link de recurso (vem de fora) não pode apontar para a rede interna, e cada redirecionamento é
  conferido. **Contras:** a conferência resolve o nome antes da chamada; troca de DNS entre a
  conferência e a chamada não é coberta.
- **B — bloquear toda rede interna.** **Contras:** inviabiliza a IA local (ADR-0002).

## Decisão
Adotar as opções marcadas acima e, junto:

- regra de senha: de 8 caracteres a 72 bytes, com letras e números, fora de uma lista de senhas
  comuns e sem repetir o e-mail; vale para o cadastro, a edição e a troca da própria senha;
- `POST /acesso/me/senha`: qualquer usuário troca a própria senha informando a atual;
- e-mail inexistente gasta o mesmo tempo de verificação de um existente;
- documentação da API só em `dev` (ou com `GDA_API_DOCS=true`); `/redoc` desligado; `/saude` responde
  só `{"status": "ok"}`;
- a API recusa corpo maior que 6 MB (o mesmo limite do nginx) e parâmetros `limite` fora da faixa;
- exportação de tabela: célula de até 2.000 caracteres; PDF de até 5.000 linhas e 1,5 milhão de
  caracteres;
- planilhas: no XLSX, texto começando com `=` é gravado como texto; no CSV, texto começando com
  `= + - @` ganha um apóstrofo (números ficam como estão);
- erro de provedor de IA mostra só a mensagem de erro do provedor, nunca o corpo bruto;
- front-end: link vindo do CKAN só vira link se for `http`/`https`;
- quem não vê o inventário não recebe o e-mail de quem pediu a última coleta.

## Consequências
- **Positivas:** as falhas do roteiro deixam de ser exploráveis; cada uma tem teste automatizado
  (`tests/test_seguranca.py`).
- **Negativas e riscos:**
  - todos os usuários precisam entrar de novo depois da atualização (tokens antigos não têm a marca
    da senha);
  - em homologação a documentação da API some; para tê-la, `GDA_API_DOCS=true` no `.env`;
  - senhas já cadastradas que não cumprem a regra continuam valendo até serem trocadas;
  - o bloqueio de login pode ser usado para travar uma conta por 15 minutos;
  - a senha inicial gerada fica no log do container: trocá-la no primeiro acesso;
  - sair não revoga o token no servidor (expira em 8 h);
  - a mensagem "Já existe um usuário com este e-mail" continua indicando, a quem gerencia usuários,
    que um e-mail fora da lista dele pertence a um administrador (o e-mail é único no sistema).

## Validação
Testes automatizados e reteste ao vivo no ambiente local em 12/11/2026. Repassar à Paloma as
mudanças de uso (senha inicial, regra de senha, bloqueio e limites da gestão de acesso).

## Revisões
| Data | Revisão | Autor |
|---|---|---|
