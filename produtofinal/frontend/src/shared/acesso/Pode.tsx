import type { ReactNode } from "react";
import { useAuth } from "@/app/auth/AuthContext";
import type { Permissao } from "@/shared/acesso/permissoes.gen";

/**
 * Renderiza o conteúdo só se o usuário tiver a permissão (ou TODAS, se for lista).
 *   <Pode permissao="inventario.coletar"><button>Atualizar dados</button></Pode>
 *
 * Esconder o botão é conveniência de interface: o backend verifica de novo em toda requisição.
 */
export function Pode({ permissao, children, senao = null }: {
  permissao: Permissao | Permissao[];
  children: ReactNode;
  senao?: ReactNode;
}) {
  const { pode } = useAuth();
  const lista = Array.isArray(permissao) ? permissao : [permissao];
  return <>{lista.every(pode) ? children : senao}</>;
}
