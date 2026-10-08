/** Formatação de valores da tela do PDA (sem dependência de React). */

/** "aaaa-mm-dd" → "dd/mm/aaaa" sem passar por Date (evita deslocamento de fuso). */
export function fmtData(valor: string | null | undefined): string {
  if (!valor) return "—";
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(valor);
  return m ? `${m[3]}/${m[2]}/${m[1]}` : valor;
}

/** Data-hora ISO 8601 → "dd/mm/aaaa" no fuso do Estado. */
export function fmtDataHora(valor: string | null | undefined): string {
  if (!valor) return "—";
  const d = new Date(valor);
  return Number.isNaN(d.getTime()) ? valor : d.toLocaleDateString("pt-BR", { timeZone: "America/Sao_Paulo" });
}

/** ID do CKAN abreviado para a tabela (8 primeiros caracteres + "…"). */
export function abreviarId(id: string): string {
  return id.length > 8 ? `${id.slice(0, 8)}…` : id;
}

/** Singular/plural simples: plural(1, "base prevista", "bases previstas"). */
export function plural(n: number, singular: string, pluralForma: string): string {
  return `${n} ${n === 1 ? singular : pluralForma}`;
}

/** Classe do badge por situação — mesmo mapa do statusBadge() do protótipo V1. */
const CLASSE_SITUACAO: Record<string, string> = {
  "Publicado": "badge-green",
  "Em dia": "badge-green",
  "Em atraso": "badge-red",
  "Próximo do prazo": "badge-amber",
  "Sem recurso": "badge-amber",
  "Não publicado": "badge-gray",
};

export const classeSituacao = (situacao: string) => CLASSE_SITUACAO[situacao] ?? "badge-gray";
