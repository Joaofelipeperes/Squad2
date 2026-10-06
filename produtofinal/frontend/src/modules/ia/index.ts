import { lazy } from "react";
import type { AppModule } from "@/modules/types";

export const iaModule: AppModule = {
  id: "ia",
  modulo: "ia",
  permissao: "ia.configurar",
  secao: "Administração",
  rotulo: "Modelos de IA",
  icone: "fa-microchip",
  caminho: "/admin/ia",
  crumb: "Administração",
  titulo: "Modelos de IA",
  userStories: ["US11", "US28"],
  pagina: lazy(() => import("./ModelosIAPage")),
};
