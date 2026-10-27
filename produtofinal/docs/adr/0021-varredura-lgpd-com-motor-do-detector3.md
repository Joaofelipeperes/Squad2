# ADR-0021 — Varrer os recursos com o motor do detector3 portado para o backend, com a IA pelo gateway

| | |
|---|---|
| **Status** | Proposta |
| **Tipo** | Técnica |
| **Data da decisão** | pendente (proposta em 26/10/2026) |
| **Data do registro** | 26/10/2026 |
| **Decisores** | Luiza Martins de Freitas Cintra (Eixo 2) |
| **Consultados** | — |
| **Origem** | Sessão de trabalho de 26/10/2026: integrar a tela de LGPD do protótipo ao backend usando o `detector3.py` e os modelos qwen2.5 7b, qwen3 e qwen3.5 |
| **Afeta** | Módulos `lgpd` e `ia`; integração CKAN (leitura de arquivos); US11, US12; ADR-0002, ADR-0010 |

## Contexto
A estratégia híbrida (ADR-0010) foi implementada pela Luiza fora do sistema, no `detector3.py`:
regras com dígito verificador e validação, perfil de coluna para valores atípicos, contexto, descarte
de coincidências e, para endereço, um modelo local via Ollama precedido por um filtro semântico de
embeddings (bge-m3), calibrado com gabarito. O módulo `lgpd` do sistema só tinha as tabelas e uma
classificação por coluna sem uso. A tela do protótipo usava dados fixos.

Restrições: dado pessoal não sai da infraestrutura (só modelo local para tarefas sensíveis); a IA só
é usada pelo `AIGateway` (AGENTS.md); não guardar o valor encontrado (PBI-35); sem dependência nova
sem ADR.

## Critérios de decisão
1. Mesmo comportamento do detector3, já calibrado no gabarito.
2. Política LGPD aplicada pelo gateway (modelo local, registro de uso sem conteúdo).
3. Trocar o modelo (qwen2.5:7b-instruct, qwen3, qwen3.5) pela tela, sem código.
4. Sem dependências novas.

## Opções consideradas

### Opção A — Chamar o `detector3.py` como programa externo (subprocesso)
- **Prós:** zero alteração no script.
- **Contras:** fala direto com o Ollama, fora do gateway e da política; exige pandas e requests na
  imagem; saída em CSV para reinterpretar; erros e progresso difíceis de controlar.

### Opção B — Portar o motor para o módulo `lgpd`, com a IA injetada (escolhida na proposta)
- **Prós:** mesmas classes e regras do script (o código foi copiado, não reescrito); as chamadas de IA
  passam pelo gateway (política, contingência, `ia_uso`); sem pandas (leitura com `csv` e openpyxl,
  que já é dependência); funções puras, reaproveitáveis numa extensão CKAN (ADR-0004).
- **Contras:** duas cópias do motor (script e sistema) para manter alinhadas.

### Opção C — Reescrever a detecção do zero no backend
- **Prós:** código desenhado para o sistema desde o início.
- **Contras:** perde a calibração do detector3; retrabalho sem ganho.

## Decisão
Proposta: Opção B. Desdobramentos necessários:
- O contrato de IA ganha `embed()` (Ollama `/api/embed` e compatível com OpenAI `/embeddings`) e o
  gateway, `embed(tarefa, textos)`; nova tarefa sensível `embeddings_dp` (filtro semântico).
- O adaptador Ollama pede `think: false` (Qwen3/Qwen3.5 sem raciocínio), com nova tentativa sem o
  parâmetro para modelos que não o aceitam (Qwen2.5).
- Um achado por (recurso, coluna, tipo) — primeira linha, nº de células, maior confiança — em vez de
  um por célula (milhares de linhas para um CSV de servidores).
- Varredura em segundo plano na API (como a coleta manual) e job incremental no worker, registrada
  em `lgpd_varredura` com aviso quando uma etapa de IA não está configurada.

## Consequências
- **Positivas:** a tela funciona com dados reais; o modelo é trocado pela tela; o assistente passa a
  ter contagens reais de achados.
- **Negativas e riscos:** manter o script e o módulo alinhados (mudança de regra no detector3 deve
  ser replicada em `deteccao.py`); varredura em CPU é lenta para recursos grandes (limite por tamanho
  e por execução do job); PDF ainda não coberto (exige PyMuPDF/Tesseract — nova ADR).

## Validação
Luiza: comparar o resultado do módulo com o do `detector3.py` no mesmo arquivo e no gabarito, e
escolher o modelo (qwen2.5:7b-instruct × qwen3 × qwen3.5) e a margem do filtro.

## Revisões
| Data | Revisão | Autor |
|---|---|---|
| 27/10/2026 | Renumerada de ADR-0018 para ADR-0021 no merge com a `desenvolvimento` (as ADR-0017 a 0019 já existiam lá). Implementação ajustada às ADR-0018/0019: acesso ao banco pelo `LgpdDao`, chaves pelo `id` próprio, download pelo `id_ckan`. Sem mudança na decisão | Luiza |
