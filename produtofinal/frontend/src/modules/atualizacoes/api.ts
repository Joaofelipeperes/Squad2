/**
 * Contrato JSON da tela Monitoramento de Atualizações (/api/v1/atualizacoes/datasets).
 * Datas-hora em ISO 8601 (UTC); `prazo_esperado` é só data.
 */
import { api } from "@/shared/api/client";

export interface Opcao { valor: string; rotulo: string }

/** Dataset publicado no portal (previsto no PDA ou espontâneo) com a situação de atualização (ADR-0037). */
export interface AtualizacaoLinha {
  dataset_id: number;
  dataset_titulo: string;
  dataset_name: string | null;
  orgao_chave: string;
  orgao_sigla: string;
  orgao_nome: string | null;
  tipo_base: string; // "Prevista no PDA" | "Espontânea"
  periodicidade_declarada: string | null; // campo "Atualização" do CKAN, como o órgão preencheu
  periodicidade: string; // valor do domínio, "Sem atualização periódica" ou "Periodicidade não informada"
  ultima_atualizacao: string | null; // last_modified do recurso, nunca metadata_modified
  ultima_atualizacao_estimada: boolean;
  dias_desde_atualizacao: number | null;
  prazo_esperado: string | null;
  situacao: string;
}

export interface ResumoAtualizacoes {
  atualizados: number;
  atrasados: number;
  proximos_do_vencimento: number;
  sem_atualizacao_periodica: number; // declarado "Não possui atualização periódica" (válido)
  periodicidade_nao_informada: number; // campo "Atualização" vazio ou inválido (não conforme)
  sem_data: number; // periodicidade válida, sem recurso válido com data
  previstas_no_pda: number;
  espontaneas: number;
}

export interface AtualizacoesLista {
  plano_nome: string | null; // PDA vigente que define o tipo de base
  hoje: string;
  total: number;
  resumo: ResumoAtualizacoes;
  opcoes: { orgaos: Opcao[]; periodicidades: string[]; situacoes: string[]; tipos_base: string[] };
  datasets: AtualizacaoLinha[];
}

export interface FiltrosAtualizacoes {
  dataset: string; orgao: string; periodicidade: string; situacao: string; tipo_base: string;
}

export const FILTROS_VAZIOS: FiltrosAtualizacoes = {
  dataset: "", orgao: "", periodicidade: "", situacao: "", tipo_base: "",
};

function consulta(f: FiltrosAtualizacoes): string {
  const qs = new URLSearchParams();
  (Object.keys(f) as (keyof FiltrosAtualizacoes)[]).forEach((k) => {
    if (f[k].trim()) qs.set(k, f[k].trim());
  });
  const s = qs.toString();
  return s ? `/atualizacoes/datasets?${s}` : "/atualizacoes/datasets";
}

export const atualizacoesApi = {
  lista: (f: FiltrosAtualizacoes) => api.get<AtualizacoesLista>(consulta(f)),
};
