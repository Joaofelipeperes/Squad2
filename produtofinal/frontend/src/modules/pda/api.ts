/**
 * Contrato JSON do módulo `pda` (/api/v1/pda) — tipos e chamadas.
 * Datas chegam como "aaaa-mm-dd"; data-hora em ISO 8601. Formatação em formato.ts.
 */
import { api } from "@/shared/api/client";

/** PDA cadastrado (ex.: "PDA 2025-2027"). Só um é vigente por vez. */
export interface PlanoPda {
  id: number;
  nome: string;
  vigencia_inicio: string | null;
  vigencia_fim: string | null;
  vigente: boolean;
  arquivo_nome: string | null;
  importado_por: string | null;
  importado_em: string;
  total_bases: number;
  vinculos_resolvidos: number;
  vinculos_pendentes: number;
}

export interface LinhaIgnorada { linha: number; motivo: string }

/** Resposta do POST /pda/planos (PBI-12). */
export interface ImportacaoResumo {
  plano: PlanoPda;
  bases_importadas: number;
  linhas_ignoradas: LinhaIgnorada[];
  vinculos_resolvidos: number;
  vinculos_pendentes: number;
  sem_vinculo: number;
  orgaos_sem_correspondencia: string[];
  tem_coluna_prazo: boolean;
  tem_coluna_portal: boolean;
  colunas_opcionais_ausentes: string[];
}

export interface VinculosResultado { vinculos_resolvidos: number; vinculos_pendentes: number }

export interface Opcao { valor: string; rotulo: string }

export type Vinculo = "resolvido" | "pendente" | "sem_vinculo";
export type FlagPrazo = "vencido" | "proximo" | "";

/** Base prevista no PDA com a situação calculada pelo backend (PBI-19). */
export interface BasePda {
  id: number;
  plano_id: number;
  plano_nome: string;
  orgao_sigla: string;
  orgao_chave: string;
  orgao_nome: string | null;
  nome_previsto: string;
  descricao: string | null;
  unidade_responsavel: string | null;
  periodicidade: string;
  periodicidade_original: string | null;
  politicas_publicas: string | null;
  possui_conteudo_sigiloso: boolean | null;
  prazo_abertura: string | null;
  vinculo: Vinculo;
  dataset_id: number | null;
  dataset_id_ckan: string | null; // ID do dataset no CKAN (link do portal)
  dataset_name: string | null;
  dataset_titulo: string | null;
  dataset_name_planilha: string | null;
  dataset_ativo: boolean | null;
  data_publicacao: string | null;
  recursos_validos: number;
  formatos: string[];
  ultima_atualizacao: string | null;
  ultima_atualizacao_estimada: boolean;
  situacao: string;
  flag_prazo: FlagPrazo;
  classificacao: string;
}

export interface BasesPda {
  plano: PlanoPda | null;
  hoje: string;
  janela_alerta_dias: number;
  total_previstas: number;
  opcoes: { orgaos: Opcao[]; periodicidades: string[]; anos: number[] };
  bases: BasePda[];
}

/** Filtros da lista (PBI-20/21). Vazio = sem filtro. `prazo`: "vencido" | "proximo". */
export interface FiltrosPda {
  orgao: string;
  situacao: string;
  periodicidade: string;
  ano: string;
  prazo: string;
}

export const FILTROS_VAZIOS: FiltrosPda = { orgao: "", situacao: "", periodicidade: "", ano: "", prazo: "" };

/** Rótulos de situação na ordem do filtro do protótipo. */
export const SITUACOES = [
  "Publicado", "Em dia", "Em atraso", "Prazo vencido", "Próximo do prazo", "Não publicado", "Sem recurso",
] as const;

/** Criação manual (POST /pda/planos/manual) e edição (PUT /pda/planos/{id}) de um PDA. */
export interface PlanoEntrada {
  nome: string;
  vigencia_inicio: string | null;
  vigencia_fim: string | null;
  definir_vigente?: boolean; // só na criação
}

/** Inclusão (POST /pda/planos/{id}/bases) e edição (PUT /pda/bases/{id}) de uma base. */
export interface BaseEntrada {
  orgao_sigla: string;
  organizacao_id: number | null; // vazio = identificar pela sigla
  nome_previsto: string;
  descricao: string | null;
  unidade_responsavel: string | null;
  periodicidade: string | null;
  prazo_abertura: string | null;
  politicas_publicas: string | null;
  possui_conteudo_sigiloso: boolean | null;
  dataset_id: number | null; // escolhido na busca; tem precedência sobre dataset_link
  dataset_link: string | null; // link do portal ou name; serve só para achar o ID
}

/** Opções do formulário de base: organizações do portal (valor = id) e periodicidades. */
export interface FormularioPda { organizacoes: Opcao[]; periodicidades: string[] }

/** Dataset do inventário encontrado pela busca do formulário de base (valor = ID CKAN). */
export interface DatasetOpcao {
  id: number;
  id_ckan: string | null;
  name: string;
  titulo: string;
  organizacao_id: number | null;
  orgao_nome: string | null;
  ativo_no_portal: boolean;
}

/** Limite de tamanho do arquivo aceito pelo backend (413 acima disso). */
export const TAMANHO_MAX_ARQUIVO = 5 * 1024 * 1024;

function consultaBases(planoId: number | null, f: FiltrosPda): string {
  const qs = new URLSearchParams();
  if (planoId != null) qs.set("plano_id", String(planoId));
  (Object.keys(f) as (keyof FiltrosPda)[]).forEach((k) => {
    if (f[k]) qs.set(k, f[k]);
  });
  const s = qs.toString();
  return s ? `/pda/bases?${s}` : "/pda/bases";
}

export const pdaApi = {
  planos: () => api.get<PlanoPda[]>("/pda/planos"),
  importar: (form: FormData) => api.upload<ImportacaoResumo>("/pda/planos", form),
  criarPlano: (dados: PlanoEntrada) => api.post<PlanoPda>("/pda/planos/manual", dados),
  atualizarPlano: (id: number, dados: PlanoEntrada) => api.put<PlanoPda>(`/pda/planos/${id}`, dados),
  formulario: () => api.get<FormularioPda>("/pda/formulario"),
  buscarDatasets: (busca: string) =>
    api.get<DatasetOpcao[]>(`/pda/formulario/datasets?${new URLSearchParams({ busca })}`),
  criarBase: (planoId: number, dados: BaseEntrada) => api.post<BasePda>(`/pda/planos/${planoId}/bases`, dados),
  atualizarBase: (id: number, dados: BaseEntrada) => api.put<BasePda>(`/pda/bases/${id}`, dados),
  excluirBase: (id: number) => api.del<void>(`/pda/bases/${id}`),
  definirVigente: (id: number) => api.put<PlanoPda>(`/pda/planos/${id}/vigente`),
  excluir: (id: number) => api.del<void>(`/pda/planos/${id}`),
  vincular: (id: number) => api.post<VinculosResultado>(`/pda/planos/${id}/vincular`),
  bases: (planoId: number | null, f: FiltrosPda) => api.get<BasesPda>(consultaBases(planoId, f)),
  base: (id: number) => api.get<BasePda>(`/pda/bases/${id}`),
};
