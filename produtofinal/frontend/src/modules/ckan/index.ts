import { lazy } from "react";
import type { AppModule } from "@/modules/types";

export const ckanModule: AppModule = {
  id: "ckan_config",
  modulo: "ckan_config",
  permissao: "ckan_config.gerenciar",
  secao: "Administração",
  rotulo: "Configurações CKAN",
  icone: "fa-plug",
  caminho: "/admin/ckan",
  crumb: "Administração",
  titulo: "Configurações CKAN",
  userStories: ["ADR-0024"],
  pagina: lazy(() => import("./ConfiguracoesCkanPage")),
};
