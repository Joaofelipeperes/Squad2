# Módulo: ckan_config (Configurações CKAN)

Perfis de conexão com o CKAN e troca do CKAN em uso (ADR-0024). Tela em **Administração ·
Configurações CKAN** (`/admin/ckan`), permissão `ckan_config.gerenciar` (só administrador).
"Novo perfil" e "Editar" abrem o formulário em modal (`frontend/src/modules/ckan/PerfilCkanForm.tsx`).
A tabela de perfis ordena por coluna e pagina no navegador (`useTabela`, ADR-0028).

## Para que serve
A solução lê de um CKAN (inventário/LGPD) e lê a auditoria do dsaudit (rastreabilidade/diff). Em vez
de depender só do `.env`/`GDA_ENVIRONMENT`, esta tela guarda **perfis de conexão** e deixa escolher
qual CKAN o sistema usa. A troca vale **na hora, para todo o sistema**, e **sobrepõe** o `.env`.
Trocar de perfil **não apaga** os dados já coletados (inventário, eventos, achados): só muda de qual
CKAN as próximas leituras vêm.

## Perfil
- **nome** — identificação (ex.: "CKAN Docker", "Homologação").
- **base_url** — CKAN da leitura pública (coleta do inventário e download de recursos da LGPD).
- **auditoria_base_url** — CKAN de onde a auditoria/diff (dsaudit) é lida; vazio = usa a `base_url`.
- **auditoria_api_token** — token de um usuário **editor**, exigido pela `dsaudit_activity_list`.
  Guardado cifrado (ADR-0019 / `core/crypto`); a tela mostra só uma dica (`••••1a2b`).
- **selecionado** — o CKAN em uso agora (no máximo um).

## Resolução do CKAN em uso
`service.config_ativa()` lê o perfil `selecionado` do banco a cada construção de cliente
(`cliente_leitura`, `cliente_auditoria`), então a troca é imediata e vale para a API e o worker.
Sem nenhum perfil, cai para o `.env` (compatível com quem ainda não abriu a tela). Na primeira
subida (nenhum perfil gravado), `semear_perfil_inicial` grava o CKAN lido como perfil em uso: com
`GDA_ENVIRONMENT=producao` (servidores da UFG e da SECTI/CGE, ADR-0032), o "Portal de Dados Abertos
GO" (`GDA_CKAN_BASE_URL`, vazio = https://dadosabertos.go.gov.br); em dev e homologação, o "CKAN
Docker" local. Chamado pela preparação da API a cada subida (`app/instalacao.py`); não mexe em
perfis já gravados.

## Rotas
- `GET /ckan-config/perfis` — lista os perfis.
- `POST /ckan-config/perfis` — cria (o primeiro criado já entra em uso).
- `PUT /ckan-config/perfis/{id}` — edita (token: ausente = mantém, vazio = remove, texto = troca).
- `DELETE /ckan-config/perfis/{id}` — exclui (não permite excluir o perfil em uso).
- `POST /ckan-config/perfis/{id}/selecionar` — passa a usar este CKAN em todo o sistema.

## Histórico de alterações
| Data | Alteração | Autor |
|---|---|---|
| 09/11/2026 | Tela: tabela de perfis com ordenação por coluna e paginação (`useTabela`, ADR-0028); retirados da tela os textos sobre a troca valer na hora para todo o sistema (lede, subtítulo do painel e aviso amarelo) | Victor |
| 09/11/2026 | Criação e edição de perfil passam a abrir em modal (`PerfilCkanForm.tsx`, componente `Modal`), no mesmo padrão do cadastro de perfil de Modelos de IA; antes o formulário aparecia como painel abaixo da tabela | Victor |
| 06/11/2026 | `semear_perfil_docker` não grava o perfil "CKAN Docker" com `GDA_ENVIRONMENT=producao`: no servidor (UFG/CGE, ADR-0032) a coleta tentava o CKAN local inexistente e falhava. Teste `test_seed_nao_grava_perfil_docker_em_producao` | Victor |
| 09/11/2026 | `semear_perfil_docker` vira `semear_perfil_inicial` e, em produção, grava o perfil "Portal de Dados Abertos GO" (portal oficial) em uso, para a tela mostrar o CKAN lido no servidor (ADR-0032, revisão da ADR-0024). Chamado por `app/instalacao.py`. Teste `test_seed_em_producao_grava_o_portal_oficial` | Victor |
