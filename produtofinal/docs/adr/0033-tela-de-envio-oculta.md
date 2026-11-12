# ADR-0033 — Ocultar a tela "Envio de dados do órgão" e manter o módulo `envio` só como esqueleto

| | |
|---|---|
| **Status** | Aceita |
| **Tipo** | Escopo |
| **Data da decisão** | 09/11/2026 |
| **Data do registro** | 09/11/2026 |
| **Decisores** | Victor Hugo Benatti (coordenação) |
| **Consultados** | — (o envio não foi pedido pela CGE-GO; ver "Decisões em aberto" no README) |
| **Origem** | Sessão de trabalho de 09/11/2026, preparação da entrega em produção (ADR-0032) |
| **Afeta** | módulo `envio` (tela `frontend/src/modules/envio/`), `frontend/src/modules/registry.ts`, papel padrão Órgão publicador (ADR-0005) |

## Contexto
O módulo `envio` nasceu em 30/09/2026 como esqueleto **não comprometido** para materializar o papel
Órgão publicador e o escopo de órgão no controle de acesso. A tela "Envio de dados do órgão" só mostra
o órgão do usuário e um aviso de funcionalidade em definição; o backend não tem nenhuma rota.
O PGP v2 deixa fora do escopo os pipelines de ingestão dos órgãos, e a CGE-GO não pediu a
funcionalidade. Com a entrega em produção (ADR-0032), uma tela sem função no menu passaria a ideia
de algo prometido.

## Critérios de decisão
1. Não entregar em produção tela que a CGE-GO não pediu (PGP v2, AGENTS.md §5).
2. Guardar o que já existe para uma implementação futura, sem retrabalho.
3. Mudança pequena e fácil de desfazer.

## Opções consideradas

### Opção A — Ocultar a tela no registro do frontend e manter os arquivos
- **Prós:** uma linha no `registry.ts`; os arquivos, as permissões `envio.*`, o papel Órgão publicador
  e o módulo do backend (sem rotas) continuam prontos para reativar; nenhuma migração.
- **Contras:** código parado no repositório; um usuário que só tenha o papel Órgão publicador passa a
  ver a página "Sem acesso".

### Opção B — Remover o módulo inteiro (tela, backend, permissões e papel)
- **Prós:** repositório sem código parado; o papel Órgão publicador sai da tela de Usuários.
- **Contras:** perde o esqueleto e o escopo de órgão já desenhados; mexe no catálogo de permissões,
  nos papéis padrão e nos testes de acesso; reativar exige refazer.

### Opção C — Manter a tela visível com o aviso "em definição"
- **Prós:** nenhuma mudança.
- **Contras:** leva para produção uma tela vazia que o cliente não pediu.

## Decisão
**Opção A.** A tela sai do menu e das rotas (`MODULOS` em `frontend/src/modules/registry.ts`); os
arquivos de `frontend/src/modules/envio/` e `backend/app/modules/envio/` ficam como estão. O backend
segue registrado em `INSTALLED_MODULES` porque não expõe nenhuma rota e porque a guarda
`test_toda_tela_declara_modulo_existente_e_permissao_valida` exige que o módulo declarado na pasta da
tela exista.

## Consequências
- **Positivas:** a entrega em produção só tem telas pedidas; reativar é desfazer uma linha.
- **Negativas e riscos:** o papel Órgão publicador continua no catálogo e pode ser atribuído, mas o
  usuário que só o tenha vê "Sem acesso". Mitigação: não atribuir esse papel enquanto o envio não for
  pedido; a matriz em `docs/modulos/acesso.md` registra isso.

## Validação
Informar a Paloma (GEDA) junto das demais decisões da entrega. Se a CGE-GO pedir o envio, a decisão de
escopo segue a linha "Envio de recursos pelos órgãos" em "Decisões em aberto" e gera nova ADR.

## Revisões
| Data | Revisão | Autor |
|---|---|---|
