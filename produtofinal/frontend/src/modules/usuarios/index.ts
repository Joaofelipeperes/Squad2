import { lazy } from "react";
import type { AppModule } from "@/modules/types";

export const usuariosModule: AppModule = {
  id: "usuarios",
  modulo: "acesso",
  permissao: "acesso.gerenciar_usuarios",
  secao: "Administração",
  rotulo: "Usuários e papéis",
  icone: "fa-users",
  caminho: "/admin/usuarios",
  crumb: "Administração",
  titulo: "Usuários e papéis",
  userStories: ["US24"],
  pagina: lazy(() => import("./UsuariosPage")),
};
