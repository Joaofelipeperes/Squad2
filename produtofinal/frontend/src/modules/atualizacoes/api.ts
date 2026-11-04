/**
 * Contrato JSON da tela Monitoramento de Atualizações (/api/v1/atualizacoes/datasets).
 * Datas-hora em ISO 8601 (UTC); `prazo_esperado` é só data.
 */
import { api } from "@/shared/api/client";

export interface Opcao { valor: string; rotulo: string }

export interface AtualizacaoLinha {
  base_id: number;
  dataset_id: number;
  dataset_titulo: string;
  dataset_name: string | null;
  orgao_chave: string;
  orgao_sigla: string;
  orgao_nome: string | null;
  periodicidade: string;
  ultima_atualizacao: string | null; // last_modified do recurso, nunca metadata_modified
  ultima_atualizacao_estimada: boolean;
  dias_desde_atualizacao: number | null;
  prazo_esperado: string | null;
  situacao: string;
}

export interface AtualizacoesLista {
  plano_nome: string | null;
  hoje: string;
  total: number;
  resumo: { atualizados: number; atrasados: number; proximos_do_vencimento: number; sem_informacao: number };
  opcoes: { orgaos: Opcao[]; periodicidades: string[]; situacoes: string[] };
  datasets: AtualizacaoLinha[];
}

export interface FiltrosAtualizacoes { dataset: string; orgao: string; periodicidade: string; situacao: string }

export const FILTROS_VAZIOS: FiltrosAtualizacoes = { dataset: "", orgao: "", periodicidade: "", situacao: "" };

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
