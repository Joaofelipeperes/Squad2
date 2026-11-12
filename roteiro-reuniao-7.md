# Roteiro — Reunião 7 com as POs (CGE)

Período: **29/10 (Reunião 6) → 05/11**. Fontes: transcrição da Reunião 6, commits em `desenvolvimento`
desde 29/10 e commits da branch `dev-86e3xcapz` (card 86e3xcapz), incluindo o `2a342a9` de 05/11.

Legenda: ✅ feito · 🔀 commitado e enviado na `dev-86e3xcapz`, **ainda sem merge em `desenvolvimento`** ·
🔶 parcial · ⏳ pendente · ↩️ já existia antes da reunião (só mostrar)

---

## 1. Pedidos da Paloma / Júnior na Reunião 6

| # | Pedido (o que ela falou) | Status | O que foi feito / onde mostrar |
|---|---|---|---|
| 1 | **Datasets do mais recente para o mais antigo** ("o último criado aparece primeiro") | ✅ 🔀 | Tela **Datasets**: nova coluna **"Criado no CKAN"** e ordem padrão pela data de criação, mais recente primeiro. A coleta também passou a ler o CKAN nessa ordem. E qualquer coluna agora ordena com um clique no título (ADR-0028). |
| 2 | **Botão que leva ao dataset no portal**, mantendo o download | ↩️ | O detalhe do dataset já tem **"Abrir no portal"** no rodapé do modal, desde 18/10. O download dos recursos continua igual. Na reunião abrimos o recurso, não esse botão. **Mostrar o botão.** |
| 3 | **Base vinculada ao PDA × base espontânea** (para achar base que é do PDA mas não foi vinculada) | ✅ + ✅ 🔀 | ✅ **Dashboard**: total e % de bases espontâneas + gráfico dos 10 órgãos com mais espontâneas (30/10, ADR-0026). ✅ 🔀 **Datasets**: coluna e filtro **"Tipo de base"** (Prevista no PDA × Espontânea). Fluxo para mostrar: filtrar por órgão + "Espontânea" → achar a base → ir ao PDA → vincular → ela passa a "Prevista". |
| 4 | Rastreabilidade: **ver o que mudou dentro do arquivo** (alteração real × "falsa atualização") | ✅ | O diff do conteúdo voltou a funcionar pela auditoria do portal. A tela mostra uma prévia de 3 linhas e **baixa o CSV com todas as alterações**, que foi a sugestão do Prof. Alessandro (João, 30/10). |
| 5 | Rastreabilidade: só aparecia depois de **"esvaziar cache"** (o problema da demo) | ✅ 🔀 | Corrigido (ADR-0029): a API não fica mais em cache e as telas recarregam sozinhas quando a coleta termina. A Rastreabilidade consulta de novo enquanto a sincronização da auditoria roda. **Mostrar "Atualizar dados" sem F5.** |
| 6 | Distinguir **recurso sobrescrito × recurso novo × alteração de metadado** e filtrar por tipo | ↩️ | O filtro por **tipo de alteração** já existia. Repetir o teste dos dois jeitos (sobrescrever e criar recurso novo). |
| 7 | Atualização medida pelo recurso, não por mudança de nome/metadado | 🔶 | Nova tela **Monitoramento de Atualizações** (item 13) usa o `last_modified` do **recurso** e avisa que mudança só de metadado não conta. A precisão total (renomear um arquivo também mexe no `last_modified`) depende da extensão de auditoria instalada no portal. |
| 8 | LGPD: **CNPJ não é dado pessoal**; manter "nome" | ✅ | Os tipos ativos vêm do parâmetro `tipos_dado_pessoal`: CPF, e-mail, telefone, endereço, data de nascimento e nome. **CNPJ fica fora** e pode ser ajustado em *Administração → Parâmetros*, sem mexer no código. |
| 9 | LGPD: **anonimizar só depois da confirmação** (opção 2 da Luiza) | ↩️ | O fluxo já funciona assim (ADR-0008): só achados **confirmados** são anonimizados, com prévia, download da prévia, aprovação e publicação. Também dá para reverter. Mostrar para fechar o ponto. |
| 10 | Relatórios / **exportar o mapeamento** (Excel, PDF) | ✅ 🔀 | Nova tela **Relatórios** com os 6 relatórios do protótipo: cumprimento do PDA, atualizações, dados pessoais, por órgão, datasets sem recurso e formatos não abertos. Tem prévia e exporta em **XLSX, CSV e PDF** (30/10). |
| 11 | Enviar **imagens/documento das telas** para a Paloma dar devolutiva dos gráficos | ⏳ *(confirmar)* | Ação do Victor. Se já foi enviado, pedir a devolutiva sobre **quais gráficos adicionar no Dashboard**. |
| 12 | Gráficos novos no Dashboard (aguardando a devolutiva dela) | 🔶 | Sem a devolutiva, já entraram no Dashboard **Possíveis dados pessoais** (por tipo e por status da triagem) e **Bases espontâneas**. |
| 13 | **Especificar a infraestrutura ideal** para a Paloma negociar com a SETI (pedido do Prof. Alessandro) | ⏳ | Não há documento de infra no repositório. Levar CPU, RAM, disco, GPU para o modelo de IA, Docker e acesso ao CKAN. |
| 14 | Reuniões semanais | ✅ | Esta é a primeira. |
| 15 | Ponto focal do órgão com acesso só de visualização (futuro) | ↩️ | Já é possível: usuário vinculado a um órgão + papel com permissões só de leitura. Tudo respeita o escopo do órgão. |

## 2. Metas de novembro anunciadas na reunião

| Meta | Status |
|---|---|
| Relatórios Excel / PDF | ✅ 🔀 Entregue (item 10) |
| **Índice de atenção** por órgão (com o risco LGPD) | ⏳ A coluna existe em Organizações, mas mostra "a definir". `indice_atencao_por_orgao` ainda não foi implementado. **Validar o critério com a Paloma.** A coluna "Riscos LGPD" já aparece. |
| Validar o eixo 1 (PDA) com as POs | ⏳ Pode ser feito nesta reunião |
| Aprovar o motor LGPD (modelo de IA) com a SETI + GPU/CPU | ⏳ Depende da SETI (junto com o item 13) |
| Deploy na SETI (homologação a partir de ~16/11) | ⏳ |

## 3. O que mais fizemos além dos pedidos

| Entrega | Status | Resumo |
|---|---|---|
| **Monitoramento de Atualizações** (nova tela) | ✅ | Cartões de situação, filtros por dataset, órgão, periodicidade e situação, dias desde a última atualização e prazo esperado. A situação segue a periodicidade do PDA (João, PBI-81). |
| **Configurações CKAN** (nova tela) | ✅ | Perfis de conexão e troca do CKAN em uso, que vale na hora para todo o sistema sem apagar dados. Token de auditoria cifrado (João). |
| Cliente CKAN mais robusto | ✅ | Segue redirects. Resposta "Acesso negado" em HTML não derruba mais a auditoria. |
| **Paginação e ordenação em todas as tabelas** | ✅ 🔀 | Datasets, PDA, Atualizações, Organizações, LGPD, Rastreabilidade, Log de acesso e Usuários. 50 por página (até 999), total no rodapé, clique na coluna ordena (ADR-0028). |
| Rastreabilidade e Log de acesso paginados no banco | ✅ 🔀 | Antes cortavam em 300 e 200 linhas sem avisar. Agora o total é exato e o CSV do log sai com até 5.000 linhas. |
| LGPD: **achados agrupados por arquivo** + fila com rolagem | ✅ | Uma linha por arquivo, e os achados aparecem ao expandir (Luiza, 04/11). |
| Assistente: **sem as sugestões grandes** | ✅ | Remove o que tinhamos dito na reunião que ocupava espaço demais. |
| LGPD: fila da varredura no worker + downloads espaçados | ✅ | A varredura não trava mais e respeita o limite do portal (ADR-0025, 29/10). |
| CKAN escolhido por ambiente | ✅ | Desenvolvimento/homologação usam o CKAN Docker e produção usa o portal (ADR-0024). |
| Deploy novo chega sem limpar cache | ✅ 🔀 | O `index.html` passa a ser revalidado no nginx (ADR-0029). |

## 4. Ordem sugerida da demo

1. **Dashboard** → bases espontâneas e possíveis dados pessoais (itens 3 e 12)
2. **Datasets** → ordem "mais recente primeiro", coluna "Criado no CKAN", filtro "Tipo de base" → abrir um dataset → **"Abrir no portal"** (itens 1, 2 e 3)
3. **PDA** → vincular uma base espontânea → voltar e ver que virou "Prevista" (item 3)
4. **Monitoramento de Atualizações** (nova tela, item 7)
5. **Rastreabilidade** → editar no CKAN → "Atualizar dados" → aparece **sem limpar cache** → diff + CSV → teste de sobrescrever × criar recurso novo (itens 4, 5 e 6)
6. **Riscos de Dados Pessoais** → achados por arquivo → confirmar → anonimizar (itens 8 e 9)
7. **Relatórios** → prévia → exportar PDF e Excel (item 10)
8. **Organizações** → paginação e ordenação → explicar o índice de atenção e **pedir o critério**
9. **Assistente** sem as sugestões
10. **Fechamento:** infra para a SETI, aprovação do modelo LGPD, data da homologação e devolutiva dos gráficos

## 5. O que levar como pergunta para as POs

- Qual o **critério do índice de atenção**: que pesos dar para atraso, desatualização, risco LGPD e formatos fechados?
- **Quais gráficos** acrescentar no Dashboard?
- 50 itens por página é um bom padrão no dia a dia?
- Confirmar a **lista final de tipos de dado pessoal** (o parâmetro ainda está marcado como "provisório até a lista objetiva da CGE-GO").

> ⚠️ Antes da reunião: os itens 🔀 estão commitados na `dev-86e3xcapz` e já foram enviados ao GitHub,
> mas ainda não estão em `desenvolvimento`. São os commits de relatórios (634ef59, 2da1e6b, 4ca12b2)
> e o 2a342a9. Para demonstrar a partir de `desenvolvimento` ou do ambiente compartilhado, abra o PR
> e faça o merge antes. Rodando a demo direto da `dev-86e3xcapz`, já está tudo lá.
