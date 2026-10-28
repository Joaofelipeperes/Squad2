/** Contrato JSON da tela Organizações (/api/v1/painel/organizacoes). */
import { api } from "@/shared/api/client";

/** Linha por órgão. Campos `null` = indicador ainda não calculável (a tela mostra o motivo). */
export interface Organizacao {
  chave: string; // id da organização (texto), ou "sigla:<SIGLA>" para sigla do PDA sem organização
  organizacao_id: number | null;
  nome: string;
  siglas: string[];
  datasets_no_portal: number;
  recursos_validos: number;
  recursos_formato_fechado: number;
  formatos_fechados: Record<string, number>; // "" = sem formato informado
  bases_previstas: number;
  bases_vinculadas: number;
  bases_publicadas: number;
  bases_em_atraso: number | null; // só entre as vinculadas; null = nenhuma base vinculada
  bases_proximas_do_prazo: number;
  atualizacao_pct: number | null; // % das bases vinculadas com prazo que estão em dia (ADR-0020)
  atualizacoes_atrasadas: number | null;
  atualizacoes_avaliadas: number; // bases vinculadas com periodicidade de prazo definido
  riscos_lgpd: number | null;
  indice_atencao: string | null;
}

export interface Organizacoes {
  plano: { id: number; nome: string } | null;
  hoje: string;
  formatos_abertos: string[];
  organizacoes: Organizacao[];
}

export const organizacoesApi = {
  lista: () => api.get<Organizacoes>("/painel/organizacoes"),
};
