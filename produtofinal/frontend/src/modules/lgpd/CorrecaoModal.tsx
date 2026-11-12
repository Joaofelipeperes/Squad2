import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import type { Correcao } from "./api";
import { EM_ANDAMENTO, correcoesApi } from "./api";
import { StatusCorrecaoBadge, fmtMomento } from "./formato";
import { useAuth } from "@/app/auth/AuthContext";
import { Modal } from "@/shared/ui/Modal";
import { useToast } from "@/shared/ui/Toast";

/**
 * Passos 2 e 3 da anonimização (US26): conferir a prévia, aprovar e publicar no CKAN (PBI-92/93) ou
 * descartar; depois de publicada, reverter (PBI-94). Atualiza sozinho enquanto o backend trabalha.
 */
export function CorrecaoModal({ id, escritaHabilitada, onFechar, onMudou }: {
  id: number | null; escritaHabilitada: boolean; onFechar: () => void; onMudou: () => void;
}) {
  const { pode } = useAuth();
  const toast = useToast();
  const [texto, setTexto] = useState("");
  const [conferi, setConferi] = useState(false);
  useEffect(() => { setTexto(""); setConferi(false); }, [id]);

  const c = useQuery({
    queryKey: ["lgpd", "correcao", id],
    queryFn: () => correcoesApi.obter(id!),
    enabled: id !== null,
    refetchInterval: (q) => (q.state.data && EM_ANDAMENTO.includes(q.state.data.status) ? 2500 : false),
  });
  const dados = c.data;
  useEffect(() => { if (dados) onMudou(); }, [dados?.status]); // eslint-disable-line react-hooks/exhaustive-deps

  const acao = useMutation({
    mutationFn: (tipo: "aprovar" | "descartar" | "reverter"): Promise<Correcao> =>
      tipo === "aprovar" ? correcoesApi.aprovar(id!, texto.trim() || null)
        : tipo === "descartar" ? correcoesApi.descartar(id!)
        : correcoesApi.reverter(id!, texto.trim()),
    onSuccess: (r) => {
      c.refetch();
      onMudou();
      setTexto("");
      toast(r.status === "publicada" ? "Recurso anonimizado publicado no CKAN."
        : r.status === "revertida" ? "Original restaurado no CKAN."
        : "Prévia descartada e arquivos apagados.");
    },
    onError: (e: Error) => { c.refetch(); toast(e.message, true); },
  });
  const aprovar = pode("lgpd.aprovar_correcao");

  const rodape = <>
    {aprovar && dados && ["previa", "erro"].includes(dados.status) && (
      <button className="btn btn-danger-line btn-sm" disabled={acao.isPending} onClick={() => acao.mutate("descartar")}>
        <i className="fa-solid fa-trash" />Descartar prévia
      </button>
    )}
    {aprovar && dados?.status === "previa" && (
      <button className="btn btn-outline btn-sm" onClick={() => correcoesApi.baixarPrevia(dados.id, dados.nome_arquivo ?? "arquivo")
        .catch((e: Error) => toast(e.message, true))}>
        <i className="fa-solid fa-download" />Baixar prévia
      </button>
    )}
    {aprovar && dados?.status === "previa" && (
      <button className="btn btn-success-line btn-sm" disabled={!conferi || !escritaHabilitada || acao.isPending}
              title={!escritaHabilitada ? "Escrita no CKAN desligada neste ambiente" : undefined}
              onClick={() => acao.mutate("aprovar")}>
        <i className="fa-solid fa-cloud-arrow-up" />{acao.isPending ? "Publicando…" : "Aprovar e publicar no CKAN"}
      </button>
    )}
    {aprovar && dados?.status === "publicada" && (
      <button className="btn btn-danger-line btn-sm" disabled={texto.trim().length < 5 || !escritaHabilitada || acao.isPending}
              onClick={() => acao.mutate("reverter")}>
        <i className="fa-solid fa-rotate-left" />Reverter para o original
      </button>
    )}
    <button className="btn btn-outline btn-sm" onClick={onFechar}>Fechar</button>
  </>;

  return (
    <Modal largo aberto={id !== null} onFechar={onFechar} titulo={`Anonimização #${id ?? ""}`}
      subtitulo={dados ? `${dados.recurso_nome ?? dados.recurso_id} · ${dados.dataset_titulo ?? ""}` : undefined}
      rodape={rodape}>
      {c.isError ? <div className="inline-msg err">{c.error.message}</div> : !dados ? <p className="cell-muted">Carregando…</p> : (
        <>
          <div className="def-grid">
            <div className="def-item"><label>Situação</label><div className="val"><StatusCorrecaoBadge status={dados.status} /></div></div>
            <div className="def-item"><label>Células alteradas</label><div className="val">{dados.celulas_alteradas}</div></div>
            <div className="def-item"><label>Pedida por</label><div className="val">{dados.solicitada_por ?? "—"} · {fmtMomento(dados.solicitada_em)}</div></div>
            <div className="def-item"><label>Arquivo</label><div className="val mono">{dados.nome_arquivo ?? "—"}</div></div>
            {dados.aprovado_por && <div className="def-item"><label>Aprovada por</label><div className="val">{dados.aprovado_por} · {fmtMomento(dados.publicada_em ?? dados.aprovado_em)}</div></div>}
            {dados.revertida_por && <div className="def-item"><label>Revertida por</label><div className="val">{dados.revertida_por} · {fmtMomento(dados.revertida_em)}</div></div>}
          </div>
          {EM_ANDAMENTO.includes(dados.status) && (
            <div className="inline-msg" style={{ marginTop: 14 }}>Processando no servidor… esta janela se atualiza sozinha.</div>
          )}
          {dados.erro && <div className="inline-msg err" style={{ marginTop: 14 }}>{dados.erro}</div>}
          {dados.justificativa && <p style={{ fontSize: 13 }}><b>Justificativa:</b> {dados.justificativa}</p>}
          {dados.motivo_reversao && <p style={{ fontSize: 13 }}><b>Motivo da reversão:</b> {dados.motivo_reversao}</p>}

          <div className="table-scroll" style={{ marginTop: 14 }}>
            <table>
              <thead><tr><th>Tipo</th><th>Coluna</th><th>Como</th><th>Na varredura</th><th>Alteradas</th>
                {dados.status === "previa" && <th>Exemplos (já anonimizados)</th>}</tr></thead>
              <tbody>
                {dados.itens.map((it) => (
                  <tr key={it.achado_id}>
                    <td>{it.tipo_rotulo}</td>
                    <td className="mono">{it.coluna}</td>
                    <td style={{ fontSize: 12 }}>{it.operador_rotulo}{it.alcance === "coluna" && " · célula inteira"}</td>
                    <td className="cell-muted">{it.ocorrencias}</td>
                    <td>
                      {it.alteradas}
                      {it.aviso && <div className="cell-muted" style={{ fontSize: 11.5, maxWidth: 220 }}>{it.aviso}</div>}
                    </td>
                    {dados.status === "previa" && (
                      <td className="mono" style={{ fontSize: 12 }}>
                        {it.exemplos.map((e) => <div key={e.linha}>linha {e.linha}: {e.valor || "(vazio)"}</div>)}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {aprovar && dados.status === "previa" && (
            <>
              {!escritaHabilitada && (
                <div className="inline-msg" style={{ marginTop: 14 }}>
                  A escrita no CKAN está desligada neste ambiente (<code>GDA_CKAN_WRITE_ENABLED</code>):
                  dá para gerar, baixar e conferir a prévia, mas não publicar.
                </div>
              )}
              <div className="form-field" style={{ marginTop: 14 }}>
                <label htmlFor="cor-just">Justificativa da aprovação (opcional)</label>
                <textarea id="cor-just" className="text-input" maxLength={1000} value={texto} onChange={(e) => setTexto(e.target.value)} />
              </div>
              <label className="check-line" style={{ marginTop: 10 }}>
                <input type="checkbox" checked={conferi} onChange={(e) => setConferi(e.target.checked)} />
                <span>Conferi a prévia. O arquivo do recurso no portal será substituído pela versão
                  anonimizada; o original fica guardado para reversão.</span>
              </label>
            </>
          )}
          {aprovar && dados.status === "publicada" && (
            <div className="form-field" style={{ marginTop: 14 }}>
              <label htmlFor="cor-motivo">Motivo da reversão (obrigatório para reverter)</label>
              <textarea id="cor-motivo" className="text-input" maxLength={1000} value={texto} onChange={(e) => setTexto(e.target.value)} />
            </div>
          )}
        </>
      )}
    </Modal>
  );
}
