# ADR 0002 — Camada de IA plugável com política de dados sensíveis

**Status:** proposta · **Data:** 30/09/2026

## Contexto
O PGP prevê o Gemini via chave da SECTI (limite de decisão 19/10), mas a chave pode não sair.
A varredura LGPD processa dados pessoais reais; enviá-los a um serviço comercial é uma decisão
institucional, não técnica. O time precisa trocar de modelo sem reescrever código.

## Decisão
- Contrato `AIProvider` único e adaptadores por fornecedor, registrados por decorador.
- Configuração em banco por **perfil** (provedor + modelo + credencial cifrada + flag local),
  editável na página Administração › Modelos de IA.
- Cada **tarefa** de IA tem perfil principal e de contingência.
- Módulos de negócio só acessam IA pelo `AIGateway`, que aplica a política: tarefa marcada como
  sensível só aceita perfil local, verificado ao vincular, ao editar o perfil e a cada chamada.
- Registro de uso sem conteúdo (PBI-35).

## Consequências
Trocar o modelo do Assistente de Gemini para um modelo local é uma ação na tela. A varredura
LGPD não depende de IA (regras determinísticas primeiro), então a falta da chave não bloqueia o
Eixo 2. Rodar modelo local em produção exige servidor adequado — pendência com a SECTI.
