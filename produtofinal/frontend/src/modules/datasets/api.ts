/**
 * Contrato JSON da tela Datasets (/api/v1/inventario/datasets) — tipos e chamadas.
 * Datas-hora em ISO 8601 (UTC).
 */
import { api } from "@/shared/api/client";

export interface Opcao { valor: string; rotulo: string }

/** Linha da tela. `situacao` é a situação no PORTAL (não a do PDA). */
export interface DatasetLinha {
  id: number;
  id_ckan: string | null; // ID do dataset no CKAN (o vínculo com o portal)
  name: string;
  titulo: string;
  organizacao_id: number | null;
  orgao_nome: string | null;
  recursos_validos: number;
  formatos: string[];
  ultima_atualizacao: string | null;
  ultima_atualizacao_estimada: boolean;
  metadata_created: string | null; // criação do dataset no CKAN (ordem padrão: mais recente primeiro)
  metadata_modified: string | null;
  situacao: string;
  tipo_base: string | null; // "Prevista no PDA" | "Espontânea" (ADR-0026); null = fora do portal sem vínculo
}

export interface Recurso {
  id: number;
  id_ckan: string | null;
  nome: string | null;
  formato: string | null;
  url: string | null;
  created: string | null;
  last_modified: string | null;
  eh_dicionario_dados: boolean;
}

export interface DatasetDetalhe extends DatasetLinha {
  descricao: string | null;
  periodicidade_declarada: string | null;
  licenca: string | null;
  recursos: Recurso[];
  recursos_removidos: number;
}

export interface DatasetsLista {
  total: number;
  opcoes: { orgaos: Opcao[]; formatos: string[]; situacoes: string[]; tipos_base: string[] };
  datasets: DatasetLinha[];
}

export interface FiltrosDatasets { busca: string; orgao: string; formato: string; situacao: string; tipo_base: string }

export const FILTROS_VAZIOS: FiltrosDatasets = { busca: "", orgao: "", formato: "", situacao: "", tipo_base: "" };

/** Base prevista do PDA vinculada ao dataset (subconjunto de BaseOut do módulo pda). */
export interface BaseVinculada {
  id: number;
  plano_nome: string;
  nome_previsto: string;
  prazo_abertura: string | null;
  periodicidade: string;
  situacao: string;
}

function consulta(f: FiltrosDatasets): string {
  const qs = new URLSearchParams();
  (Object.keys(f) as (keyof FiltrosDatasets)[]).forEach((k) => {
    if (f[k].trim()) qs.set(k, f[k].trim());
  });
  const s = qs.toString();
  return s ? `/inventario/datasets?${s}` : "/inventario/datasets";
}

export const datasetsApi = {
  lista: (f: FiltrosDatasets) => api.get<DatasetsLista>(consulta(f)),
  detalhe: (id: number) => api.get<DatasetDetalhe>(`/inventario/datasets/${id}`),
  basesPda: (id: number) => api.get<BaseVinculada[]>(`/pda/datasets/${id}/bases`),
};
