# Decisões do projeto — linha do tempo

Registro de **todas** as decisões que moldaram a solução, em ordem cronológica. Cada decisão técnica
tem uma ADR (Architecture Decision Record) com contexto, alternativas, prós e contras, escolha,
consequências e revisões. Decisões de gestão já registradas em outros documentos aparecem aqui com
a fonte.

- **Como registrar:** copie [`_MODELO.md`](_MODELO.md) para `NNNN-titulo-curto.md` (próximo número
  livre), preencha e acrescente uma linha nesta página **no mesmo commit** da mudança.
- **Numeração** segue a ordem de registro; a **ordem cronológica** está na tabela abaixo.
- **Decisão aceita não é reescrita.** Fato novo ou melhoria → linha em "Revisões". Mudou a decisão →
  ADR nova e a antiga passa a "Substituída por ADR-XXXX".
- **Registro retroativo:** decisões anteriores a 01/10/2026 foram registradas em 07/10/2026 a partir
  das atas; a data da decisão é a original.

**Status:** Aceita · Proposta · Em análise · Substituída · Descartada.

## Linha do tempo

| Data | Decisão | Tipo | Status | Registro |
|---|---|---|---|---|
| 20/08/2026 | Priorizar o Eixo 1 (monitoramento temporal) antes do Eixo 2 (LGPD) | Escopo | Substituída por D3 (22/09) | Reunião 1 e orientador; citada na Reunião 3 |
| 20/08/2026 | Aferir atualização pelo recurso e vincular pelo ID do dataset (refinada em 27/08 e 17/09) | Negócio | Aceita | [ADR-0006](0006-regras-de-afericao-do-inventario.md) |
| 31/08/2026 | Orientação da SECTI: priorizar modelo comercial (Gemini) com chave específica para a aplicação | Técnica (externa) | Aceita como insumo; ver ADR-0002 e ADR-0010 | Documento "CKAN — Dúvidas" (31/08) |
| 17/09/2026 | Reuniões com a CGE-GO a cada 15 dias, ou antes sob demanda | Processo | Aceita | Reunião 3 |
| 22/09/2026 | D1 — Calendário oficial no ClickUp, entregas amarradas aos checkpoints com o orientador | Processo | Aceita | Backlog v2, aba Alterações v1→v2 |
| 22/09/2026 | D2 — Anonimização no escopo, com publicação no CKAN após aprovação | Escopo | Aceita | [ADR-0008](0008-anonimizacao-com-publicacao-no-ckan.md) |
| 22/09/2026 | D3 — Eixos 1 e 2 em paralelo; João assume a base comum; Victor coordena | Processo | Aceita | Backlog v2, aba Alterações v1→v2 |
| 22/09/2026 | D4 — Metadados obrigatórios (US16), login (US24) e Assistente (US28) viram compromisso | Escopo | Aceita | Backlog v2, aba Alterações v1→v2 |
| 22/09/2026 | D5 — Protótipo V1 é a referência das telas | Escopo | Aceita | [ADR-0007](0007-prototipo-v1-referencia-das-telas.md) |
| 22/09/2026 | Abrir a definição da fonte da rastreabilidade (US29) após incompatibilidade da extensão de auditoria | Técnica | Em análise | [ADR-0009](0009-fonte-da-rastreabilidade.md) |
| 30/09/2026 | Monólito modular com FastAPI e React | Técnica | Aceita | [ADR-0001](0001-monolito-modular.md) |
| 30/09/2026 | Gateway de IA com provedores plugáveis e política de dados sensíveis | Técnica | Aceita | [ADR-0002](0002-camada-ia-plugavel.md) |
| 30/09/2026 | Frontend em React reaproveitando o CSS do protótipo | Técnica | Aceita | [ADR-0003](0003-frontend-modular.md) |
| 30/09/2026 | Desenvolver como aplicação independente do CKAN, com regras portáveis | Técnica | Aceita para desenvolvimento; entrega final em aberto | [ADR-0004](0004-implantacao-independente.md) |
| 30/09/2026 | Controle de acesso por papéis e permissões, com escopo por órgão | Técnica | Aceita | [ADR-0005](0005-controle-de-acesso.md) |
| 30/09/2026 | Detecção de dados pessoais híbrida: regras + modelo local | Técnica | Aceita (modelo em avaliação) | [ADR-0010](0010-deteccao-de-dados-pessoais-hibrida.md) |
| 30/09/2026 | Assistente com contexto montado pelo backend, sem banco vetorial | Técnica | Aceita | [ADR-0011](0011-assistente-sem-banco-vetorial.md) |
| 30/09/2026 | Coleta diária em processo agendador próprio | Técnica | Aceita | [ADR-0012](0012-agendamento-em-worker-proprio.md) |
| 30/09/2026 | PostgreSQL/SQLite e convenção de nomes de constraints | Técnica | Aceita | [ADR-0013](0013-banco-de-dados-e-convencoes.md) |
| 30/09/2026 | Documentação viva por módulo com verificação automática | Processo | Aceita | [ADR-0014](0014-documentacao-viva-por-modulo.md) |
| 30/09/2026 | Envio de recursos por órgãos só como esqueleto não comprometido | Escopo | Proposta | [docs/modulos/envio.md](../modulos/envio.md) |
| 01/10/2026 | Reforço da detecção híbrida e do modelo offline (LIGO e orientador) | Técnica | Revisão da ADR-0010 | [ADR-0010](0010-deteccao-de-dados-pessoais-hibrida.md) |
| 01/10/2026 | Registrar toda decisão técnica como ADR numa linha do tempo | Processo | Aceita | [ADR-0015](0015-registro-de-decisoes.md) |
| 07/10/2026 | Convenções de modelagem formalizadas e MER gerado do código | Técnica | Revisão da ADR-0013 | [ADR-0013](0013-banco-de-dados-e-convencoes.md) |

## Decisões em aberto

| Tema | Opções | Quem decide | Onde |
|---|---|---|---|
| Forma de entrega final | Extensão do CKAN × aplicação acessada pelo portal | Paloma / Júnior, com a SECTI | ADR-0004, PBI-102 |
| Fonte da rastreabilidade | Extensão de auditoria × activity stream × diff entre coletas | João, com a SECTI | ADR-0009, PBI-70 (prazo previsto 28/09) |
| Modelo local para classificar dados pessoais | Qwen ajustado do LIGO × modelos testados pela Luiza × classificador especializado | Luiza | ADR-0010 |
| Chave de modelo comercial para o Assistente | Gemini via SECTI/LIGO × modelo local | SECTI/LIGO via Paloma (limite 19/10) | ADR-0002 |
| Hospedagem do protótipo navegável | Oracle Cloud (camada gratuita, conta do coordenador) × OpenShift da TI Central | Victor, com a Paloma | Sugestão do orientador (01/10) |
| Distribuição dos papéis padrão | Matriz atual × ajustes da GEDA | Paloma | ADR-0005 |
| Envio de recursos pelos órgãos | Incluir no escopo × manter fora | Paloma / Júnior, com a SECTI | docs/modulos/envio.md |

## Pendências de validação com a CGE-GO

O orientador pediu (01/10) que as decisões tomadas pelo time sem a participação da Paloma sejam
repassadas a ela, com as alternativas e o porquê. Candidatas: ADR-0001, 0002, 0004, 0005, 0010 e 0011.
