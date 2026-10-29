import type { StatusAchado, StatusCorrecao, StatusVarredura } from "./api";
import { ROTULO_STATUS } from "./api";

export { fmtDataHora } from "@/modules/pda/formato";

/** Data e hora (America/Sao_Paulo), para varreduras e decisões. */
export function fmtMomento(valor: string | null | undefined): string {
  if (!valor) return "—";
  const d = new Date(valor);
  return Number.isNaN(d.getTime()) ? valor : d.toLocaleString("pt-BR", {
    timeZone: "America/Sao_Paulo", day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit" });
}

/** Mesma etiqueta do protótipo (priorityTag). */
export function PrioridadeTag({ prioridade }: { prioridade: string }) {
  return <span className={`priority-tag priority-${prioridade}`}>{prioridade}</span>;
}

/** Mesmas cores do protótipo (statusBadge): Revisar âmbar, Confirmado vermelho, Falso positivo cinza. */
const CLASSE: Record<StatusAchado, string> = {
  revisar: "badge-amber", confirmado: "badge-red", falso_positivo: "badge-gray", tratado: "badge-green",
};
export function StatusAchadoBadge({ status }: { status: StatusAchado }) {
  return <span className={`badge ${CLASSE[status] ?? "badge-gray"}`}>{ROTULO_STATUS[status] ?? status}</span>;
}

const VARREDURA: Record<StatusVarredura, [string, string]> = {
  pendente: ["badge-gray", "Na fila"],
  executando: ["badge-blue", "Varrendo"],
  ok: ["badge-green", "Concluída"],
  erro: ["badge-red", "Erro"],
  ignorado: ["badge-gray", "Ignorado"],
  cancelada: ["badge-gray", "Cancelada"],
};
export function StatusVarreduraBadge({ status }: { status: StatusVarredura }) {
  const [cls, rotulo] = VARREDURA[status] ?? ["badge-gray", status];
  return <span className={`badge ${cls}`}>{rotulo}</span>;
}

const CORRECAO: Record<StatusCorrecao, [string, string]> = {
  gerando_previa: ["badge-blue", "Gerando prévia"],
  previa: ["badge-amber", "Prévia pronta"],
  publicando: ["badge-blue", "Publicando"],
  publicada: ["badge-green", "Publicada no CKAN"],
  revertendo: ["badge-blue", "Revertendo"],
  revertida: ["badge-gray", "Revertida"],
  descartada: ["badge-gray", "Descartada"],
  erro: ["badge-red", "Erro"],
};
export function StatusCorrecaoBadge({ status }: { status: StatusCorrecao }) {
  const [cls, rotulo] = CORRECAO[status] ?? ["badge-gray", status];
  return <span className={`badge ${cls}`}>{rotulo}</span>;
}
