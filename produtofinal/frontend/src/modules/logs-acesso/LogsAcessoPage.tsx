import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import type { FormEvent } from "react";
import { api } from "@/shared/api/client";
import { PageLede } from "@/shared/ui/PageLede";
import { useToast } from "@/shared/ui/Toast";
import type { Direcao, Ordem } from "@/shared/ui/tabela";
import { ColunaOrdenavel, POR_PAGINA_PADRAO, Paginacao, alternarOrdem } from "@/shared/ui/tabela";

interface LogAcesso {
  id: number; ocorrido_em: string; usuario: string | null; metodo: string; caminho: string;
  rota: string | null; acao: string | null; status_http: number; ip: string | null; user_agent: string | null;
}
/** Página do log (ADR-0028). `ate_id` fixa o fim da lista: as páginas seguintes o repetem. */
interface LogsPagina { total: number; pagina: number; por_pagina: number; ate_id: number | null; registros: LogAcesso[] }
interface Filtros { usuario: string; desde: string; ate: string }
type Coluna = "ocorrido_em" | "usuario" | "metodo" | "caminho" | "acao" | "status_http" | "ip" | "user_agent";

const VAZIO: Filtros = { usuario: "", desde: "", ate: "" };
const ORDEM_PADRAO: Ordem<Coluna> = { coluna: "ocorrido_em", direcao: "desc" };
/** A exportação traz de uma vez até este número de linhas (limite do backend). */
const LIMITE_CSV = 5000;

/** SQLite devolve a data sem fuso; o backend grava em UTC. */
const utc = (iso: string) => (/[zZ]|[+-]\d{2}:?\d{2}$/.test(iso) ? iso : `${iso}Z`);
const fmt = (iso: string) =>
  new Date(utc(iso)).toLocaleString("pt-BR", { timeZone: "America/Sao_Paulo", dateStyle: "short", timeStyle: "medium" });
/** datetime-local é hora de Brasília; sem horário de verão desde 2019, o offset é fixo. */
const brt = (local: string) => (local ? `${local}:00-03:00` : "");

function consultar(f: Filtros, ordem: Ordem<Coluna>, pagina: number, porPagina: number, ateId: number | null) {
  const q = new URLSearchParams({
    pagina: String(pagina), por_pagina: String(porPagina), ordenar: ordem.coluna, direcao: ordem.direcao,
  });
  if (f.usuario.trim()) q.set("usuario", f.usuario.trim());
  if (f.desde) q.set("desde", brt(f.desde));
  if (f.ate) q.set("ate", brt(f.ate));
  if (ateId != null) q.set("ate_id", String(ateId));
  return api.get<LogsPagina>(`/acesso/logs?${q}`);
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
  const toast = useToast();
  const [form, setForm] = useState<Filtros>(VAZIO);
  const [filtros, setFiltros] = useState<Filtros>(VAZIO);
  const [ordem, setOrdem] = useState<Ordem<Coluna>>(ORDEM_PADRAO);
  const [pagina, setPagina] = useState(1);
  const [porPagina, setPorPagina] = useState(POR_PAGINA_PADRAO);
  // Fim da lista fixado ao sair da 1ª consulta: as requisições da própria navegação (que também
  // entram no log) não deslocam as páginas seguintes.
  const [ateId, setAteId] = useState<number | null>(null);
  const [exportando, setExportando] = useState(false);

  const logs = useQuery({
    queryKey: ["acesso", "logs", filtros, ordem, pagina, porPagina, ateId],
    queryFn: () => consultar(filtros, ordem, pagina, porPagina, ateId),
    placeholderData: (anterior: LogsPagina | undefined) => anterior,
  });
  /** Nova consulta do zero: volta à 1ª página e solta o fim fixado (traz os registros novos). */
  const reiniciar = () => { setPagina(1); setAteId(null); };
  const set = (campo: keyof Filtros) => (e: { target: { value: string } }) => setForm({ ...form, [campo]: e.target.value });
  const aplicar = (e: FormEvent) => { e.preventDefault(); setFiltros(form); reiniciar(); };
  const dados = logs.data;
  const fixarFim = () => { if (ateId == null && dados?.ate_id != null) setAteId(dados.ate_id); };
  const ordenarPor = (coluna: Coluna, primeira: Direcao) => {
    fixarFim(); setOrdem((o) => alternarOrdem(o, coluna, primeira)); setPagina(1);
  };
  const col = { ordem, onOrdenar: ordenarPor };
  const registros = dados?.registros ?? [];

  async function exportar() {
    setExportando(true);
    try {
      const r = await consultar(filtros, ordem, 1, LIMITE_CSV, ateId);
      exportarCsv(r.registros);
      if (r.total > r.registros.length) toast(`CSV com os primeiros ${LIMITE_CSV} de ${r.total} registros. Use os filtros para reduzir.`);
    } catch (e) {
      toast(e instanceof Error ? e.message : "Não foi possível exportar.", true);
    } finally {
      setExportando(false);
    }
  }

  return (
    <section className="screen">
      <PageLede titulo="Log de acesso">
        Cada requisição à API fica registrada com data e hora, usuário, rota chamada e resultado.
        Os mais recentes aparecem primeiro; clique no título de uma coluna para ordenar por ela.
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
          <div className="filter-actions">
            <button type="button" className="btn btn-ghost btn-sm"
              onClick={() => { setForm(VAZIO); setFiltros(VAZIO); setOrdem(ORDEM_PADRAO); reiniciar(); }}>
              Limpar filtros
            </button>
            <button type="submit" className="btn btn-primary btn-sm"><i className="fa-solid fa-filter" />Filtrar</button>
          </div>
        </form>

        <div className="panel-head">
          <div><h3>Requisições</h3></div>
          <button className="btn btn-ghost btn-sm" disabled={!registros.length || exportando} onClick={exportar}
            title={`Exporta até ${LIMITE_CSV} registros com os filtros e a ordem atuais`}>
            <i className="fa-solid fa-file-csv" />{exportando ? "Exportando…" : "Exportar CSV"}
          </button>
        </div>
        <div className="table-scroll">
          <table>
            <thead><tr>
              <ColunaOrdenavel coluna="ocorrido_em" primeira="desc" {...col}>Data/hora</ColunaOrdenavel>
              <ColunaOrdenavel coluna="usuario" {...col}>Usuário</ColunaOrdenavel>
              <ColunaOrdenavel coluna="metodo" {...col}>Método</ColunaOrdenavel>
              <ColunaOrdenavel coluna="caminho" {...col}>Caminho</ColunaOrdenavel>
              <ColunaOrdenavel coluna="acao" {...col}>Ação</ColunaOrdenavel>
              <ColunaOrdenavel coluna="status_http" {...col}>Status</ColunaOrdenavel>
              <ColunaOrdenavel coluna="ip" {...col}>IP</ColunaOrdenavel>
              <ColunaOrdenavel coluna="user_agent" {...col}>User-agent</ColunaOrdenavel>
            </tr></thead>
            <tbody>
              {registros.map((l) => (
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
          {!dados && logs.isFetching && <div className="table-empty">Carregando…</div>}
          {logs.isSuccess && !registros.length && <div className="table-empty">Nenhum registro para os filtros.</div>}
        </div>
        {dados && (
          <Paginacao id="log" total={dados.total} pagina={pagina} porPagina={porPagina}
            onPagina={(p) => { fixarFim(); setPagina(p); }}
            onPorPagina={(n) => { fixarFim(); setPorPagina(n); setPagina(1); }}
            carregando={logs.isPlaceholderData} />
        )}
      </div>
    </section>
  );
}
