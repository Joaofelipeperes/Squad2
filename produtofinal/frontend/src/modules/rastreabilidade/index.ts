import { lazy } from "react";
import type { AppModule } from "@/modules/types";

export const rastreabilidadeModule: AppModule = {
  id: "rastreabilidade",
  modulo: "rastreabilidade",
  permissao: "rastreabilidade.acessar",
  secao: "Inventário",
  rotulo: "Rastreabilidade",
  icone: "fa-timeline",
  caminho: "/rastreabilidade",
  crumb: "Inventário",
  titulo: "Rastreabilidade",
  userStories: ["US14", "US29"],
  pagina: lazy(() => import("./RastreabilidadePage")),
};
