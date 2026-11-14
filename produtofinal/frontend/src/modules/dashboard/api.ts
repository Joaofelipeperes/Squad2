/** Contrato JSON da Visão Geral (/api/v1/painel/visao-geral). */
import { api } from "@/shared/api/client";

/** Cartões. `null` = indicador ainda não calculável (a tela mostra o motivo). */
export interface Kpis {
  orgaos_monitorados: number;
  orgaos_no_pda: number;
  bases_previstas: number;
  bases_vinculadas: number;
  bases_publicadas: number; // no prazo + fora do prazo
  bases_publicadas_fora_do_prazo: number; // 1º recurso publicado depois do prazo do plano (ADR-0038)
  bases_em_atraso: number | null; // só entre as vinculadas; null = nenhuma vinculada
  bases_prazo_vencido: number; // sem vínculo e com prazo vencido (atraso não confirmado)
  datasets_publicados: number;
  datasets_fora_do_portal: number;
  recursos_monitorados: number;
  datasets_sem_recurso: number;
  atualizacoes_em_atraso: number | null; // entre todos os datasets publicados (ADR-0037); null = nenhum
  periodicidade_nao_informada: number | null; // campo "Atualização" do CKAN vazio ou inválido
  possiveis_dados_pessoais: number | null; // achados aguardando revisão; null sem lgpd.acessar
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

/** Bases espontâneas (ADR-0026): datasets ativos no portal sem base do PDA vigente vinculada. */
export interface Espontaneas {
  datasets_no_portal: number;
  no_pda: number;
  espontaneas: number;
  por_orgao: Contagem[]; // até 10 órgãos e "Outros órgãos (N)"
}

/** Resumo do módulo LGPD (só contagens). */
export interface DadosPessoais {
  recursos_analisados: number;
  recursos_com_achados: number;
  aguardando_revisao: number;
  criticos: number;
  por_tipo: Contagem[];
  por_status: Contagem[];
}

export interface VisaoGeral {
  plano: { id: number; nome: string } | null;
  hoje: string;
  ultima_coleta: string | null;
  kpis: Kpis;
  situacoes_pda: Contagem[];
  /** Todos os datasets publicados pela periodicidade do campo "Atualização" do CKAN (ADR-0037). */
  situacoes_atualizacao: Contagem[];
  atualizacao_por_tipo: Contagem[]; // datasets publicados: "Prevista no PDA" × "Espontânea"
  atualizacao_estimada: number; // datasets cuja data veio da criação do recurso (sem last_modified)
  alertas: Alerta[]; // até 10 de cada tipo, na ordem de prioridade
  total_alertas: number;
  alertas_por_tipo: Record<string, number>;
  espontaneas: Espontaneas;
  dados_pessoais: DadosPessoais | null; // null = usuário sem lgpd.acessar
}

export const dashboardApi = {
  visaoGeral: () => api.get<VisaoGeral>("/painel/visao-geral"),
};
