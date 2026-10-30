# Módulo: ckan_config (Configurações CKAN)

Perfis de conexão com o CKAN e troca do CKAN em uso (ADR-0024). Tela em **Administração ·
Configurações CKAN** (`/admin/ckan`), permissão `ckan_config.gerenciar` (só administrador).

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
subida, `semear_perfil_docker` grava o CKAN local do Docker como o perfil "CKAN Docker" em uso.

## Rotas
- `GET /ckan-config/perfis` — lista os perfis.
- `POST /ckan-config/perfis` — cria (o primeiro criado já entra em uso).
- `PUT /ckan-config/perfis/{id}` — edita (token: ausente = mantém, vazio = remove, texto = troca).
- `DELETE /ckan-config/perfis/{id}` — exclui (não permite excluir o perfil em uso).
- `POST /ckan-config/perfis/{id}/selecionar` — passa a usar este CKAN em todo o sistema.
