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
  atualizacao_pct: number | null; // % das bases vinculadas com prazo que estão em dia (ADR-0023)
  atualizacoes_atrasadas: number | null;
  atualizacoes_avaliadas: number; // bases vinculadas com periodicidade de prazo definido
  // Riscos LGPD (só com lgpd.acessar): recursos com possível dado pessoal aguardando revisão ou
  // confirmado; null = sem acesso ao módulo ou nenhum recurso do órgão varrido
  riscos_lgpd: number | null;
  lgpd_recursos_analisados: number;
  lgpd_aguardando_revisao: number; // achados
  lgpd_confirmados: number; // achados
  risco_lgpd_pct: number | null; // riscos_lgpd / recursos varridos
  // Índice de atenção (ADR-0030): média ponderada do risco LGPD e do atraso de atualização
  indice_atencao: "Alto" | "Médio" | "Baixo" | null;
  indice_atencao_valor: number | null; // 0 a 100
  atraso_atualizacao_pct: number | null; // componente do índice: atualizações atrasadas / avaliadas
  indice_atencao_componentes: string[]; // "Risco LGPD", "Atraso de atualização"
}

/** Pesos e faixas do índice de atenção em vigor (tela Parâmetros). */
export interface CriterioAtencao {
  peso_lgpd: number;
  peso_atualizacao: number;
  limite_medio: number;
  limite_alto: number;
}

export interface Organizacoes {
  plano: { id: number; nome: string } | null;
  hoje: string;
  formatos_abertos: string[];
  lgpd_visivel: boolean; // o usuário vê o módulo LGPD
  criterio_atencao: CriterioAtencao;
  organizacoes: Organizacao[];
}

export const organizacoesApi = {
  lista: () => api.get<Organizacoes>("/painel/organizacoes"),
};
