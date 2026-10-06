import { api } from "@/shared/api/client";

export interface CampoSpec {
  name: "base_url" | "model" | "api_key";
  label: string;
  required: boolean;
  secret: boolean;
  placeholder: string | null;
  help: string | null;
}
export interface TipoProvedor {
  tipo: string;
  rotulo: string;
  descricao: string;
  url_padrao: string | null;
  exige_chave: boolean;
  local_por_padrao: boolean;
  modelos_sugeridos: string[];
  campos: CampoSpec[];
}
export interface PerfilIA {
  id: number;
  nome: string;
  tipo: string;
  modelo: string;
  base_url: string | null;
  tem_chave: boolean;
  api_key_dica: string | null;
  execucao_local: boolean;
  temperatura: number;
  max_tokens: number;
  timeout_s: number;
  ativo: boolean;
  atualizado_em: string;
}
export type PerfilIn = Omit<PerfilIA, "id" | "tem_chave" | "api_key_dica" | "atualizado_em"> & {
  api_key?: string | null;
};
export interface TarefaIA {
  tarefa: string;
  rotulo: string;
  descricao: string;
  sensivel: boolean;
  user_story: string;
  perfil_id: number | null;
  perfil_fallback_id: number | null;
  somente_local: boolean;
}
export interface TesteConexao { ok: boolean; mensagem: string; latencia_ms: number | null; modelos: string[] }
export interface UsoIA {
  momento: string; tarefa: string; perfil_nome: string; modelo: string; sucesso: boolean;
  usou_fallback: boolean; latencia_ms: number | null; tokens_entrada: number | null;
  tokens_saida: number | null; erro: string | null;
}

export const iaApi = {
  tipos: () => api.get<TipoProvedor[]>("/ia/tipos-provedor"),
  perfis: () => api.get<PerfilIA[]>("/ia/perfis"),
  criar: (b: PerfilIn) => api.post<PerfilIA>("/ia/perfis", b),
  atualizar: (id: number, b: PerfilIn) => api.put<PerfilIA>(`/ia/perfis/${id}`, b),
  excluir: (id: number) => api.del<void>(`/ia/perfis/${id}`),
  testarConexao: (b: { tipo: string; modelo?: string; base_url?: string | null; api_key?: string | null; perfil_id?: number }) =>
    api.post<TesteConexao>("/ia/testar-conexao", b),
  testarPerfil: (id: number) => api.post<TesteConexao>(`/ia/perfis/${id}/testar`),
  tarefas: () => api.get<TarefaIA[]>("/ia/tarefas"),
  vincular: (tarefa: string, b: { perfil_id: number | null; perfil_fallback_id: number | null }) =>
    api.put<TarefaIA[]>(`/ia/tarefas/${tarefa}`, b),
  uso: () => api.get<UsoIA[]>("/ia/uso?limite=20"),
  playground: (b: { tarefa: string; mensagem: string }) =>
    api.post<{ texto: string; perfil: string; modelo: string; latencia_ms: number | null; usou_fallback: boolean }>(
      "/ia/playground", b),
};
