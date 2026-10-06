# Módulo `lgpd` — Dados pessoais e anonimização

| | |
|---|---|
| **Status** | Parcial (tabelas e etapa de IA prontas; detectores e telas a implementar) |
| **Responsável** | Luiza (Eixo 2) |
| **User stories** | US11, US12, US13, US26, US27 (PBI-31 a PBI-42, PBI-86 a PBI-95) |
| **Backend** | `backend/app/modules/lgpd/` · escrita no CKAN em `backend/app/integrations/ckan/writer.py` |
| **Frontend** | `frontend/src/modules/lgpd/` |
| **Última atualização** | 30/09/2026 |

## Propósito
Varre os recursos publicados em busca de possíveis dados pessoais, prioriza os achados para revisão
humana e, após aprovação, publica no CKAN a versão anonimizada do recurso.

## Telas
| Tela | Rota | Permissão para ver | Ações na tela (permissão) |
|---|---|---|---|
| Riscos de Dados Pessoais | `/lgpd` | `lgpd.acessar` | Marcar falso positivo / confirmado / tratado (`lgpd.triar`); prévia e aprovação da anonimização (`lgpd.aprovar_correcao`); exportar (`relatorios.exportar`) |

Referência visual: `#screen-lgpd` e `#modal-lgpd` do Protótipo V1 (contador vermelho no menu).

## API
Nenhum endpoint ainda. Previstos:

| Método | Rota (`/api/v1/lgpd`) | Permissão | Descrição |
|---|---|---|---|
| GET | `/achados` | `lgpd.acessar` | Lista priorizada com filtros |
| POST | `/achados/{id}/decisao` | `lgpd.triar` | Registra decisão humana (PBI-40) |
| GET | `/achados/{id}/previa` | `lgpd.aprovar_correcao` | Prévia da anonimização (PBI-91) |
| POST | `/correcoes` | `lgpd.aprovar_correcao` | Aprova e publica no CKAN (PBI-92/93) |
| POST | `/correcoes/{id}/reverter` | `lgpd.aprovar_correcao` | Restaura o original (PBI-94) |

## Serviços e métodos
Pipeline da varredura (US11), em `service.py`:
1. Leitura do recurso tabular (PBI-32).
2. `detectar_por_regras(coluna) -> ClassificacaoColuna | None` — **a implementar**: CPF/CNPJ com
   dígito verificador, e-mail, telefone, CEP. Não usa IA.
3. `classificar_colunas_ambiguas(db, colunas) -> list[ClassificacaoColuna]` — **implementado**:
   envia nome da coluna + até 10 amostras à tarefa de IA `classificacao_dp` (modelo local por
   política) e interpreta a resposta JSON. Resposta inválida → nenhuma classificação.
4. Score de confiança e prioridade → `Achado` (PBI-86, PBI-36).

Tipos de apoio: `AmostraColuna(nome, valores)`, `ClassificacaoColuna(coluna, tipo, confianca)`.

## Modelo de dados
| Tabela | Colunas relevantes |
|---|---|
| `lgpd_achado` | recurso_id, coluna, linha, ocorrencias, tipo, metodo (regra/ia), confianca, prioridade, status, impressao_digital |
| `lgpd_decisao` | achado_id, decisao, justificativa, usuario, momento (histórico imutável — PBI-42) |
| `lgpd_correcao` | recurso_id, aprovado_por, aprovado_em, caminho_backup, status, erro |

## Permissões
| Permissão | Papéis padrão | Sensível |
|---|---|:-:|
| `lgpd.acessar` | Administrador, Gerência GEDA, Equipe GEDA | ✓ |
| `lgpd.triar` | Administrador, Gerência GEDA | ✓ |
| `lgpd.aprovar_correcao` | Administrador, Gerência GEDA | ✓ |

## Interações com outros módulos
| Direção | Módulo | O quê |
|---|---|---|
| consome | inventario | `Recurso` (url, formato, `url_type`) |
| consome | ia | `AIGateway.chat(TarefaIA.CLASSIFICACAO_DADO_PESSOAL, ...)` |
| consome | parametros | `tipos_dado_pessoal`, `confianca_minima_lgpd` |
| consome | CKAN (integração) | `CkanWriter.replace_resource_file` — única escrita do sistema |
| é consumido por | painel | ranking de exposição por órgão (US27) e indicador de risco (PBI-57) |
| é consumido por | atualizacoes | correções publicadas não contam como atualização (PBI-79) |
| é consumido por | relatorios | relatório priorizado (PBI-38) |
| é consumido por | assistente | **apenas contagens**, nunca conteúdo |

## Jobs agendados
Previsto: varredura em lote após a coleta diária (PBI-34).

## Regras de negócio e decisões
- **Não retenção** (PBI-35): o achado guarda localização e tipo, nunca o valor encontrado.
- Sinaliza, não bloqueia a publicação (PBI-39).
- Achado já avaliado não volta como novo (`impressao_digital`, PBI-41).
- Anonimização só após aprovação de quem tem `lgpd.aprovar_correcao`, com registro de quem e quando.
- Escrita no CKAN exige `GDA_CKAN_WRITE_ENABLED=true`, token da GEDA e recurso `url_type = upload`;
  recursos em link externo são sinalizados para a GEDA acionar o órgão.
- Cópia do original fora do banco, conforme política de retenção da GEDA; nunca versionada.

## Pendências
- Lista objetiva de tipos de dado pessoal e regras de anonimização por tipo (CGE-GO).
- Política de retenção do original (GEDA).
- Credencial de escrita e autorização formal CGE-GO/SECTI (PBI-95).
- Servidor para modelo local em produção (SECTI).

## Histórico de alterações
| Data | Alteração | Autor |
|---|---|---|
| 30/09/2026 | Tabelas, pipeline e etapa de classificação por IA (`classificar_colunas_ambiguas`) | Claude / Victor |
| 30/09/2026 | Permissões granulares `lgpd.acessar`, `lgpd.triar`, `lgpd.aprovar_correcao` | Claude / Victor |
