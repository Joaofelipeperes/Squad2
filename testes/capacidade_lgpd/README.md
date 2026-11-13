# Teste de capacidade da varredura LGPD

Mede quanto a varredura de dados pessoais (Eixo 2) custa com o volume real do portal. Responde
às perguntas usadas para dimensionar o servidor da SECTI/CGE-GO:

| # | Pergunta | Como o teste responde |
|---|---|---|
| 1 | Quanto tempo leva por recurso (por MB, por linha)? Quantas chamadas à IA local? | Varre uma **amostra** (padrão: 30 recursos, ~40% pequenos < 1 MB, ~35% médios 1–10 MB, ~25% grandes ≥ 10 MB, sempre incluindo o maior abaixo do limite) e lê de cada varredura: duração, espera na fila, linhas, chamadas à IA e achados |
| 2 | O portal inteiro leva horas ou dias? | Conta os recursos varríveis do inventário (CSV/TSV/TXT/XLSX) e projeta o total pela média de cada faixa de tamanho (com a mediana e o p90 como intervalo), na proporção medida num sorteio de candidatos. Mostra também a conta descontando os recursos que a varredura ignora ou não consegue ler |
| 3 | A varredura noturna termina antes do expediente? | Conta os recursos alterados (`last_modified`) no último dia, em 7 e em 30 dias, e compara o tempo estimado com a janela (padrão 3 h: varredura às 05:00, expediente às 08:00) e com o teto de 200 recursos por execução |
| 4 | Pico de memória com arquivo grande? Algum processo cai? | `docker stats` a cada 3 s durante todo o teste (api, worker, db, ollama) e `docker inspect` antes e depois (reinícios e morte por falta de memória). Destaca o maior arquivo varrido e o que tem mais linhas |
| 5 | As telas continuam rápidas com a CPU ocupada pela IA? | Usuários simulados (padrão: 7) abrindo as telas mais usadas, primeiro **sem** varredura (linha de base) e depois **durante** a amostra; compara p50/p95/máximo e erros por tela |
| 6 | A fila se recupera sem travar nem repetir trabalho? | Enfileira um lote (padrão: 20), **reinicia o worker** com uma varredura em execução, cancela o restante e confere: a interrompida virou erro e voltou à fila uma vez; nada ficou preso; nenhum recurso foi varrido duas vezes; um pedido novo depois disso é executado |

O resultado sai em `resultados/<data_hora>/`, nesta pasta (fora do git):
- `resultado.md`: as seis respostas, com tabelas;
- `amostra.csv`: uma linha por recurso varrido;
- `bruto.json`: todas as medições.

O teste fica na raiz do repositório, fora de `produtofinal/`, de propósito: é ferramenta do time,
não parte do sistema, e assim não entra no pacote de entrega. Ele conversa com o sistema só pela
API e pelo Docker.

## Antes de rodar

1. **IA local de verdade.** Os tempos só servem para dimensionar o servidor com o modelo local
   ligado (com a IA simulada, medem só download e regras). O script recusa rodar com a IA simulada,
   a não ser com `--aceitar-ia-simulada`, que serve para ensaiar.
   ```bash
   # em produtofinal/
   docker compose --profile ia-local up -d
   docker compose exec ollama ollama pull qwen2.5:7b-instruct
   docker compose exec ollama ollama pull bge-m3
   docker compose exec api python -m app.cli configurar-ia-local
   ```
   Se a tarefa "Classificação de dados pessoais" já estiver ligada ao perfil "Simulado (dev)", troque
   para o perfil "Ollama local" na tela **Modelos de IA**. O `configurar-ia-local` não sobrescreve uma
   escolha que já existe.
2. **Máquina.** Rode no computador mais parecido possível com o servidor, ou anote a configuração
   (o relatório registra CPUs e RAM do Docker). A IA em CPU deve ser o gargalo.
3. **CKAN.** A varredura baixa os arquivos do portal configurado em **Perfis do CKAN**. Para medir
   o tempo real, use o portal oficial: os downloads são espaçados de propósito e o portal pode
   responder 429 (ADR-0025), e isso entra no tempo.
4. **Fila vazia.** O script não começa se houver varredura pendente ou em execução.
5. **Tempo.** Com a IA local em CPU, cada chamada ao modelo leva segundos e um arquivo com milhares
   de textos diferentes leva horas sozinho. Como o worker varre um recurso por vez, um arquivo lento
   segura todos os que vêm depois. Por isso:
   - a amostra é pedida **do menor para o maior** arquivo;
   - `--teto-recurso-min N` interrompe (reiniciando o worker) a varredura que passar de N minutos,
     e a fila segue. O tempo desse recurso entra no relatório como piso ("≥ N min"). Com o teto, o
     maior arquivo vai primeiro, para a medição de memória da pergunta 4 ficar garantida;
   - a espera pela amostra desiste depois de `--tempo-maximo-h` (padrão 8 h) e cancela o que sobrou.

   Antes da amostra há uns 5 min de preparo e, depois, o teste da fila (até ~1 h). Com a IA local,
   use o teto (por exemplo `--teto-recurso-min 30`).
6. **Login.** O login vale 8 h contadas do início do teste (`GDA_JWT_EXPIRE_MINUTES=480`), menos que
   o teste inteiro pode durar. Gere um token só para o teste, válido por 12 h, e passe com `--token`
   (a API confere só a assinatura e a validade do token; nada muda na configuração):
   ```bash
   # em produtofinal/
   docker compose exec -T -e GDA_JWT_EXPIRE_MINUTES=720 api python -c "from sqlalchemy import select; from app.core.db import SessionLocal; from app.core.security import create_access_token; from app.modules.acesso.models import Usuario; print(create_access_token(SessionLocal().execute(select(Usuario).where(Usuario.email == 'voce@cge.go.gov.br')).scalar_one().id))"
   ```

## Como rodar

Na raiz do repositório, com um Python 3.11 ou mais novo que tenha o `httpx` (o ambiente do backend
serve; em outro Python, `pip install httpx`):

```bash
python testes/capacidade_lgpd/teste_capacidade_lgpd.py --email voce@cge.go.gov.br
```

O script acha sozinho a pasta `produtofinal/` e roda nela os comandos `docker compose`. A API
precisa estar em `http://localhost:8000` (ou informe `--api`).

A senha é perguntada, ou lida de `GDA_TESTE_SENHA`. O usuário precisa de `lgpd.varrer`,
`ia.configurar` e `parametros.acessar` (por exemplo, administrador). Também aceita `--token`, ou
`GDA_TESTE_TOKEN`, no lugar de e-mail e senha.

Opções úteis:

| Opção | Padrão | Para quê |
|---|---|---|
| `--api` | `http://localhost:8000/api/v1` | endereço da API do sistema |
| `--amostra` | 30 | recursos medidos |
| `--candidatos` | 90 | recursos sorteados para medir o tamanho e escolher a amostra |
| `--usuarios` | 7 | usuários simulados nas telas (0 pula a pergunta 5) |
| `--fila` | 20 | pedidos no teste da fila (0 pula a pergunta 6) |
| `--tempo-maximo-h` | 8 | tempo máximo de espera pela amostra |
| `--teto-recurso-min` | 0 (sem teto) | interrompe a varredura da amostra que passar disso, para a fila seguir |
| `--janela-h` | 3 | horas entre a varredura noturna e o expediente |
| `--limite-p95-s` | 2 | tempo de resposta aceitável das telas (p95) |
| `--semente` | — | repetir o mesmo sorteio |
| `--aceitar-ia-simulada` | — | ensaiar o teste sem o modelo local |

## Efeitos no ambiente

- **Cria varreduras de verdade** para os recursos da amostra e do teste da fila. Os achados vão
  para a tela Dados Pessoais, como numa varredura normal: só local e tipo, nunca o valor.
- **Reinicia o container do worker**: uma vez no teste da fila (pergunta 6), uma vez para cada
  recurso que passar do teto (`--teto-recurso-min`) e, se preciso, para esvaziar a fila entre as
  fases. Cancela o que estiver pendente. A varredura interrompida fica no histórico como erro de
  interrupção; o sistema recoloca o recurso na fila só na primeira vez que isso acontece com ele.
- **Lê o tamanho dos arquivos no portal** só pelo cabeçalho da resposta, sem baixar o conteúdo,
  com pausa de 1 s entre os pedidos.
- Não altera bases do PDA, usuários nem parâmetros.

Os dados lidos são públicos (portal de dados abertos). O teste não guarda nenhum valor de dado pessoal.
