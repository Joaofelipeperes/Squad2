# ADR 0001 — Monólito modular com FastAPI e React

**Status:** proposta · **Data:** 30/09/2026

## Contexto
Quatro residentes em dedicação parcial, dois eixos em paralelo, entrega em 02/12/2026,
infraestrutura do Estado sem contêineres e sem orçamento. A GEDA já usa Python, e o CKAN é Python.

## Decisão
Um backend Python 3.11 (FastAPI + SQLAlchemy 2 síncrono + Alembic) e um frontend React/TS,
cada um dividido em módulos com contrato fixo e registro central.

## Alternativas consideradas
- **Django + DRF**: admin e auth prontos, mas mais convenções a aprender e acoplamento maior
  entre camadas. Seria a segunda opção.
- **Microsserviços por eixo**: isolamento máximo, porém custo de deploy, observabilidade e
  integração incompatível com prazo e infraestrutura.
- **SQLAlchemy assíncrono**: ganho irrelevante para ~450 datasets e poucos usuários; adiciona
  complexidade de depuração. FastAPI executa rotas síncronas em thread pool.

## Consequências
Um único deploy e um único banco; a documentação OpenAPI gerada (/api/v1/docs) serve de
contrato entre frontend e backend. Se um módulo crescer demais, ele já tem fronteira clara para
ser extraído.
