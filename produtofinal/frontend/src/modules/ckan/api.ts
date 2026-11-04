import { api } from "@/shared/api/client";

export interface PerfilCkan {
  id: number;
  nome: string;
  base_url: string;
  auditoria_base_url: string | null;
  tem_token: boolean;
  auditoria_api_token_dica: string | null;
  selecionado: boolean;
  atualizado_em: string;
}

export interface PerfilCkanIn {
  nome: string;
  base_url: string;
  auditoria_base_url?: string | null;
  // ausente = mantém o token atual; "" = remove; texto = substitui
  auditoria_api_token?: string | null;
}

export const ckanApi = {
  perfis: () => api.get<PerfilCkan[]>("/ckan-config/perfis"),
  criar: (b: PerfilCkanIn) => api.post<PerfilCkan>("/ckan-config/perfis", b),
  atualizar: (id: number, b: PerfilCkanIn) => api.put<PerfilCkan>(`/ckan-config/perfis/${id}`, b),
  excluir: (id: number) => api.del<void>(`/ckan-config/perfis/${id}`),
  selecionar: (id: number) => api.post<PerfilCkan>(`/ckan-config/perfis/${id}/selecionar`),
};
