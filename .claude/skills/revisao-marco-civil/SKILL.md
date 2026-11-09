---
name: revisao-marco-civil
description: Revisa o código quanto à conformidade com o Marco Civil da Internet (Lei 12.965/2014) e seu regulamento (Decreto 8.771/2016) — registros de acesso a aplicações (log com IP, data e hora), guarda e sigilo desses registros, padrões de segurança, transparência e consentimento na coleta. Use quando o usuário pedir revisão de Marco Civil, de logs de acesso, de guarda de registros ou de IP do usuário.
---

# Revisão de conformidade com o Marco Civil da Internet

Você revisa **código** procurando pontos em que a aplicação web descumpre ou não demonstra
cumprimento do Marco Civil (MCI, Lei 12.965/2014) e do Decreto 8.771/2016. O sistema é um
**provedor de aplicações de internet** (não de conexão), então os deveres relevantes são os de
registros de acesso a aplicações, proteção desses registros e direitos dos usuários. Gere um
relatório com arquivo:linha, dispositivo legal e correção. Não é parecer jurídico: diga isso.

## Regras invioláveis

- **Nada sai da máquina.** Não envie código, trechos ou dados a serviços externos, MCPs remotos,
  APIs de IA de terceiros nem buscas na web. Só leitura local (Read, Grep, Glob, git).
- Não altere código durante a revisão. Não abra `.env` nem bases com registros reais.

## Escopo

1. Arquivos/pasta indicados pelo usuário; senão o diff da branch contra a base
   (`git diff --merge-base origin/desenvolvimento`, ou `origin/main`).
2. Para revisão completa, priorize: o middleware/rota que grava o log de acesso
   (`backend/app/main.py`, `backend/app/core/deps.py`, `backend/app/modules/acesso`), configuração
   de proxy reverso (`produtofinal/deploy/`, `frontend/nginx.conf`, `Dockerfile`s), telas e rotas que
   consultam/exportam o log, rotinas de expurgo no worker, aviso de privacidade/termos no frontend.
3. Leia antes `produtofinal/AGENTS.md` e as ADRs sobre log e acesso (ex.: 0005, 0016, 0019) para
   entender finalidade e decisões já tomadas.

## Aplicabilidade — avalie e registre no relatório

- **Art. 15 (guarda obrigatória por 6 meses)** obriga o provedor de aplicações "constituído na forma
  de pessoa jurídica" que exerce a atividade "com fins econômicos". Órgão público pode não se
  enquadrar literalmente; trate a guarda de 6 meses como **referência de boa prática e de
  investigação de incidentes**, marcando a obrigatoriedade como "A confirmar com a assessoria
  jurídica do órgão". Os demais deveres (sigilo, segurança, transparência, minimização) valem.
- O log de acesso também é dado pessoal (IP, usuário, user-agent): cruze com a skill
  `revisao-lgpd` quando o achado envolver finalidade, retenção ou direitos do titular.

## Checklist

### Conteúdo do registro de acesso (MCI art. 5º, VIII; art. 15)
- [ ] Cada acesso registra **data e hora** com fuso horário explícito (UTC ou offset gravado; não
      hora local ambígua) e fonte de tempo confiável (relógio do servidor, não do cliente).
- [ ] Registra o **IP de origem real do usuário**. Atrás de proxy reverso/load balancer, o IP deve
      vir de `X-Forwarded-For`/`X-Real-IP` **somente** quando a requisição vem de proxy confiável
      (lista fixa de IPs/redes). Aceitar o cabeçalho de qualquer origem permite forjar o IP.
- [ ] Recomendado: **porta lógica de origem** (necessária para identificar usuário atrás de
      CGNAT; jurisprudência do STJ a exige de provedores). Marque como observação se faltar.
- [ ] O registro identifica a aplicação/recurso acessado e o usuário autenticado, sem gravar
      **conteúdo** das comunicações (corpo de requisição, senhas, tokens, parâmetros sensíveis).

### Sigilo e disponibilização (MCI arts. 10, 13 §§, 15 §§, 22–23)
- [ ] Registros só são acessíveis a perfis autorizados (verifique permissão na rota de consulta e
      exportação). Usuário comum não vê registros de terceiros.
- [ ] Não há rota pública, endpoint de debug, arquivo estático ou exportação sem autenticação que
      exponha os registros.
- [ ] A entrega de registros a terceiros pressupõe ordem judicial (art. 10 §1º, art. 22) — não deve
      haver integração que os envie automaticamente a serviços externos.

### Padrões de segurança dos registros (Decreto 8.771/2016, art. 13)
- [ ] **I — controle estrito de acesso** aos registros, com responsabilidades definidas.
- [ ] **II — autenticação** de quem acessa os registros (idealmente com segundo fator para
      administradores; registre a ausência como Média).
- [ ] **III — inventário dos acessos aos registros**: quem consultou/exportou o log, quando e o
      quê. Consultar o próprio log de acesso deve gerar trilha.
- [ ] **IV — inviolabilidade**: o log não pode ser alterado/apagado pela aplicação nem por usuários
      (sem rota de UPDATE/DELETE, permissões de banco restritas, append-only, hash encadeado ou
      exportação periódica assinada são boas soluções).

### Minimização e eliminação (MCI art. 7º, X; art. 16; Decreto 8.771, art. 13 §2º)
- [ ] Guarda só o necessário à finalidade; dados excessivos (corpo inteiro, cabeçalhos completos,
      cookies) violam o art. 16, II.
- [ ] Há rotina de expurgo/anonimização após o prazo definido (ex.: 6 meses + prazo de retenção
      justificado). Guardar para sempre também é problema.
- [ ] Não registra acessos a **outras** aplicações (ex.: rastreadores de terceiros) sem
      consentimento (art. 16, I).

### Direitos e transparência para o usuário (MCI art. 7º, VI–XI)
- [ ] Usuário é informado, de forma clara, da coleta e guarda dos registros e da finalidade
      (aviso de privacidade/termos acessível na aplicação).
- [ ] Coleta de dados para além do necessário à prestação do serviço exige consentimento
      expresso e destacado (art. 7º, IX) — cookies de analytics, rastreadores, pixels, fontes/CDNs
      de terceiros que recebem o IP.
- [ ] Dados não são fornecidos a terceiros sem consentimento ou hipótese legal (art. 7º, VII).

## Severidade

- **Alta** — registros expostos a quem não deveria, IP forjável aceito como verdadeiro, log
  alterável/apagável pela aplicação, conteúdo sensível (senha/token) gravado no log.
- **Média** — falta de inventário de acesso aos registros, sem 2º fator para quem consulta, sem
  expurgo, data/hora sem fuso, falta de aviso ao usuário.
- **Baixa / Observação** — porta lógica ausente, melhorias de documentação.

Só reporte o que verificou. Dependências de produção (relógio NTP, permissões do banco, proxy real
da UFG) vão em **"A confirmar"**.

## Formato do relatório

```markdown
# Revisão Marco Civil da Internet — <escopo> — <data>

> Revisão automatizada de código. Aponta riscos; não substitui parecer jurídico.

## Resumo
<2–4 frases, incluindo a conclusão sobre aplicabilidade do art. 15>

## Achados
### [ALTA] <título>
- **Onde:** `caminho/arquivo.py:123`
- **O que acontece:** <descrição concreta>
- **Fundamento:** Lei 12.965/2014 art. X / Decreto 8.771/2016 art. 13, inciso Y (+ ADR, se houver)
- **Correção sugerida:** <ação objetiva>

## A confirmar
## Pontos positivos
```

Ordene por severidade. Mostre no chat; grave em arquivo só se o usuário pedir.
