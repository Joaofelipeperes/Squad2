import type { KeyboardEvent } from "react";
import type { CorrecoesLista } from "./api";
import { StatusCorrecaoBadge, fmtMomento } from "./formato";

/** Últimas anonimizações (US26) — abre a prévia, a publicação ou a reversão de cada uma. */
export function CorrecoesPainel({ dados, onAbrir }: { dados: CorrecoesLista | undefined; onAbrir: (id: number) => void }) {
  const lista = dados?.correcoes ?? [];
  if (!dados || lista.length === 0) return null;
  const teclado = (id: number) => (e: KeyboardEvent<HTMLTableRowElement>) => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onAbrir(id); }
  };
  return (
    <div className="panel">
      <div className="panel-head">
        <div>
          <h3>Anonimizações</h3>
          <div className="sub">
            Prévia → aprovação → publicação no CKAN, com cópia do original para reversão
            {!dados.escrita_habilitada && " · escrita no CKAN desligada neste ambiente"}
          </div>
        </div>
      </div>
      <div className="table-scroll">
        <table>
          <thead><tr><th>#</th><th>Recurso</th><th>Situação</th><th>Células</th><th>Pedida por</th><th>Publicada</th></tr></thead>
          <tbody>
            {lista.map((c) => (
              <tr key={c.id} tabIndex={0} onClick={() => onAbrir(c.id)} onKeyDown={teclado(c.id)}>
                <td className="cell-muted">{c.id}</td>
                <td>
                  <div className="cell-strong mono">{c.recurso_nome ?? c.recurso_id}</div>
                  <div className="cell-muted" style={{ fontSize: 12 }}>{c.dataset_titulo}</div>
                </td>
                <td><StatusCorrecaoBadge status={c.status} /></td>
                <td className="cell-muted">{c.celulas_alteradas}</td>
                <td className="cell-muted">{c.solicitada_por ?? "—"}</td>
                <td className="cell-muted">{c.publicada_em ? `${fmtMomento(c.publicada_em)} · ${c.aprovado_por}` : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
