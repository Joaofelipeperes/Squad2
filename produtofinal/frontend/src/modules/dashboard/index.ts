import { lazy } from "react";
import type { AppModule } from "@/modules/types";

export const dashboardModule: AppModule = {
  id: "dashboard",
  modulo: "painel",
  permissao: "painel.acessar",
  secao: "Visão geral",
  rotulo: "Dashboard",
  icone: "fa-chart-simple",
  caminho: "/",
  crumb: "GEDA · CGE-GO",
  titulo: "Visão Geral",
  userStories: ["US19", "US25"],
  pagina: lazy(() => import("./DashboardPage")),
};
