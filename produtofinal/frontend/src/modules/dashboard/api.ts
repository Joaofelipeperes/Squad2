/** Contrato JSON da Visão Geral (/api/v1/painel/visao-geral). */
import { api } from "@/shared/api/client";

/** Cartões. `null` = indicador ainda não calculável (a tela mostra o motivo). */
export interface Kpis {
  orgaos_monitorados: number;
  orgaos_no_pda: number;
  bases_previstas: number;
  bases_vinculadas: number;
  bases_publicadas: number;
  bases_em_atraso: number | null; // só entre as vinculadas; null = nenhuma vinculada
  bases_prazo_vencido: number; // sem vínculo e com prazo vencido (atraso não confirmado)
  datasets_publicados: number;
  datasets_fora_do_portal: number;
  recursos_monitorados: number;
  datasets_sem_recurso: number;
  atualizacoes_em_atraso: number | null; // entre as vinculadas (ADR-0020); null = nenhuma
  possiveis_dados_pessoais: number | null;
}

export interface Contagem { rotulo: string; total: number }

export interface Alerta {
  tipo: string; // "PDA" | "Atualização" | "Inventário"
  orgao: string | null;
  item: string;
  situacao: string;
  prazo: string | null;
  destino: string; // rota da tela onde o item é tratado
}

export interface VisaoGeral {
  plano: { id: number; nome: string } | null;
  hoje: string;
  ultima_coleta: string | null;
  kpis: Kpis;
  situacoes_pda: Contagem[];
  /** Bases do PDA vigente pela periodicidade do PDA, mais "Aguardando vínculo" (sem dataset). */
  situacoes_atualizacao: Contagem[];
  atualizacao_estimada: number; // bases vinculadas cuja data veio da criação (sem last_modified)
  alertas: Alerta[]; // até 10 de cada tipo, na ordem de prioridade
  total_alertas: number;
  alertas_por_tipo: Record<string, number>;
}

export const dashboardApi = {
  visaoGeral: () => api.get<VisaoGeral>("/painel/visao-geral"),
};
