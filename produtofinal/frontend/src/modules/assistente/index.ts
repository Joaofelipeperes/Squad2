import { lazy } from "react";
import type { AppWidget } from "@/modules/types";

/** Botão flutuante do Assistente GEDA (US28), presente em todas as telas. */
export const assistenteWidget: AppWidget = {
  id: "assistente",
  modulo: "assistente",
  permissao: "assistente.usar",
  componente: lazy(() => import("./AssistenteChat")),
};
