---
name: front-sem-cara-de-ia
description: Revisa e melhora a estética do front-end para tirar a "cara de app feito com IA" — gradientes roxo-azul, cards idênticos em grade, emojis como ícone, sombras e cantos arredondados em tudo, textos genéricos de marketing, tudo centralizado. Use quando o usuário pedir para deixar o front mais bonito, mais profissional, menos genérico, menos "template", com identidade própria, "sem cara de IA", ou para polir/refinar uma tela, componente ou o visual do app como um todo.
---

# Front-end sem cara de IA

Você deixa a interface com cara de produto desenhado por alguém, não de saída padrão de gerador.
O objetivo **não** é "mais enfeite": é tirar os vícios de template e substituir por decisões
deliberadas — hierarquia, ritmo, densidade e detalhes coerentes com o que o app faz.

Contexto deste projeto: painel institucional da CGE-GO (monitoramento de dados abertos), usado por
servidores públicos no dia a dia. A estética certa aqui é **ferramenta de trabalho sóbria e densa**
(pense em painel de gestão, planilha bem feita, sistema bancário interno), não landing page de startup.

## Regras invioláveis

- **Não edite `produtofinal/frontend/src/design-system/prototipo-v1.css`.** É o protótipo aprovado
  com a CGE-GO. Ajustes vão em `overrides.css` (ou CSS do módulo). Se a melhoria exigir mudar um
  token do protótipo, proponha ao usuário antes — é decisão de produto, não sua.
- Use os tokens existentes (`--navy-*`, `--blue-*`, `--gray-*`, `--ink`, `--radius-*`, `--shadow-*`).
  Não invente cor hex solta; se faltar um tom, crie um token novo em `overrides.css` e diga por quê.
- Não adicione biblioteca de UI (Tailwind, shadcn, MUI, Framer Motion etc.) sem o usuário pedir.
  O stack é React + Vite + CSS puro + Font Awesome + Chart.js.
- Não piore acessibilidade: contraste AA, foco visível, alvo de clique ≥ 24px, nada que dependa só de cor.
- Mudança visual não muda comportamento. Não mexa em lógica, chamadas de API ou textos de regra de negócio.

## Fluxo

1. **Escopo.** Tela/componente indicado pelo usuário; senão, as telas tocadas no diff da branch
   (`git diff --merge-base origin/desenvolvimento -- produtofinal/frontend`, ou `origin/main` se
   `desenvolvimento` não existir). "O app todo" → comece pelo shell
   (sidebar, topbar), Visão Geral e a tela mais usada, nessa ordem.
2. **Olhe antes de mexer.** Se der, rode o app (skill `run` ou `npm run dev` em `produtofinal/frontend`)
   e tire screenshot no navegador embutido. Leia o TSX e o CSS que estilizam a tela.
3. **Diagnóstico.** Liste os vícios encontrados usando o checklist abaixo, com `arquivo:linha`.
   Classifique: **forte** (grita "IA/template"), **médio**, **detalhe**.
4. **Proponha antes de aplicar** quando a mudança for grande (layout de tela, token, nova fonte).
   Ajustes pequenos e claramente melhores pode aplicar direto.
5. **Aplique** em `overrides.css` / CSS do módulo / TSX, mantendo o estilo do código existente.
6. **Verifique** com screenshot depois (desktop e ~375px), em claro, e confira `npm run typecheck`.
7. **Relate** o antes/depois por item, o que ficou de fora e por quê.

## Checklist: sinais de "feito com IA"

### Cor
- Gradiente roxo→azul / azul→ciano / "aurora" em fundo, botão, título ou card. → Cor chapada do token.
  Gradiente só se já existe no protótipo (a sidebar navy é intencional, mantenha).
- Texto com gradiente (`background-clip: text`). → Remova.
- Paleta "arco-íris": cada card/KPI com uma cor diferente sem significado. → Neutro por padrão;
  cor só carrega significado (status: verde ok, âmbar atenção, vermelho erro; azul = ação/link).
- Fundo cinza-claro + cards brancos com sombra em todo bloco. → Agrupe por borda fina ou espaço;
  sombra só no que flutua (modal, dropdown, popover).
- Glassmorphism / `backdrop-filter: blur` sem motivo. → Remova.

### Forma e profundidade
- `border-radius` grande (12–24px) em tudo, pills em todo botão. → Use `--radius-sm`/`--radius-md`;
  raio consistente por tipo de elemento, menor quanto menor o elemento.
- Sombras grandes e difusas em cards estáticos. → `--shadow-1` ou borda `--gray-200`.
- Hover que levanta card (`translateY(-4px)` + sombra maior) em coisa que não é clicável. → Remova;
  em item clicável, mude fundo/borda sutilmente.
- Bordas coloridas à esquerda (`border-left: 4px solid`) em todo card/alerta. → Use só onde marca
  estado, e não em cascata.

### Layout
- Grade de 3 ou 4 cards idênticos (ícone em círculo + título + 2 linhas). → Varie peso: um item
  principal maior, os demais em lista ou tabela; KPI sem ícone decorativo.
- Tudo centralizado, inclusive textos longos e formulários. → Alinhamento à esquerda; centralize só
  estados vazios curtos.
- Espaçamento uniforme e frouxo (mesmo `gap: 24px` em tudo). → Ritmo: menos espaço dentro do grupo,
  mais entre grupos. Ferramenta de trabalho pede densidade (tabelas compactas, linhas de 36–40px).
- Hero/banner de boas-vindas ocupando a dobra ("Bem-vindo ao seu painel! 👋"). → Vá direto ao dado.
- Larguras todas iguais / `max-width` arbitrário. → Colunas por conteúdo (números alinhados à direita,
  `font-variant-numeric: tabular-nums`, datas e códigos em mono).

### Tipografia
- Só Inter em pesos 400/600 com títulos enormes. → Escala contida (página 20–22px, seção 15–16px,
  corpo 13–14px); contraste de hierarquia por peso, cor e caixa — não só tamanho.
- Rótulos todos em MAIÚSCULAS com tracking em todo lugar. → Reserve para cabeçalhos de tabela e
  rótulos pequenos de seção.
- Números de KPI gigantes sem unidade, sem comparação, sem data. → Número + unidade + contexto
  ("de 412 bases", "atualizado 09/11 14:02").
- Aproveite o IBM Plex Mono que já está instalado para IDs, slugs, hashes, contagens em tabela.

### Ícones e imagem
- Emoji como ícone (🚀 ✨ 📊 🔒) em título, botão ou menu. → Font Awesome do projeto, ou nada.
- Ícone dentro de círculo/quadrado colorido em todo card. → Ícone solto, cor do texto, ou remova.
- Ícone em todo botão e todo título. → Só onde ajuda a escanear (menu, ações de linha).
- Ilustração genérica / blob decorativo. → Remova.

### Texto (microcopy)
- Marketing vazio: "Desbloqueie o poder dos seus dados", "Experiência perfeita", "Tudo em um só lugar".
  → Texto que diz o que acontece: "12 bases sem atualização há mais de 30 dias".
- "Oops! Algo deu errado 😢". → Diga o que falhou e o que fazer: "Não foi possível carregar as bases.
  Tente de novo; se persistir, avise o suporte (erro 502)."
- Botões genéricos ("Enviar", "OK", "Clique aqui"). → Verbo + objeto: "Incluir base", "Salvar perfil".
- Pontos de exclamação, entusiasmo, emojis em texto institucional. → Tom neutro de órgão público.
- Para revisão profunda de textos, use a skill `design:ux-copy`.

### Movimento
- Animação de entrada em tudo (fade-up em cascata, contador subindo de 0). → Remova; dado aparece pronto.
- Transições longas (> 200ms) em hover. → 100–150ms, só em cor/fundo/borda.
- Respeite `prefers-reduced-motion`.

### Estados (onde IA costuma esquecer)
- Sem estado vazio, carregando e erro específicos. → Cada tabela/lista tem os três, com texto útil.
- Skeleton genérico piscando. → Preferir skeleton no formato do conteúdo, ou texto "Carregando…".
- Focos, desabilitados e linhas selecionadas sem estilo. → Defina todos.

## O que dá identidade (em vez de enfeite)

Prefira poucas decisões fortes e repetidas com consistência:

- **Densidade de ferramenta**: tabelas bem desenhadas valem mais que cards. Cabeçalho fixo,
  zebra sutil ou divisória fina, ações na linha alinhadas à direita.
- **Um acento só**: o navy institucional + azul de ação. Todo o resto é cinza e status.
- **Detalhes de dado**: números tabulares, unidades, datas relativas com a absoluta no `title`,
  códigos em mono, truncamento com reticências e texto completo no hover.
- **Assimetria intencional**: Visão Geral com um bloco principal e blocos de apoio, não grade
  simétrica de cards iguais.
- **Bordas finas e alinhamento rigoroso**: tudo numa grade de 4px; bordas `--gray-200` de 1px.

## Formato do relatório

```
## Diagnóstico — <tela/componente>

### Forte
- <arquivo:linha> — <vício> → <o que fazer>
### Médio
- ...
### Detalhe
- ...

## Aplicado
- <arquivo> — <mudança>

## Pendente / precisa de decisão
- <item> — <por que não apliquei>
```

Termine com screenshot antes/depois quando conseguiu rodar o app; se não rodou, diga que não verificou visualmente.
