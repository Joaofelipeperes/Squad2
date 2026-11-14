import { classeSituacao } from "./formato";

/** Explicação das situações que não confirmam nada sobre o portal. */
export const DICA_SITUACAO: Record<string, string> = {
  "Prazo vencido": "Prazo do PDA vencido; publicação ainda não confirmada: aguardando vínculo",
  "Publicado no prazo": "Primeiro recurso válido publicado no portal até o prazo do PDA",
  "Publicado fora do prazo": "Primeiro recurso válido publicado no portal depois do prazo do PDA",
};

/** Badge de situação PDA (equivalente ao statusBadge() do protótipo V1). */
export function SituacaoBadge({ situacao }: { situacao: string }) {
  return <span className={`badge ${classeSituacao(situacao)}`} title={DICA_SITUACAO[situacao]}>{situacao}</span>;
}
