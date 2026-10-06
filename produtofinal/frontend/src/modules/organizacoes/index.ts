import { lazy } from "react";
import type { AppModule } from "@/modules/types";

export const organizacoesModule: AppModule = {
  id: "organizacoes",
  modulo: "painel",
  permissao: "painel.acessar",
  secao: "Inventário",
  rotulo: "Organizações",
  icone: "fa-building-columns",
  caminho: "/organizacoes",
  crumb: "Inventário",
  titulo: "Organizações",
  userStories: ["US19"],
  pagina: lazy(() => import("./OrganizacoesPage")),
};
