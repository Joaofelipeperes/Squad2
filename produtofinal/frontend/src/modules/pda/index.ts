import { lazy } from "react";
import type { AppModule } from "@/modules/types";

export const pdaModule: AppModule = {
  id: "pda",
  modulo: "pda",
  permissao: "pda.acessar",
  secao: "Governança do PDA",
  rotulo: "Monitoramento PDA",
  icone: "fa-clipboard-check",
  caminho: "/pda",
  crumb: "Governança do PDA",
  titulo: "Monitoramento do PDA",
  userStories: ["US6", "US7", "US8"],
  pagina: lazy(() => import("./PdaPage")),
};
