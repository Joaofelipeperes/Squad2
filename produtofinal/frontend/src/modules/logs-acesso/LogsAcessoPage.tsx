import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import type { FormEvent } from "react";
import { api } from "@/shared/api/client";
import { PageLede } from "@/shared/ui/PageLede";

interface LogAcesso {
  id: number; ocorrido_em: string; usuario: string | null; metodo: string; caminho: string;
  rota: string | null; acao: string | null; status_http: number; ip: string | null; user_agent: string | null;
}
interface Filtros { usuario: string; desde: string; ate: string; limite: string }

const VAZIO: Filtros = { usuario: "", desde: "", ate: "", limite: "200" };

/** SQLite devolve a data sem fuso; o backend grava em UTC. */
const utc = (iso: string) => (/[zZ]|[+-]\d{2}:?\d{2}$/.test(iso) ? iso : `${iso}Z`);
const fmt = (iso: string) =>
  new Date(utc(iso)).toLocaleString("pt-BR", { timeZone: "America/Sao_Paulo", dateStyle: "short", timeStyle: "medium" });
/** datetime-local é hora de Brasília; sem horário de verão desde 2019, o offset é fixo. */
const brt = (local: string) => (local ? `${local}:00-03:00` : "");

function consultar(f: Filtros) {
  const q = new URLSearchParams({ limite: f.limite });
  if (f.usuario.trim()) q.set("usuario", f.usuario.trim());
  if (f.desde) q.set("desde", brt(f.desde));
  if (f.ate) q.set("ate", brt(f.ate));
  return api.get<LogAcesso[]>(`/acesso/logs?${q}`);
}

const classeStatus = (s: number) => (s >= 500 ? "badge-red" : s >= 400 ? "badge-amber" : "badge-green");

function exportarCsv(logs: LogAcesso[]) {
  const cab = ["Data/hora", "Usuário", "Método", "Caminho", "Ação", "Status HTTP", "IP", "User-agent"];
  const linhas = logs.map((l) => [fmt(l.ocorrido_em), l.usuario, l.metodo, l.caminho, l.acao, l.status_http, l.ip, l.user_agent]);
  const cel = (v: unknown) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  // BOM + ";" para o Excel em pt-BR abrir com acentos e colunas certas
  const csv = "﻿" + [cab, ...linhas].map((r) => r.map(cel).join(";")).join("\r\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  a.download = `log-acesso-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(a.href);
}

export default function LogsAcessoPage() {
  const [form, setForm] = useState<Filtros>(VAZIO);
  const [filtros, setFiltros] = useState<Filtros>(VAZIO);
  const logs = useQuery({ queryKey: ["acesso", "logs", filtros], queryFn: () => consultar(filtros) });
  const set = (campo: keyof Filtros) => (e: { target: { value: string } }) => setForm({ ...form, [campo]: e.target.value });
  const aplicar = (e: FormEvent) => { e.preventDefault(); setFiltros(form); };
  const dados = logs.data ?? [];

  return (
    <section className="screen">
      <PageLede titulo="Log de acesso">
        Cada requisição à API fica registrada com data e hora, usuário, rota chamada e resultado.
        Os mais recentes aparecem primeiro.
      </PageLede>

      <div className="panel">
        <form className="filters-bar" onSubmit={aplicar}>
          <div className="filter-field" style={{ flex: 1, minWidth: 220 }}>
            <label htmlFor="log-usuario">Usuário</label>
            <input id="log-usuario" className="text-input" placeholder="Trecho do e-mail"
              value={form.usuario} onChange={set("usuario")} />
          </div>
          <div className="filter-field">
            <label htmlFor="log-desde">Desde</label>
            <input id="log-desde" type="datetime-local" className="text-input" value={form.desde} onChange={set("desde")} />
          </div>
          <div className="filter-field">
            <label htmlFor="log-ate">Até</label>
            <input id="log-ate" type="datetime-local" className="text-input" value={form.ate} onChange={set("ate")} />
          </div>
          <div className="filter-field">
            <label htmlFor="log-limite">Limite</label>
            <select id="log-limite" value={form.limite} onChange={set("limite")}>
              {["200", "1000", "5000"].map((n) => <option key={n} value={n}>{n} linhas</option>)}
            </select>
          </div>
          <div className="filter-actions">
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => { setForm(VAZIO); setFiltros(VAZIO); }}>
              Limpar filtros
            </button>
            <button type="submit" className="btn btn-primary btn-sm"><i className="fa-solid fa-filter" />Filtrar</button>
          </div>
        </form>

        <div className="panel-head">
          <div>
            <h3>Requisições</h3>
            <div className="sub">{logs.isFetching ? "Carregando…" : `${dados.length} registros`}</div>
          </div>
          <button className="btn btn-ghost btn-sm" disabled={!dados.length} onClick={() => exportarCsv(dados)}>
            <i className="fa-solid fa-file-csv" />Exportar CSV
          </button>
        </div>
        <div className="table-scroll">
          <table>
            <thead><tr>
              <th>Data/hora</th><th>Usuário</th><th>Método</th><th>Caminho</th><th>Ação</th>
              <th>Status</th><th>IP</th><th>User-agent</th>
            </tr></thead>
            <tbody>
              {dados.map((l) => (
                <tr key={l.id}>
                  <td style={{ whiteSpace: "nowrap" }}>{fmt(l.ocorrido_em)}</td>
                  <td>{l.usuario ?? <span className="cell-muted">anônimo</span>}</td>
                  <td className="cell-strong">{l.metodo}</td>
                  <td style={{ wordBreak: "break-all" }}>{l.caminho}</td>
                  <td className="cell-muted">{l.acao ?? "—"}</td>
                  <td><span className={`badge ${classeStatus(l.status_http)}`}>{l.status_http}</span></td>
                  <td className="cell-muted">{l.ip ?? "—"}</td>
                  <td className="cell-muted" title={l.user_agent ?? ""}
                    style={{ maxWidth: 260, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {l.user_agent ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {logs.isError && <div className="table-empty">{(logs.error as Error).message}</div>}
          {logs.isSuccess && !dados.length && <div className="table-empty">Nenhum registro para os filtros.</div>}
        </div>
      </div>
    </section>
  );
}
