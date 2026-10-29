# ADR-0024 — O CKAN lido é escolhido pelo ambiente: portal oficial em produção, CKAN local fora dela

| | |
|---|---|
| **Status** | Aceita |
| **Tipo** | Técnica |
| **Data da decisão** | 28/10/2026 |
| **Data do registro** | 28/10/2026 |
| **Decisores** | Victor Hugo Benatti (coordenação) |
| **Consultados** | — |
| **Origem** | Sessão de trabalho de 28/10/2026 (dataset criado no CKAN local não aparecia após "Atualizar dados") |
| **Afeta** | `core/config.py` (`ckan_base_url`, `GDA_ENVIRONMENT`); `docker-compose.ckan-local.yml`; `.env.example`; `/api/v1/saude`; coleta (`inventario`), rastreabilidade e varredura LGPD, que leem pelo `CkanClient`; escrita (US26), cujo endereço padrão é o mesmo da leitura |

## Contexto
`GDA_CKAN_BASE_URL` tinha como padrão fixo o portal oficial, e só o `docker-compose.ckan-local.yml`
trocava para o CKAN local. Subir a solução sem esse arquivo (ou com um `.env` que repetisse o valor
do `.env.example`) fazia o ambiente de homologação ler o portal de produção em silêncio: um dataset
criado no CKAN local não aparecia na coleta, sem nenhum erro. O ambiente já é declarado em
`GDA_ENVIRONMENT` (`dev | homologacao | producao`), mas não influía no CKAN.

## Critérios de decisão
1. Ambiente de testes nunca ler (nem escrever, US26) no portal oficial por engano.
2. Produção ler o portal oficial sem configuração extra.
3. Continuar possível apontar para outro CKAN (API fora do Docker, outro servidor de testes).
4. Simplicidade: nenhuma infraestrutura nova.

## Opções consideradas

### Opção A — Padrão do CKAN derivado de `GDA_ENVIRONMENT`, com `GDA_CKAN_BASE_URL` opcional
- **Prós:** um único parâmetro (o ambiente) decide; produção e homologação ficam corretas sem
  lembrar de outra variável; `GDA_CKAN_BASE_URL` continua valendo para casos especiais; o padrão
  da escrita (US26) acompanha a leitura, então homologação não publica no portal.
- **Contras:** o endereço do CKAN local (`ckansquad2-ckan-1`) fica no código; só resolve dentro da
  rede do CKAN (ainda é preciso o `docker-compose.ckan-local.yml`). Rodando a API fora do Docker é
  preciso informar `http://localhost:5000`.

### Opção B — Manter `GDA_CKAN_BASE_URL` fixo e independente do ambiente
- **Prós:** nenhuma mudança.
- **Contras:** foi o que causou o problema: o valor padrão é produção e nada avisa quando o
  ambiente de testes lê o portal oficial.

### Opção C — `GDA_CKAN_BASE_URL` obrigatório (sem padrão)
- **Prós:** explícito; nunca lê o CKAN errado por omissão.
- **Contras:** mais um item obrigatório em todo `.env`; não resolve um `.env` copiado com o valor
  de outro ambiente.

## Decisão
**Opção A.** Sem `GDA_CKAN_BASE_URL`: `producao` → `https://dadosabertos.go.gov.br`;
`homologacao` e `dev` → `http://ckansquad2-ckan-1:5000` (container do CKAN da raiz, `container_name`
fixo). Valor informado prevalece. `GDA_ENVIRONMENT` fora de `dev | homologacao | producao` passa a
impedir a subida (antes um erro de digitação como "production" só era barrado se as chaves fossem
fracas). O `docker-compose.ckan-local.yml` deixa de definir o CKAN e só liga a rede;
`/api/v1/saude` mostra o CKAN em uso.

## Consequências
- **Positivas:** homologação lê o CKAN local sem configuração extra; produção lê o portal oficial;
  dá para conferir qual CKAN está em uso pelo endpoint de saúde.
- **Negativas e riscos:** `.env` antigos com `GDA_CKAN_BASE_URL=https://dadosabertos.go.gov.br`
  continuam lendo o portal oficial — esvaziar a variável. Homologação sem o
  `docker-compose.ckan-local.yml` falha ao coletar (nome do container não resolve) em vez de ler
  produção: erro visível, que é o comportamento desejado.

## Validação
Time do produto (João, coleta; Luiza, LGPD) ao subir o ambiente local.

## Revisões
| Data | Revisão | Autor |
|---|---|---|
