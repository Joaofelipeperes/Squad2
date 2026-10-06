import { api } from "@/shared/api/client";
import type { OrgaoResumo, Usuario } from "@/shared/types";

export interface PermissaoCatalogo { codigo: string; rotulo: string; descricao: string; sensivel: boolean }
export interface GrupoCatalogo { modulo: string; permissoes: PermissaoCatalogo[] }
export interface Papel {
  id: number; codigo: string; nome: string; descricao: string | null; sistema: boolean;
  exige_orgao: boolean; todas: boolean; permissoes: string[]; total_usuarios: number;
}
export interface UsuarioIn {
  email: string; nome: string; senha?: string | null; ativo: boolean;
  orgao_id: string | null; papel_ids: number[];
}
export interface PapelIn {
  codigo: string; nome: string; descricao: string | null; exige_orgao: boolean; permissoes: string[];
}

export const acessoApi = {
  usuarios: () => api.get<Usuario[]>("/acesso/usuarios"),
  criarUsuario: (b: UsuarioIn) => api.post<Usuario>("/acesso/usuarios", b),
  atualizarUsuario: (id: number, b: UsuarioIn) => api.put<Usuario>(`/acesso/usuarios/${id}`, b),
  papeis: () => api.get<Papel[]>("/acesso/papeis"),
  criarPapel: (b: PapelIn) => api.post<Papel>("/acesso/papeis", b),
  atualizarPapel: (id: number, b: PapelIn) => api.put<Papel>(`/acesso/papeis/${id}`, b),
  excluirPapel: (id: number) => api.del<void>(`/acesso/papeis/${id}`),
  catalogo: () => api.get<GrupoCatalogo[]>("/acesso/catalogo"),
  orgaos: () => api.get<OrgaoResumo[]>("/acesso/orgaos"),
};

/** Nome legível dos módulos no agrupamento de permissões. */
export const NOME_MODULO: Record<string, string> = {
  painel: "Visão geral", inventario: "Inventário", pda: "Monitoramento do PDA",
  atualizacoes: "Atualizações", rastreabilidade: "Rastreabilidade", lgpd: "Dados pessoais (LGPD)",
  metadados: "Metadados", relatorios: "Relatórios", assistente: "Assistente GEDA",
  envio: "Órgão publicador", parametros: "Parâmetros", ia: "Modelos de IA", acesso: "Usuários e papéis",
};
