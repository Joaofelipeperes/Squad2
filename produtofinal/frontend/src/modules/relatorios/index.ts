import { lazy } from "react";
import type { AppModule } from "@/modules/types";

export const relatoriosModule: AppModule = {
  id: "relatorios",
  modulo: "relatorios",
  permissao: "relatorios.acessar",
  secao: "Saídas",
  rotulo: "Relatórios",
  icone: "fa-file-lines",
  caminho: "/relatorios",
  crumb: "Saídas",
  titulo: "Relatórios",
  userStories: ["US20"],
  pagina: lazy(() => import("./RelatoriosPage")),
};
