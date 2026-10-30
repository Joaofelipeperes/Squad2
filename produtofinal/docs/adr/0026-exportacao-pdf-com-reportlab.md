# ADR-0026 — Gerar o PDF dos relatórios no backend com reportlab

| | |
|---|---|
| **Status** | Aceita |
| **Tipo** | Técnica |
| **Data da decisão** | 30/10/2026 |
| **Data do registro** | 30/10/2026 |
| **Decisores** | Victor Hugo Benatti (coordenação) |
| **Consultados** | — (validar com o João, responsável pelo módulo `relatorios`) |
| **Origem** | Sessão de 30/10: pedido de exportação em PDF na tela Relatórios (card ClickUp 86e3xcapz) |
| **Afeta** | Módulo `relatorios`, `backend/pyproject.toml`, imagem da API; US20, PBI-60 |

## Contexto
A tela Relatórios (US20) exporta os 6 relatórios em XLSX e CSV com `openpyxl`, que já estava nas
dependências. Foi pedida também a exportação em PDF, para anexar em prestação de contas e enviar a
quem não trabalha com planilhas. Os relatórios têm até 12 colunas e centenas de linhas (ex.: 410
bases do PDA, 797 recursos em formato fechado), então o PDF precisa quebrar páginas, repetir o
cabeçalho da tabela e quebrar o texto dentro das células. O PGP v2 só permite ferramentas gratuitas
ou de código aberto e infraestrutura leve.

## Critérios de decisão
1. Download direto do arquivo, igual ao XLSX/CSV (mesma rota e mesma permissão).
2. Tabelas longas e largas legíveis: quebra de página, cabeçalho repetido, texto quebrado na célula.
3. Licença livre e nenhuma dependência de sistema na imagem da API.
4. Manutenção simples pelo time da CGE-GO depois da Residência.

## Opções consideradas

### Opção A — reportlab
- **Prós:** biblioteca madura (BSD), Python puro do ponto de vista da imagem (wheels prontos);
  `LongTable` com `repeatRows` repete o cabeçalho em cada página; `Paragraph` quebra texto nas
  células; A4 paisagem, numeração de páginas e rodapé simples.
- **Contras:** dependência nova de ~4 MB; API mais verbosa que a do fpdf2.

### Opção B — fpdf2
- **Prós:** Python puro e leve; API de tabela simples.
- **Contras:** LGPL-3; menos controle sobre quebra de texto e altura das linhas em tabelas
  longas com muitas colunas.

### Opção C — Imprimir pelo navegador (CSS de impressão)
- **Prós:** nenhuma dependência nova no backend.
- **Contras:** não é download direto (o usuário salva como PDF pelo Ctrl+P); o resultado depende do
  navegador; a prévia da tela só tem as 50 primeiras linhas, então seria preciso outra tela só
  para impressão.

## Decisão
Opção A: reportlab. Atende melhor os critérios 1 e 2 sem dependência de sistema (critério 3), e o
PDF sai pela mesma rota `GET /relatorios/{id}/exportar?formato=pdf`, com as mesmas permissões dos
outros formatos.

## Consequências
- **Positivas:** os três formatos saem do mesmo `Tabela` (colunas + linhas) do service; o PDF leva
  título, referência (ex.: PDA vigente), data de geração e total de linhas.
- **Negativas e riscos:** relatórios com muitas colunas ficam com fonte pequena (8 pt) em A4
  paisagem; se a GEDA pedir layout próprio (logo, assinatura), o gerador cresce. A imagem da API
  precisa ser reconstruída para instalar a dependência.

## Validação
Com o João (responsável pelo módulo) e, quanto ao layout, com a Paloma na próxima apresentação.

## Revisões
| Data | Revisão | Autor |
|---|---|---|
