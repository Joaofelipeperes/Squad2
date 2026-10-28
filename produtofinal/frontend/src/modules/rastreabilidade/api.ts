/**
 * Contrato JSON da tela Rastreabilidade (/api/v1/rastreabilidade/eventos) — tipos e chamadas.
 * Datas-hora em ISO 8601 (UTC).
 */
import { api } from "@/shared/api/client";

export interface Opcao { valor: string; rotulo: string }

/** Item do evento: campo com valor anterior → novo, ou uma contagem (só `novo`). */
export interface Detalhe {
  escopo: string | null;
  recurso: string | null;
  situacao: string | null; // recurso: added | changed | removed
  campo: string;
  anterior: string | null;
  novo: string | null;
}

export interface Evento {
  id: number;
  ocorrido_em: string;
  tipo: string;
  tipo_rotulo: string;
  origem: string; // auditoria_ckan | comparacao_coletas (cadastro do órgão) | atividade_nativa (fora da auditoria)
  dataset_id: string | null; // vazio em evento do cadastro do órgão
  dataset_titulo: string | null;
  organizacao_id: string | null;
  orgao_nome: string | null;
  recurso_id: string | null;
  recurso_nome: string | null;
  usuario: string | null;
  resumo: string;
  detalhes: Detalhe[];
  tem_diff: boolean; // há diff linha a linha no CKAN (buscado sob demanda)
}

export interface Sincronizacao {
  id: number;
  iniciada_em: string;
  finalizada_em: string | null;
  status: string; // executando | ok | erro | ignorada
  datasets_consultados: number;
  datasets_sem_permissao: number;
  datasets_nao_encontrados: number;
  orgaos_consultados: number;
  eventos_novos: number;
  erro: string | null;
}

export interface EventosLista {
  total: number;
  exibidos: number;
  opcoes: { tipos: Opcao[]; orgaos: Opcao[] };
  sincronizacao: Sincronizacao | null;
  eventos: Evento[];
}

export interface DiffCampo { campo: string; anterior: string | null; novo: string | null }

export interface DiffLinha {
  chave: string;     // ex.: "id=12" ou "linha=5"
  situacao: string;  // incluída | alterada | removida
  campos: DiffCampo[];
}

/** Diff linha a linha lido do CKAN na hora (a solução não grava esses valores). */
export interface Diff {
  evento_id: number;
  recurso_nome: string | null;
  arquivo_anterior: string | null;
  arquivo_novo: string | null;
  versao_anterior: number | null;
  versao_nova: number | null;
  colunas_chave: string[];
  total_linhas: number;
  linhas: DiffLinha[];
}

/** `desde`/`ate` no formato do input date (aaaa-mm-dd), interpretados no horário de Brasília. */
export interface FiltrosEventos {
  busca: string; tipo: string; orgao: string; desde: string; ate: string; ordem: "recentes" | "antigos";
}

export const FILTROS_VAZIOS: FiltrosEventos = { busca: "", tipo: "", orgao: "", desde: "", ate: "", ordem: "recentes" };

/** Sem horário de verão desde 2019: o offset de Brasília é fixo (-03:00). */
const inicioDoDia = (d: string) => `${d}T00:00:00-03:00`;
const fimDoDia = (d: string) => `${d}T23:59:59.999-03:00`;

function consulta(f: FiltrosEventos): string {
  const qs = new URLSearchParams();
  if (f.busca.trim()) qs.set("busca", f.busca.trim());
  if (f.tipo) qs.set("tipo", f.tipo);
  if (f.orgao) qs.set("orgao", f.orgao);
  if (f.desde) qs.set("desde", inicioDoDia(f.desde));
  if (f.ate) qs.set("ate", fimDoDia(f.ate));
  if (f.ordem !== "recentes") qs.set("ordem", f.ordem);
  const s = qs.toString();
  return s ? `/rastreabilidade/eventos?${s}` : "/rastreabilidade/eventos";
}

export const rastreabilidadeApi = {
  eventos: (f: FiltrosEventos) => api.get<EventosLista>(consulta(f)),
  diff: (eventoId: number) => api.get<Diff>(`/rastreabilidade/eventos/${eventoId}/diff`),
};
