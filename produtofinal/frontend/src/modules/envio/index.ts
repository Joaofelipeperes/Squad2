import { lazy } from "react";
import type { AppModule } from "@/modules/types";

export const envioModule: AppModule = {
  id: "envio",
  modulo: "envio",
  permissao: "envio.acessar",
  secao: "Órgão publicador",
  rotulo: "Envio de dados",
  icone: "fa-cloud-arrow-up",
  caminho: "/envio",
  crumb: "Órgão publicador",
  titulo: "Envio de dados do órgão",
  userStories: [],
  pagina: lazy(() => import("./EnvioPage")),
};
