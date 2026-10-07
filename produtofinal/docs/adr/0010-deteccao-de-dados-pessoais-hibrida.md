# ADR-0010 — Detectar dados pessoais com regras determinísticas e modelo local só para casos ambíguos

| | |
|---|---|
| **Status** | Aceita (estratégia) · modelo local em avaliação |
| **Tipo** | Técnica |
| **Data da decisão** | 30/09/2026 (desenho); reforçada em 01/10/2026 |
| **Data do registro** | 07/10/2026 |
| **Decisores** | Luiza Martins de Freitas Cintra (Eixo 2) e Victor Hugo Benatti |
| **Consultados** | LIGO/TI Central — Adriano e Gabriel (01/10); Prof. Alessandro Cruvinel (01/10) |
| **Origem** | Sessão de 30/09; reunião com o LIGO e reunião com o orientador (01/10) |
| **Afeta** | Módulos `lgpd`, `ia`; US11, US12 |

## Contexto
A varredura precisa cobrir ~2.900 recursos. Tipos como CPF e CNPJ têm formato fixo e dígito
verificador; nomes, endereços e texto livre não têm tamanho nem padrão previsíveis. Em 01/10, na
reunião com o LIGO (equipe de IA da TI Central), o Gabriel questionou o uso de IA e sugeriu regras
para os tipos mapeáveis e IA só para o restante, além de um modelo pequeno ajustado para a tarefa. O
LIGO ofereceu um Qwen ajustado internamente enquanto avalia o custo do Gemini, e ficou de levantar a
periodicidade e o volume de publicação por órgão. No mesmo dia o orientador recomendou modelo offline
para analisar conteúdo, por custo, latência e LGPD (o dado não trafega para fora).

## Critérios de decisão
1. Não enviar dado pessoal para fora da infraestrutura (LGPD).
2. Custo e tempo de processamento compatíveis com o volume.
3. Funcionar mesmo sem chave de modelo comercial.
4. Precisão suficiente para priorizar a revisão humana.

## Opções consideradas

### Opção A — Só regras determinísticas (regex + dígito verificador)
- **Prós:** rápido, gratuito, explicável, sem IA.
- **Contras:** não detecta nome, endereço e texto livre com segurança.

### Opção B — Modelo comercial (Gemini) em todo o conteúdo
- **Prós:** boa compreensão de contexto.
- **Contras:** dado pessoal trafega para fora; custo e latência proporcionais ao volume; depende da chave.

### Opção C — Modelo local em todo o conteúdo
- **Prós:** dado não sai da infraestrutura.
- **Contras:** lento e caro em processamento para todo o volume; exige servidor adequado.

### Opção D — Híbrido: regras para padrões estruturados + modelo local para colunas ambíguas
- **Prós:** a maior parte resolvida sem IA; o modelo vê só amostras das colunas que as regras não
  resolvem; o dado não sai da infraestrutura.
- **Contras:** dois mecanismos para manter e calibrar.

### Opção E — Classificador pequeno especializado (ajustado para a tarefa)
- **Prós:** rápido e barato por chamada; foco em classificação.
- **Contras:** exige dados rotulados ou um modelo pronto; candidatos ainda a avaliar — o Qwen ajustado
  do LIGO; os modelos testados pela Luiza (versão anterior do Qwen, InternVL); a ferramenta indicada
  pelo orientador (grafada "Jeev" na transcrição — confirmar nome); modelos de projetos de LGPD da UFG
  indicados pelo orientador.

## Decisão
Opção D como estratégia. O "modelo local" da etapa de IA será escolhido por avaliação comparativa
entre os candidatos de C e E; qualquer um entra como perfil na tela de IA, sem mudança de código
(ADR-0002).

## Consequências
- **Positivas:** o Eixo 2 não depende do LIGO nem da chave comercial para avançar.
- **Negativas e riscos:** o prazo do LIGO não é o do projeto (alerta do orientador em 01/10); planejar
  a avaliação com modelos já disponíveis ao time.

## Validação
Resultado da avaliação dos modelos (Luiza) e confirmação com a CGE-GO dos tipos de dado pessoal
(lista pendente da GEDA).

## Revisões
| Data | Revisão | Autor |
|---|---|---|
| 01/10/2026 | Estratégia confirmada pela sugestão do LIGO e pela recomendação do orientador; candidatos da Opção E incluídos | Victor |
