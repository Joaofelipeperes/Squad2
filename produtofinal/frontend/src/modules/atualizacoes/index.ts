import { lazy } from "react";
import type { AppModule } from "@/modules/types";

export const atualizacoesModule: AppModule = {
  id: "atualizacoes",
  modulo: "atualizacoes",
  permissao: "atualizacoes.acessar",
  secao: "Governança do PDA",
  rotulo: "Atualizações",
  icone: "fa-rotate",
  caminho: "/atualizacoes",
  crumb: "Governança do PDA",
  titulo: "Monitoramento de Atualizações",
  userStories: ["US9", "US10"],
  pagina: lazy(() => import("./AtualizacoesPage")),
};
