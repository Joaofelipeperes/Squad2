import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import type { EscopoVarredura } from "./api";
import { lgpdApi } from "./api";
import { StatusVarreduraBadge, fmtMomento } from "./formato";
import { useAuth } from "@/app/auth/AuthContext";
import { datasetsApi, FILTROS_VAZIOS as FILTROS_DATASETS } from "@/modules/datasets/api";
import { useToast } from "@/shared/ui/Toast";

/**
 * Painel de varreduras (não existe no protótipo, que usava dados fixos): pede a varredura dos
 * recursos e mostra as últimas execuções. A varredura roda no backend, em segundo plano; enquanto
 * houver uma em andamento, o painel se atualiza sozinho.
 */
export function VarreduraPainel({ onAndamento }: { onAndamento: (n: number) => void }) {
  const { pode } = useAuth();
  const toast = useToast();
  const qc = useQueryClient();
  const [busca, setBusca] = useState("");
  const [dataset, setDataset] = useState("");
  const [buscaAtiva, setBuscaAtiva] = useState("");

  const lista = useQuery({
    queryKey: ["lgpd", "varreduras"],
    queryFn: lgpdApi.varreduras,
    refetchInterval: (q) => ((q.state.data?.em_andamento ?? 0) > 0 ? 4000 : false),
  });
  const emAndamento = lista.data?.em_andamento ?? 0;
  useEffect(() => { onAndamento(emAndamento); }, [emAndamento, onAndamento]);

  useEffect(() => {
    const t = setTimeout(() => setBuscaAtiva(busca.trim()), 300);
    return () => clearTimeout(t);
  }, [busca]);
  const podeVarrer = pode("lgpd.varrer");
  const datasets = useQuery({
    queryKey: ["inventario", "datasets", "lgpd-busca", buscaAtiva],
    queryFn: () => datasetsApi.lista({ ...FILTROS_DATASETS, busca: buscaAtiva }),
    enabled: podeVarrer && pode("inventario.acessar") && buscaAtiva.length >= 2,
  });

  const varrer = useMutation({
    mutationFn: (p: { escopo: EscopoVarredura; id?: number }) => lgpdApi.varrer(p.escopo, p.id),
    onSuccess: (r, p) => {
      qc.invalidateQueries({ queryKey: ["lgpd", "varreduras"] });
      const doDataset = p.escopo === "dataset";
      const fila = r.ja_na_fila ? ` ${r.ja_na_fila} já estava(m) na fila.` : "";
      toast(r.criadas
        ? (doDataset
          ? `${r.criadas} arquivo(s) do dataset entraram na fila de varredura.${fila}`
          : `${r.criadas} arquivo(s) novos ou alterados entraram na fila (no máximo 200 por vez).${fila}`)
        : r.ja_na_fila ? "Esses arquivos já estão na fila."
        : doDataset ? "Esse dataset não tem arquivos para varrer." : "Nenhum arquivo novo ou alterado desde a última varredura.");
    },
    onError: (e: Error) => toast(e.message, true),
  });

  const cancelar = useMutation({
    mutationFn: lgpdApi.cancelarFila,
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ["lgpd", "varreduras"] });
      toast(`${r.canceladas} varredura(s) cancelada(s). A que já estava rodando termina normalmente.`);
    },
    onError: (e: Error) => toast(e.message, true),
  });

  const ultimas = (lista.data?.varreduras ?? []).slice(0, 6);
  return (
    <div className="panel">
      <div className="panel-head">
        <div>
          <h3>Varredura dos recursos</h3>
          <div className="sub">
            Procura CPF, CNPJ, e-mail, telefone, CEP e endereço nos arquivos CSV e XLSX do portal
            {emAndamento > 0 && <> · <b>{emAndamento} em andamento</b> (atualiza sozinho)</>}
          </div>
        </div>
        {podeVarrer && emAndamento > 0 && (
          <button className="btn btn-danger-line btn-sm" disabled={cancelar.isPending}
                  onClick={() => cancelar.mutate()}>
            <i className="fa-solid fa-ban" />Cancelar fila
          </button>
        )}
      </div>
      <div className="panel-body">
        {podeVarrer && (
          <div className="varredura-opcoes">
            <div className="varredura-opcao">
              <h4><i className="fa-solid fa-globe" />Todo o portal</h4>
              <p>Varre só os arquivos <b>publicados ou alterados desde a última varredura</b>, até 200
                 por vez. Essa varredura também roda sozinha todos os dias de madrugada.</p>
              <div>
                <button className="btn btn-primary btn-sm" disabled={varrer.isPending}
                        onClick={() => varrer.mutate({ escopo: "pendentes" })}>
                  <i className="fa-solid fa-magnifying-glass" />Varrer arquivos novos e alterados
                </button>
              </div>
            </div>

            {pode("inventario.acessar") && (
              <div className="varredura-opcao">
                <h4><i className="fa-solid fa-database" />Um dataset específico</h4>
                <p>Varre <b>todos os arquivos do dataset escolhido</b>, mesmo os que já foram varridos.
                   Use para conferir um dataset na hora.</p>
                <div className="varredura-dataset">
                  <input id="lgpd-busca-ds" className="text-input" aria-label="Buscar dataset pelo nome"
                         placeholder="Buscar dataset pelo nome…"
                         value={busca} onChange={(e) => { setBusca(e.target.value); setDataset(""); }} />
                  <select id="lgpd-ds" aria-label="Dataset" value={dataset}
                          onChange={(e) => setDataset(e.target.value)} disabled={!datasets.data}>
                    <option value="">{buscaAtiva.length < 2 ? "Digite ao menos 2 letras" :
                      datasets.data ? `${datasets.data.datasets.length} encontrado(s)` : "Buscando…"}</option>
                    {datasets.data?.datasets.slice(0, 50).map((d) => (
                      <option key={d.id} value={d.id}>{d.titulo}</option>
                    ))}
                  </select>
                  <button className="btn btn-outline btn-sm" disabled={!dataset || varrer.isPending}
                          onClick={() => varrer.mutate({ escopo: "dataset", id: Number(dataset) })}>
                    <i className="fa-solid fa-play" />Varrer este dataset
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
        {lista.isError ? (
          <div className="inline-msg err" role="alert">{lista.error.message}</div>
        ) : ultimas.length === 0 ? (
          <p className="cell-muted" style={{ fontSize: 13, margin: 0 }}>Nenhuma varredura executada ainda.</p>
        ) : (
          <div className="table-scroll">
            <table>
              <thead><tr><th>Recurso</th><th>Situação</th><th>Linhas</th><th>Achados</th>
                <th>Chamadas ao modelo</th><th>Modelo</th><th>Quando</th></tr></thead>
              <tbody>
                {ultimas.map((v) => (
                  <tr key={v.id}>
                    <td>
                      <div className="cell-strong mono">{v.recurso_nome ?? v.recurso_id}</div>
                      <div className="cell-muted" style={{ fontSize: 12 }}>{v.dataset_titulo}</div>
                      {(v.erro || v.aviso) && (
                        <div className={v.erro ? "inline-msg err" : "inline-msg"} style={{ marginTop: 6, whiteSpace: "pre-wrap" }}>
                          {v.erro ?? v.aviso}
                        </div>
                      )}
                    </td>
                    <td><StatusVarreduraBadge status={v.status} /></td>
                    <td className="cell-muted">{v.linhas_analisadas.toLocaleString("pt-BR")}</td>
                    <td className="cell-muted">{v.achados}</td>
                    <td className="cell-muted">{v.chamadas_ia}</td>
                    <td className="mono cell-muted">{v.modelo ?? "—"}</td>
                    <td className="cell-muted">{fmtMomento(v.finalizada_em ?? v.iniciada_em ?? v.solicitada_em)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
