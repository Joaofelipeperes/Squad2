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

/** Badge do tipo de base (ADR-0026): Prevista no PDA × Espontânea. Usado também em Atualizações. */
export function TipoBaseBadge({ tipo }: { tipo: string | null }) {
  if (!tipo) return <span className="cell-muted" title="Fora do portal e sem vínculo com o PDA vigente">—</span>;
  return <span className={`badge ${tipo === "Espontânea" ? "badge-amber" : "badge-blue"}`}>{tipo}</span>;
}
