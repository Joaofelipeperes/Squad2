import { lazy } from "react";
import type { AppModule } from "@/modules/types";

export const parametrosModule: AppModule = {
  id: "parametros",
  modulo: "parametros",
  permissao: "parametros.acessar",
  secao: "Administração",
  rotulo: "Parâmetros",
  icone: "fa-sliders",
  caminho: "/admin/parametros",
  crumb: "Administração",
  titulo: "Parâmetros de monitoramento",
  userStories: ["US8", "US11", "US16", "US17"],
  pagina: lazy(() => import("./ParametrosPage")),
};
