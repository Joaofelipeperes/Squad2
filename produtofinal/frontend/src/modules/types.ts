import type { ComponentType, LazyExoticComponent } from "react";
import type { Permissao } from "@/shared/acesso/permissoes.gen";

/** Seções do menu lateral, na ordem do protótipo V1 (+ Órgão publicador e Administração). */
export const SECOES = [
  "Visão geral",
  "Governança do PDA",
  "Inventário",
  "Saídas",
  "Órgão publicador",
  "Administração",
] as const;
export type Secao = (typeof SECOES)[number];

/**
 * Contrato de uma tela. Cada pasta em src/modules/ exporta um `AppModule` no index.ts;
 * menu, rotas e título da topbar são montados a partir do registro (registry.ts).
 *
 * `permissao` é OBRIGATÓRIA: sem ela o item some do menu e a rota não existe.
 * `modulo` liga a tela ao módulo do backend e ao seu docs/modulos/<modulo>.md.
 */
export interface AppModule {
  id: string;
  modulo: string;
  permissao: Permissao;
  secao: Secao;
  rotulo: string;
  icone: string;            // classe Font Awesome, ex.: "fa-chart-simple"
  caminho: string;
  crumb: string;
  titulo: string;
  pagina: LazyExoticComponent<ComponentType>;
  destaqueAlerta?: boolean; // contador vermelho no menu (LGPD)
  userStories: string[];
}

/** Componente global (fora das rotas), ex.: o botão flutuante do Assistente GEDA. */
export interface AppWidget {
  id: string;
  modulo: string;
  permissao: Permissao;
  componente: LazyExoticComponent<ComponentType>;
}
