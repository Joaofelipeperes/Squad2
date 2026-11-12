---
name: revisao-lgpd
description: Revisa o código quanto à conformidade com a LGPD (Lei 13.709/2018), com foco no tratamento de dados pessoais pelo poder público. Use quando o usuário pedir revisão de LGPD, privacidade, proteção de dados pessoais, dados sensíveis, anonimização, retenção/eliminação de dados ou direitos do titular — no diff da branch ou num módulo/pasta indicado.
---

# Revisão de conformidade com a LGPD

Você revisa **código** (não documentos jurídicos) procurando pontos em que o tratamento de dados
pessoais contraria ou não demonstra conformidade com a LGPD. O resultado é um relatório de achados
com arquivo:linha, artigo da lei e correção sugerida. Não é parecer jurídico: diga isso no relatório.

## Regras invioláveis

- **Nada sai da máquina.** Não envie código, trechos, nomes de tabelas nem dados para serviços
  externos, MCPs remotos, APIs de IA de terceiros ou sites. Use só leitura local (Read, Grep, Glob,
  git). Não faça buscas na web com trechos do código.
- Não altere código durante a revisão. Correções só se o usuário pedir depois.
- Não abra nem copie arquivos `.env`, chaves ou bases com dados reais; apenas registre que existem
  e se estão protegidos (ex.: no `.gitignore`).

## Escopo

1. Se o usuário indicou arquivos, pasta ou módulo, revise isso.
2. Senão, revise o diff da branch atual contra a base:
   `git diff --merge-base origin/desenvolvimento` (ou `origin/main` se `desenvolvimento` não existir).
3. Se pedirem "o projeto todo", priorize: modelos e migrações (`backend/app/modules/*/models.py`,
   `backend/alembic/versions`), `backend/app/modules/lgpd`, `acesso`, `rastreabilidade`, `envio`,
   `assistente`, `ia`, `backend/app/integrations/`, `backend/app/core/`, logs e o frontend que exibe
   ou exporta dados.

Antes de julgar, leia o contexto do projeto: `produtofinal/AGENTS.md` e as ADRs em
`produtofinal/docs/adr/` que tratam de dados pessoais, IA e logs (ex.: 0002, 0008, 0010, 0011, 0016,
0019, 0020, 0021, 0025). Uma decisão registrada em ADR não torna algo conforme, mas mostra a
finalidade e a base legal pretendidas — cite a ADR no achado.

## Contexto jurídico a considerar

O sistema é operado por órgão público (CGE-GO). Aplicam-se, além das regras gerais:
- **Cap. IV (arts. 23–32):** tratamento pelo poder público para execução de políticas públicas e
  competências legais; dever de informar hipóteses de tratamento; uso compartilhado (arts. 25–27).
- **Base legal (art. 7º, III e art. 11, II, b)**: normalmente execução de políticas públicas ou
  cumprimento de obrigação legal, não consentimento.
- **Interação com a LAI (Lei 12.527/2011)** e com o Decreto estadual 10.176/2022 (dados abertos):
  publicar dado aberto não pode expor dado pessoal sem base legal; informação pessoal tem acesso
  restrito (LAI art. 31).

## Checklist (verifique cada item; registre só o que achar)

### Inventário e finalidade
- [ ] Quais campos/tabelas guardam dado pessoal (nome, CPF, e-mail, IP, user-agent, matrícula,
      telefone, endereço, geolocalização) ou **sensível** (saúde, biometria, religião, etnia,
      opinião política, filiação sindical, vida sexual — art. 5º, II)?
- [ ] Cada dado pessoal tem finalidade identificável no código/ADR (art. 6º, I)? Campos coletados
      "por via das dúvidas" violam **necessidade/minimização** (art. 6º, III).
- [ ] Dado coletado para uma finalidade é reutilizado para outra incompatível (art. 6º, II)?

### Segurança (arts. 46–49) — sobreposição com ISO 27001
- [ ] Dados pessoais e sensíveis protegidos em repouso quando necessário (criptografia de campo,
      hash de identificadores, chaves fora do código)?
- [ ] Senhas com hash forte (bcrypt/argon2), nunca reversível.
- [ ] Controle de acesso por papel/órgão aplicado em **toda** rota que retorna dado pessoal
      (verifique o portão em `core/deps.py` e se a rota o usa).
- [ ] Dados pessoais não vão para logs, mensagens de erro, stack traces, URLs/query strings,
      analytics ou cache do navegador.

### Anonimização e publicação
- [ ] O processo de anonimização é de fato irreversível com meios razoáveis (art. 12)? Mascaramento
      parcial (ex.: `***.123.456-**`) ou pseudonimização com chave guardada é **pseudonimização**
      (art. 13, §4º), e o dado continua pessoal.
- [ ] Antes de publicar no CKAN há aprovação humana e verificação de que não restou dado pessoal?
- [ ] Detectores de dado pessoal: há falsos negativos óbvios (CPF sem máscara, nomes em texto livre,
      colunas renomeadas)? Arquivos não tabulares ficam sem verificação?

### Compartilhamento e terceiros (arts. 26, 33–36)
- [ ] Algum dado pessoal é enviado a serviço externo (IA comercial, e-mail, telemetria, CDN,
      fontes externas)? Para IA, confira a política em `integrations/ai/` e se ela é aplicada
      antes de **toda** chamada, inclusive prompts montados com dados de usuários.
- [ ] Transferência internacional (servidor do provedor fora do Brasil) sem hipótese do art. 33.
- [ ] Bibliotecas de frontend carregadas de CDN de terceiros que recebem IP do usuário.

### Retenção e eliminação (arts. 15–16)
- [ ] Existe prazo e rotina de eliminação para logs e dados pessoais? Exclusão lógica (soft delete)
      mantém o dado indefinidamente — registre se não houver expurgo posterior.
- [ ] Backups, exportações (PDF/CSV) e arquivos temporários com dados pessoais são limpos?

### Direitos do titular (arts. 18–22) e transparência (art. 9º, art. 23, I)
- [ ] É possível localizar, exportar, corrigir e eliminar os dados de um titular (usuário do sistema)?
- [ ] Há informação ao usuário sobre o tratamento (aviso de privacidade, finalidade do log de acesso)?

### Registro e governança (arts. 37, 38, 41, 48)
- [ ] As operações de tratamento ficam registradas (quem acessou/alterou/publicou dado pessoal)?
- [ ] Incidentes: há como detectar e reconstituir um vazamento (logs suficientes, sem dado pessoal
      em excesso)? Registre a ausência de procedimento de comunicação à ANPD só como observação.

## Severidade

- **Alta** — exposição efetiva ou provável de dado pessoal/sensível (rota sem autorização, dado em
  log público, envio a terceiro, publicação sem anonimização, segredo no repositório).
- **Média** — falta de controle exigido pela lei sem exposição demonstrada (sem retenção, sem
  minimização, pseudonimização tratada como anonimização).
- **Baixa / Observação** — melhoria de demonstração de conformidade (documentação, registro, aviso).

Só reporte o que você verificou no código. Se depender de configuração de produção ou de processo
que não está no repositório, marque como **"A confirmar"** e diga o que precisa ser checado.

## Formato do relatório

```markdown
# Revisão LGPD — <escopo> — <data>

> Revisão automatizada de código. Aponta riscos; não substitui parecer jurídico nem a avaliação
> do encarregado (DPO) do órgão.

## Resumo
<2–4 frases: quantos achados por severidade e o risco principal>

## Achados
### [ALTA] <título curto>
- **Onde:** `caminho/arquivo.py:123`
- **O que acontece:** <descrição concreta, com o dado pessoal envolvido>
- **Fundamento:** LGPD art. X (+ ADR-NNNN, se houver)
- **Correção sugerida:** <ação objetiva>

## A confirmar
- <itens que dependem de ambiente/processo>

## Pontos positivos
- <controles bem implementados, em 1 linha cada>
```

Ordene os achados por severidade. Mostre o relatório no chat; grave em arquivo só se o usuário pedir.
