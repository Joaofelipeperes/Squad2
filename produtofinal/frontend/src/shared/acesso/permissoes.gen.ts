// ARQUIVO GERADO por scripts/gerar_permissoes_ts.py a partir de
// backend/app/core/permissoes.py — NÃO EDITAR À MÃO.

export const PERMISSOES = [
  "painel.acessar",
  "inventario.acessar",
  "inventario.coletar",
  "pda.acessar",
  "pda.editar_vinculos",
  "pda.gerenciar_planos",
  "atualizacoes.acessar",
  "rastreabilidade.acessar",
  "lgpd.acessar",
  "lgpd.triar",
  "lgpd.aprovar_correcao",
  "metadados.acessar",
  "relatorios.acessar",
  "relatorios.exportar",
  "assistente.usar",
  "envio.acessar",
  "envio.enviar_recurso",
  "parametros.acessar",
  "parametros.editar",
  "ia.configurar",
  "acesso.gerenciar_usuarios",
  "acesso.gerenciar_papeis"
] as const;

export type Permissao = (typeof PERMISSOES)[number];

export const ROTULOS_PERMISSAO: Record<Permissao, string> = {
  "painel.acessar": "Ver Dashboard e Organizações",
  "inventario.acessar": "Ver Datasets",
  "inventario.coletar": "Atualizar dados",
  "pda.acessar": "Ver Monitoramento do PDA",
  "pda.editar_vinculos": "Editar vínculos do PDA",
  "pda.gerenciar_planos": "Gerenciar PDAs",
  "atualizacoes.acessar": "Ver Atualizações",
  "rastreabilidade.acessar": "Ver Rastreabilidade",
  "lgpd.acessar": "Ver Dados Pessoais (LGPD)",
  "lgpd.triar": "Triar achados LGPD",
  "lgpd.aprovar_correcao": "Aprovar anonimização",
  "metadados.acessar": "Ver conformidade de metadados",
  "relatorios.acessar": "Ver Relatórios",
  "relatorios.exportar": "Exportar relatórios",
  "assistente.usar": "Usar o Assistente GEDA",
  "envio.acessar": "Ver área do órgão publicador",
  "envio.enviar_recurso": "Enviar recurso",
  "parametros.acessar": "Ver parâmetros",
  "parametros.editar": "Editar parâmetros",
  "ia.configurar": "Configurar modelos de IA",
  "acesso.gerenciar_usuarios": "Gerenciar usuários",
  "acesso.gerenciar_papeis": "Gerenciar papéis"
};
