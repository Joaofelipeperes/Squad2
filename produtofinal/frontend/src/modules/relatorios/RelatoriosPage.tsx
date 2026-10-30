import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import type { Formato, Relatorio } from "./api";
import { relatoriosApi } from "./api";
import { Pode } from "@/shared/acesso/Pode";
import { Modal } from "@/shared/ui/Modal";
import { PageLede } from "@/shared/ui/PageLede";
import { useToast } from "@/shared/ui/Toast";

/**
 * Tela "Relatórios" (US20, PBI-60/61/77) — referência visual: #screen-reports do Protótipo V1.
 * Só aparecem os relatórios cujo módulo de origem o usuário acessa. "Gerar relatório" abre a
 * prévia (primeiras linhas); a exportação XLSX/CSV leva o relatório inteiro e exige
 * relatorios.exportar.
 */
export default function RelatoriosPage() {
  const lista = useQuery({ queryKey: ["relatorios"], queryFn: relatoriosApi.lista });
  const [aberto, setAberto] = useState<Relatorio | null>(null);

  return (
    <section className="screen">
      <PageLede titulo="Relatórios">
        Geração de relatórios consolidados para prestação de contas e acompanhamento gerencial.
      </PageLede>

      {lista.isLoading && <div className="panel"><div className="table-empty">Carregando relatórios...</div></div>}
      {lista.isError && <div className="panel"><div className="table-empty">Não foi possível carregar os relatórios: {lista.error.message}</div></div>}
      {lista.data && lista.data.length === 0 && (
        <div className="panel">
          <div className="empty-state">
            <i className="fa-solid fa-file-lines" />
            <p>Nenhum relatório disponível para o seu perfil.</p>
          </div>
        </div>
      )}

      {lista.data && lista.data.length > 0 && (
        <div className="reports-grid">
          {lista.data.map((r) => (
            <div key={r.id} className="report-card">
              <div className="report-icon"><i className={`fa-solid ${r.icone}`} /></div>
              <h4>{r.titulo}</h4>
              <p>{r.descricao}</p>
              <button className="btn btn-outline btn-sm" onClick={() => setAberto(r)}>Gerar relatório</button>
            </div>
          ))}
        </div>
      )}

      {aberto && <PreviaModal relatorio={aberto} onFechar={() => setAberto(null)} />}
    </section>
  );
}

function PreviaModal({ relatorio, onFechar }: { relatorio: Relatorio; onFechar: () => void }) {
  const toast = useToast();
  const previa = useQuery({ queryKey: ["relatorios", relatorio.id, "previa"], queryFn: () => relatoriosApi.previa(relatorio.id) });
  const exportar = useMutation({
    mutationFn: (formato: Formato) => relatoriosApi.exportar(relatorio.id, formato),
    onSuccess: () => toast("Relatório exportado."),
    onError: (e: Error) => toast(e.message, true),
  });
  const p = previa.data;
  const subtitulo = p
    ? [p.referencia, `${p.total} ${p.total === 1 ? "linha" : "linhas"}`,
       p.total > p.linhas.length ? `prévia das ${p.linhas.length} primeiras` : null].filter(Boolean).join(" · ")
    : "Gerando prévia...";

  return (
    <Modal aberto titulo={relatorio.titulo} subtitulo={subtitulo} onFechar={onFechar} largo
      rodape={
        <>
          <button className="btn btn-outline btn-sm" onClick={onFechar}>Fechar</button>
          <Pode permissao="relatorios.exportar">
            <button className="btn btn-outline btn-sm" disabled={!p || exportar.isPending} onClick={() => exportar.mutate("csv")}>
              <i className="fa-solid fa-file-csv" />Exportar CSV
            </button>
            <button className="btn btn-primary btn-sm" disabled={!p || exportar.isPending} onClick={() => exportar.mutate("xlsx")}>
              <i className="fa-solid fa-file-export" />{exportar.isPending ? "Exportando..." : "Exportar Excel"}
            </button>
          </Pode>
        </>
      }>
      {previa.isLoading && <div className="table-empty">Gerando prévia...</div>}
      {previa.isError && <div className="table-empty">Não foi possível gerar a prévia: {previa.error.message}</div>}
      {p && (
        <div className="table-scroll">
          <table>
            <thead><tr>{p.colunas.map((c) => <th key={c}>{c}</th>)}</tr></thead>
            <tbody>
              {p.linhas.length === 0
                ? <tr><td colSpan={p.colunas.length} className="table-empty">Nenhum registro.</td></tr>
                : p.linhas.map((linha, i) => (
                  <tr key={i}>{linha.map((v, j) => <td key={j} className={v ? undefined : "cell-muted"}>{v || "—"}</td>)}</tr>
                ))}
            </tbody>
          </table>
        </div>
      )}
    </Modal>
  );
}
