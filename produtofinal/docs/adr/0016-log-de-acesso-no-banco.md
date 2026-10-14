# ADR-0016 — Registrar toda requisição à API numa tabela de log de acesso no banco

| | |
|---|---|
| **Status** | Aceita |
| **Tipo** | Técnica |
| **Data da decisão** | 14/10/2026 |
| **Data do registro** | 14/10/2026 |
| **Decisores** | Victor Hugo Benatti (coordenação) |
| **Consultados** | — |
| **Origem** | Sessão de trabalho de 14/10/2026; modelo de referência: planilha `LogsDeAcessos.xlsx` |
| **Afeta** | Módulo `acesso`; `backend/app/main.py`; `backend/app/core/deps.py`; `backend/Dockerfile`; `frontend/nginx.conf` |

## Contexto
A coordenação pediu um log que registre tudo o que o usuário faz na solução, no formato de uma
planilha de referência: uma linha por requisição com data, IP, usuário, URI, controller/ação,
método HTTP, resposta e user-agent. Até aqui só existiam trilhas pontuais (`lgpd_decisao`,
`*.alterado_por`, `usuario.ultimo_acesso`). Funcionalidade fora do Backlog v2.

Toda ação do usuário passa pela API (o frontend é estático no nginx), e toda rota já passa pelo
portão `get_current_user` (ADR-0005), que conhece o usuário. IP e user-agent de servidores são dado
pessoal (LGPD); o registro tem finalidade de segurança e auditoria.

## Critérios de decisão
1. Consultável e filtrável por usuário e período, como a planilha.
2. Cobrir toda rota sem depender de cada módulo lembrar de registrar.
3. Infraestrutura leve, sem serviço novo (PGP v2).
4. Falha no log não pode derrubar a ação do usuário.

## Opções consideradas

### Opção A — Tabela `acesso_log` no banco, gravada por middleware HTTP
- **Prós:** uma linha por requisição, de qualquer módulo, sem código nos módulos; consulta por SQL
  e por rota protegida (`GET /acesso/logs`); exportável como a planilha; mesmo backup do banco.
- **Contras:** um INSERT por requisição; a tabela cresce sem expurgo; IP vira dado pessoal guardado.

### Opção B — Arquivo de log estruturado (JSON por linha) no stdout/arquivo
- **Prós:** custo quase zero por requisição; padrão de mercado para observabilidade.
- **Contras:** consulta exige ferramenta externa (grep, Loki, ELK); some com o container se não houver
  volume ou coletor; não dá para mostrar numa tela da solução sem infraestrutura nova.

### Opção C — Registro explícito em cada rota (`registrar(acao, ...)`)
- **Prós:** registra só ações de negócio, com descrição rica (antes/depois).
- **Contras:** depende de disciplina em cada módulo; rota nova sem chamada fica fora; não cobre
  leituras, que a planilha de referência inclui.

## Decisão
Opção A. Cobre tudo automaticamente (critério 2), é consultável pela própria solução (critério 1) e
usa o banco que já existe (critério 3). O middleware grava em sessão própria, numa thread, depois da
resposta, e engole erro do log (critério 4).

Detalhes:
- Colunas: `ocorrido_em`, `usuario` (e-mail congelado, sem FK — convenção de auditoria), `metodo`,
  `caminho` (com query string), `rota` (modelo, ex.: `/api/v1/acesso/papeis/{papel_id}`), `acao`
  (nome da função), `status_http`, `ip`, `user_agent`.
- Não registra `OPTIONS` (preflight CORS) nem `/saude`. Não guarda corpo de requisição nem resposta
  (senhas, planilhas e perguntas ao Assistente ficam de fora).
- O login registra o e-mail informado também quando falha (detecção de tentativas).
- IP real: o nginx sobrescreve `X-Forwarded-For` com `$remote_addr` e o uvicorn confia no cabeçalho
  (`--forwarded-allow-ips '*'`).
- Consulta restrita à permissão nova `acesso.ver_logs` (sensível; só Administrador por padrão).

## Consequências
- **Positivas:** auditoria de quem fez o quê, quando e de onde, inclusive acessos negados (403) e
  logins com falha; base para uma tela de consulta e exportação.
- **Negativas e riscos:**
  - Crescimento contínuo: o polling da Topbar gera ~1 linha por minuto por aba aberta. Tratar com
    expurgo agendado (`JobSpec`) quando o prazo de retenção for definido (referência: 6 meses do
    art. 15 do Marco Civil da Internet).
  - Com a porta 8000 da API exposta (docker-compose de desenvolvimento), quem chama a API direto
    pode forjar `X-Forwarded-For`. Em produção só o nginx deve alcançar a API.
  - Não registra o antes/depois de alterações; para isso, trilha por entidade (opção C) pontual.

## Validação
Aceita pela coordenação (Victor) em 14/10/2026. Retenção e finalidade do tratamento do IP a
validar com a Paloma (LGPD), junto da inclusão no escopo.

## Revisões
| Data | Revisão | Autor |
|---|---|---|
