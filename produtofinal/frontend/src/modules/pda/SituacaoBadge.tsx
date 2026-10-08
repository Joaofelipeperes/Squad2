import { classeSituacao } from "./formato";

/** Badge de situação PDA (equivalente ao statusBadge() do protótipo V1). */
export function SituacaoBadge({ situacao }: { situacao: string }) {
  return <span className={`badge ${classeSituacao(situacao)}`}>{situacao}</span>;
}
