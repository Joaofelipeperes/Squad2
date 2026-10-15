import { lazy } from "react";
import type { AppModule } from "@/modules/types";

export const logsAcessoModule: AppModule = {
  id: "logs-acesso",
  modulo: "acesso",
  permissao: "acesso.ver_logs",
  secao: "Administração",
  rotulo: "Log de acesso",
  icone: "fa-list-check",
  caminho: "/admin/logs",
  crumb: "Administração",
  titulo: "Log de acesso",
  userStories: [],
  pagina: lazy(() => import("./LogsAcessoPage")),
};
