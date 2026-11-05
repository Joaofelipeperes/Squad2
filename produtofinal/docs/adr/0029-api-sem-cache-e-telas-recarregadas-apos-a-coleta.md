# ADR-0029 — API sem cache no navegador e telas recarregadas ao fim da coleta

| | |
|---|---|
| **Status** | Proposta |
| **Tipo** | Técnica |
| **Data da decisão** | 05/11/2026 (proposta; aguarda o aceite da coordenação) |
| **Data do registro** | 05/11/2026 |
| **Decisores** | Victor Hugo Benatti (coordenação) — a confirmar |
| **Consultados** | — (repassar ao João, responsável pela base comum e pela rastreabilidade) |
| **Origem** | Sessão de 05/11: depois de "Atualizar dados", a tela Rastreabilidade só mostrava os dados novos limpando o cache do navegador (card ClickUp 86e3xcapz) |
| **Afeta** | `backend/app/main.py` (middleware), `frontend/src/shared/api/client.ts`, `frontend/src/app/layout/Topbar.tsx`, tela Rastreabilidade, `frontend/nginx.conf` |

## Contexto
O botão "Atualizar dados" inicia a coleta em segundo plano. Ao fim dela, só a data da última coleta
na topbar era recarregada: as telas já carregadas continuavam com a cópia em memória do React Query
(`staleTime` de 30 s, sem recarga ao voltar à janela). Na Rastreabilidade há um passo a mais: a
leitura da auditoria do CKAN (sincronização) começa **depois** que a coleta termina, então mesmo uma
recarga logo após a coleta ainda trazia a linha do tempo antiga. Além disso, as respostas da API não
diziam ao navegador nem a proxies que não podiam ser guardadas, e o `index.html` não pedia
revalidação — depois de um deploy o navegador podia seguir com o JavaScript anterior. O efeito
percebido: só limpando o cache os dados novos apareciam.

## Critérios de decisão
1. Dado recuperado aparece sem ação manual do usuário (nem F5, nem limpar cache).
2. Sem custo relevante de requisições extras.
3. Vale para todas as telas, não só para a Rastreabilidade.

## Opções consideradas

### Opção A — Desligar o cache do React Query (`staleTime: 0`, recarregar ao focar a janela)
- **Prós:** uma linha de configuração.
- **Contras:** requisições a cada troca de tela e de foco; não resolve a sincronização da
  rastreabilidade, que termina depois; não impede cache HTTP de navegador/proxy.

### Opção B — Cabeçalho `no-store` na API + recarregar as telas quando a coleta termina + acompanhar a sincronização na Rastreabilidade
- **Prós:** recarga só quando os dados mudaram; resolve também a sincronização posterior; nenhum
  cache HTTP entre a tela e o banco; mantém o cache em memória que evita requisições repetidas.
- **Contras:** três pontos de mudança (backend, cliente HTTP, topbar/tela).

### Opção C — Botão "Recarregar" em cada tela
- **Prós:** simples de entender.
- **Contras:** continua dependendo de ação manual; não resolve o cache HTTP.

## Decisão
**Opção B.**
- Backend: middleware `sem_cache_na_api` em `main.py` põe `Cache-Control: no-store, max-age=0` e
  `Pragma: no-cache` em toda resposta sob `/api/v1` (sem sobrescrever quem já definiu o cabeçalho).
- Cliente HTTP: `fetch(..., { cache: "no-store" })` em todas as chamadas.
- Topbar: quando a última coleta sai de "executando", invalida todas as consultas (menos a da própria
  coleta) — as telas abertas recarregam do banco.
- Rastreabilidade: enquanto a sincronização da última coleta não termina (ou ainda não começou, até
  15 min depois do fim da coleta), a tela consulta de novo a cada 5 s.
- nginx: `index.html` com `Cache-Control: no-cache` (os JS/CSS têm hash no nome e continuam em cache).

## Consequências
- **Positivas:** os dados recuperados aparecem sozinhos ao fim da coleta e da sincronização; nenhum
  proxy guarda resposta da API (que tem dados por órgão e por usuário); deploy novo chega ao
  navegador sem limpar cache.
- **Negativas e riscos:** consultas a cada 5 s na Rastreabilidade só durante a sincronização; se a
  sincronização demorar mais de 15 min para começar, a tela para de consultar sozinha (a recarga da
  página resolve).

## Validação
Coordenação (Victor) aceita ou ajusta esta proposta; conferir no Docker (nginx) depois do deploy.

## Revisões
Melhorias e fatos novos que **não** mudam a decisão entram aqui. Se a decisão mudar, crie uma nova
ADR e marque esta como "Substituída por ADR-XXXX".

| Data | Revisão | Autor |
|---|---|---|
