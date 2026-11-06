# ADR-0030 — Índice de atenção por órgão é a média ponderada do risco LGPD e do atraso de atualização, com pesos e faixas em Parâmetros

| | |
|---|---|
| **Status** | Aceita (pesos e faixas provisórios até a GEDA validar) |
| **Tipo** | Negócio |
| **Data da decisão** | 05/11/2026 |
| **Data do registro** | 05/11/2026 |
| **Decisores** | Humberto (Eixo 1, tela Organizações — PBI-84), por delegação da coordenação |
| **Consultados** | Victor (coordenação), na reunião de 05/11/2026; Paloma (GEDA) ouviu a proposta na apresentação de 29/10/2026 |
| **Origem** | Reunião 6 (29/10/2026) e reunião de 05/11/2026 do Squad 2 |
| **Afeta** | `painel` (tela Organizações, relatório por órgão), `lgpd` (riscos por órgão), `parametros`; US19, PBI-76, PBI-84 |

## Contexto
A tela Organizações do Protótipo V1 tem as colunas **Riscos LGPD** e **Índice de atenção** (Alto,
Médio, Baixo), que estavam "a definir". Na apresentação de 29/10 o Victor disse à GEDA que achados
confirmados da varredura "entram no índice de risco da LGPD, índice de atenção". Em 05/11 ele
explicou a intenção: um número que diga à GEDA quais órgãos precisam de mais atenção, combinando
**atualização** e **LGPD** — "as duas coisas que ela precisa garantir" —, sem matemática complexa;
sugeriu média ponderada com peso maior para LGPD (0,7 × 0,3) e os pesos na tela de Parâmetros, para a
GEDA ajustar sem depender do time.

O que já existe: a situação de atualização pela periodicidade do PDA (ADR-0023), com o % das bases
vinculadas que estão em dia por órgão; e os achados da varredura LGPD por recurso, com status de
triagem (revisar, confirmado, falso positivo, tratado). A varredura é por demanda e cobre só parte
dos recursos; o vínculo PDA × portal também é parcial.

## Critérios de decisão
1. Explicável para a GEDA numa frase e auditável (PBI-59): dá para refazer a conta à mão.
2. Ajustável pela GEDA sem código (Parâmetros).
3. Não punir nem premiar o órgão por falta de dado (varredura ou vínculo ainda não feitos).
4. Não ampliar acesso: quem não vê o módulo LGPD não recebe nada derivado dele.
5. Prazo: entra nesta sprint, sem tabela nova.

## Opções consideradas

### Opção A — Média ponderada de dois percentuais, pesos e faixas em Parâmetros
Risco LGPD = % dos recursos **varridos** do órgão com achado em aberto (aguardando revisão ou
confirmado). Atraso de atualização = % das bases vinculadas com prazo que estão atrasadas (o
complemento da coluna Atualização). Índice = (peso LGPD × risco + peso atualização × atraso) ÷ soma
dos pesos, de 0 a 100; faixas Baixo/Médio/Alto por dois limites.
- **Prós:** é o que foi combinado na reunião; uma conta simples, com o detalhe na dica da tela;
  percentuais tornam órgãos grandes e pequenos comparáveis; pesos e faixas mudam na tela Parâmetros.
- **Contras:** com poucos recursos varridos o percentual oscila muito (1 de 2 = 50%); os pesos
  iniciais são um palpite até a GEDA calibrar.

### Opção B — Regras fixas por faixa (ex.: qualquer achado confirmado = Alto)
- **Prós:** fácil de entender; destaca o caso mais grave.
- **Contras:** não combina os dois eixos; satura (muitos órgãos "Alto"); mudar a regra exige código;
  não gera um número para ordenar a lista.

### Opção C — Soma de contagens absolutas (achados + bases atrasadas)
- **Prós:** nenhuma divisão; reflete volume.
- **Contras:** órgãos com mais recursos ficam sempre no topo, mesmo em boa situação proporcional;
  escalas diferentes (achados × bases) somadas sem critério.

## Decisão
**Opção A**, com:
- **Riscos LGPD** (coluna): número de recursos do órgão com achado aguardando revisão ou confirmado
  ("N de M varridos"). Falso positivo e tratado (anonimizado) não contam. Sem recurso varrido, "não
  varrido"; sem `lgpd.acessar`, "sem acesso".
- **Índice**: componente sem dado (nenhum recurso varrido, nenhuma base avaliada) ou com peso 0 sai
  da média e os pesos restantes são redistribuídos; sem nenhum componente, "sem dados". Atende o
  critério 3: falta de dado não vira 0 nem 100.
- Sem `lgpd.acessar`, o componente LGPD não entra no índice desse usuário (critério 4).
- **Parâmetros** (provisórios): `peso_lgpd_indice_atencao` = 70, `peso_atualizacao_indice_atencao`
  = 30, `indice_atencao_limite_medio` = 25, `indice_atencao_limite_alto` = 50 (inteiros de 0 a 100;
  limite inclusivo). Pesos relativos: não precisam somar 100.
- Regra pura em `painel/regras.py` (`indice_atencao`), portável (ADR-0004).

## Consequências
- **Positivas:** a tela Organizações fica completa e ordenável pelo índice, com filtro por faixa; o
  relatório por órgão leva as mesmas colunas; a GEDA ajusta a régua sozinha.
- **Negativas e riscos:** enquanto a varredura cobrir poucos recursos, o risco LGPD é instável — a
  tela mostra "N de M varridos" para dar a base. O índice de quem não tem acesso ao LGPD difere do da
  GEDA (só atualização); a dica da coluna diz o que entrou na conta. Um índice só com um componente
  pode chegar a 100 com uma única base atrasada.

## Validação
Apresentar à GEDA (Paloma) no próximo checkpoint: o que conta como risco (achado em aberto), os
pesos 70/30 e as faixas 25/50. Ajustes de valores são feitos em Parâmetros, sem nova ADR; mudança de
fórmula ou de componentes vira revisão ou ADR nova.

## Revisões
| Data | Revisão | Autor |
|---|---|---|
