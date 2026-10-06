import { lazy } from "react";
import type { AppModule } from "@/modules/types";

export const lgpdModule: AppModule = {
  id: "lgpd",
  modulo: "lgpd",
  permissao: "lgpd.acessar",
  secao: "Governança do PDA",
  rotulo: "Dados Pessoais (LGPD)",
  icone: "fa-shield-halved",
  caminho: "/lgpd",
  crumb: "Governança do PDA",
  titulo: "Riscos de Dados Pessoais",
  destaqueAlerta: true,
  userStories: ["US11", "US12", "US13", "US26", "US27"],
  pagina: lazy(() => import("./LgpdPage")),
};
