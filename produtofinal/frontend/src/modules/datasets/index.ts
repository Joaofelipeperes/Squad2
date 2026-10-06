import { lazy } from "react";
import type { AppModule } from "@/modules/types";

export const datasetsModule: AppModule = {
  id: "datasets",
  modulo: "inventario",
  permissao: "inventario.acessar",
  secao: "Inventário",
  rotulo: "Datasets",
  icone: "fa-database",
  caminho: "/datasets",
  crumb: "Inventário",
  titulo: "Datasets",
  userStories: ["US5", "US16", "US17"],
  pagina: lazy(() => import("./DatasetsPage")),
};
