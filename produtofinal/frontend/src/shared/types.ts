import type { Permissao } from "@/shared/acesso/permissoes.gen";

export interface PapelResumo { id: number; codigo: string; nome: string }
export interface OrgaoResumo { ckan_id: string; titulo: string }

export interface Usuario {
  id: number;
  email: string;
  nome: string;
  ativo: boolean;
  orgao: OrgaoResumo | null;
  papeis: PapelResumo[];
  ultimo_acesso: string | null;
}

/** Resposta de /acesso/me e do login. */
export interface Sessao {
  usuario: Usuario;
  permissoes: Permissao[];
}
