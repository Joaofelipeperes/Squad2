/** Contrato JSON da tela Riscos de Dados Pessoais (/api/v1/lgpd). Datas-hora em ISO 8601 (UTC). */
import { api, tokenStore } from "@/shared/api/client";

export interface Opcao { valor: string; rotulo: string }

export interface Kpis {
  recursos_analisados: number;
  recursos_com_achados: number;
  alertas_criticos: number;
  alertas_para_revisao: number;
}

export type StatusAchado = "revisar" | "confirmado" | "falso_positivo" | "tratado";

export interface Achado {
  id: number;
  prioridade: "Alta" | "Média" | "Baixa";
  orgao_id: number | null;
  orgao_sigla: string | null;
  orgao_nome: string | null;
  dataset_id: number;
  dataset_titulo: string;
  recurso_id: number;
  recurso_nome: string | null;
  tipo: string;
  tipo_rotulo: string;
  coluna: string;
  linha: number | null;
  ocorrencias: number;
  confianca: number;
  metodo: "regra" | "ia";
  status: StatusAchado;
  atualizado_em: string | null;
}

export interface Decisao { decisao: StatusAchado; justificativa: string | null; usuario: string; momento: string }

export interface AchadoDetalhe extends Achado {
  explicacao: string | null;
  recurso_url: string | null;
  recurso_formato: string | null;
  decisoes: Decisao[];
}

export interface AchadosLista {
  kpis: Kpis;
  opcoes: { prioridades: string[]; tipos: Opcao[]; orgaos: Opcao[]; status: Opcao[] };
  total: number;
  achados: Achado[];
}

export interface FiltrosLgpd { prioridade: string; tipo: string; orgao: string; status: string }
export const FILTROS_VAZIOS: FiltrosLgpd = { prioridade: "", tipo: "", orgao: "", status: "" };

export type StatusVarredura = "pendente" | "executando" | "ok" | "erro" | "ignorado" | "cancelada";

export interface Varredura {
  id: number;
  recurso_id: number;
  recurso_nome: string | null;
  dataset_titulo: string | null;
  status: StatusVarredura;
  origem: "manual" | "agendada";
  solicitada_por: string | null;
  solicitada_em: string;
  iniciada_em: string | null;
  finalizada_em: string | null;
  linhas_analisadas: number;
  chamadas_ia: number;
  achados: number;
  modelo: string | null;
  aviso: string | null;
  erro: string | null;
}

export type EscopoVarredura = "pendentes" | "dataset" | "recurso";

// ------------------------------------------------------------------ anonimização (US26)
export type StatusCorrecao =
  | "gerando_previa" | "previa" | "publicando" | "publicada" | "revertendo" | "revertida"
  | "descartada" | "erro";
export type Operador = "mascara_cpf" | "substituir" | "mascarar" | "hash" | "remover";
export type Alcance = "detectados" | "coluna";

export interface CorrecaoItem {
  achado_id: number;
  tipo: string;
  tipo_rotulo: string;
  coluna: string;
  operador: Operador;
  operador_rotulo: string;
  alcance: Alcance;
  ocorrencias: number;
  alteradas: number;
  aviso: string | null;
  exemplos: { linha: number; valor: string }[];
}

export interface Correcao {
  id: number;
  recurso_id: number;
  recurso_nome: string | null;
  dataset_titulo: string | null;
  recurso_url_type: string | null;
  status: StatusCorrecao;
  solicitada_por: string | null;
  solicitada_em: string | null;
  celulas_alteradas: number;
  nome_arquivo: string | null;
  aprovado_por: string | null;
  aprovado_em: string | null;
  justificativa: string | null;
  publicada_em: string | null;
  revertida_por: string | null;
  revertida_em: string | null;
  motivo_reversao: string | null;
  erro: string | null;
  itens: CorrecaoItem[];
}

export interface CorrecoesLista {
  escrita_habilitada: boolean;
  operadores: Opcao[];
  alcances: Opcao[];
  correcoes: Correcao[];
}

export const EM_ANDAMENTO: StatusCorrecao[] = ["gerando_previa", "publicando", "revertendo"];

/** Padrão por tipo: CPF segue a regra da GEDA (oculta 3 primeiros e 2 últimos dígitos). */
export const operadorPadrao = (tipo: string): Operador => (tipo === "cpf" ? "mascara_cpf" : "substituir");

async function baixarPrevia(id: number, nome: string) {
  const token = tokenStore.get();
  const resp = await fetch(`/api/v1/lgpd/correcoes/${id}/arquivo-previa`,
    { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!resp.ok) throw new Error(`Erro ${resp.status} ao baixar a prévia`);
  const url = URL.createObjectURL(await resp.blob());
  const a = Object.assign(document.createElement("a"), { href: url, download: `previa_anonimizada_${nome}` });
  a.click();
  URL.revokeObjectURL(url);
}

const qs = (f: FiltrosLgpd) => {
  const p = new URLSearchParams();
  Object.entries(f).forEach(([k, v]) => { if (v) p.set(k, v); });
  const s = p.toString();
  return s ? `?${s}` : "";
};

export const lgpdApi = {
  achados: (f: FiltrosLgpd) => api.get<AchadosLista>(`/lgpd/achados${qs(f)}`),
  achado: (id: number) => api.get<AchadoDetalhe>(`/lgpd/achados/${id}`),
  decidir: (id: number, decisao: StatusAchado, justificativa: string | null) =>
    api.post<AchadoDetalhe>(`/lgpd/achados/${id}/decisao`, { decisao, justificativa }),
  varreduras: () => api.get<{ em_andamento: number; varreduras: Varredura[] }>("/lgpd/varreduras?limite=15"),
  cancelarFila: () => api.post<{ canceladas: number }>("/lgpd/varreduras/cancelar"),
  varrer: (escopo: EscopoVarredura, id?: number) =>
    api.post<{ criadas: number; ja_na_fila: number; varreduras: Varredura[] }>("/lgpd/varreduras", { escopo, id }),
};

export const correcoesApi = {
  lista: () => api.get<CorrecoesLista>("/lgpd/correcoes?limite=10"),
  obter: (id: number) => api.get<Correcao>(`/lgpd/correcoes/${id}`),
  gerarPrevia: (recurso_id: number, itens: { achado_id: number; operador: Operador; alcance: Alcance }[]) =>
    api.post<Correcao>("/lgpd/correcoes", { recurso_id, itens }),
  aprovar: (id: number, justificativa: string | null) =>
    api.post<Correcao>(`/lgpd/correcoes/${id}/aprovar`, { justificativa }),
  descartar: (id: number) => api.post<Correcao>(`/lgpd/correcoes/${id}/descartar`),
  reverter: (id: number, motivo: string) => api.post<Correcao>(`/lgpd/correcoes/${id}/reverter`, { motivo }),
  baixarPrevia,
};

export const ROTULO_STATUS: Record<StatusAchado, string> = {
  revisar: "Revisar", confirmado: "Confirmado", falso_positivo: "Falso positivo", tratado: "Tratado",
};
