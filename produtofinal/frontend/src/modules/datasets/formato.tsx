/** Formatação da tela Datasets. As funções de data e ID são as mesmas da tela do PDA. */
export { abreviarId, fmtDataHora } from "@/modules/pda/formato";

/** Badge da situação no portal (Publicado / Sem recurso / Fora do portal). */
const CLASSE: Record<string, string> = {
  "Publicado": "badge-green",
  "Sem recurso": "badge-amber",
  "Fora do portal": "badge-red",
};

export function SituacaoPortalBadge({ situacao }: { situacao: string }) {
  return <span className={`badge ${CLASSE[situacao] ?? "badge-gray"}`}>{situacao}</span>;
}
