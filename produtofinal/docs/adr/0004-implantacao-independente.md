# ADR 0004 — Aplicação independente do CKAN, com regras de domínio portáveis

**Status:** proposta · **Data:** 30/09/2026

## Contexto
A CGE-GO ainda decide entre publicar a solução como extensão do CKAN (que a tornaria disponível
a toda a organização mantenedora) ou acessá-la pelo site do portal (Reunião 3, 17/09). A SECTI
não permite alterar o CKAN de produção sem esse aval.

## Decisão
Construir uma aplicação web independente, que pode ser acessada por link ou embutida no portal.
As regras de cálculo ficam em funções puras (`regras.py`), sem dependência de FastAPI ou banco,
para que possam ser reaproveitadas por uma extensão `ckanext-*` se essa for a decisão.

## Consequências
O desenvolvimento não espera a decisão. Se a opção for extensão, será preciso confirmar com a
SECTI a versão do Python das VMs do CKAN 2.9.5 e ajustar a compatibilidade das `regras.py`.
