import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import type { Evento, EventosLista, FiltrosEventos, Sincronizacao } from "./api";
import { FILTROS_VAZIOS, rastreabilidadeApi, salvarArquivo } from "./api";
import { PageLede } from "@/shared/ui/PageLede";

/**
 * Tela "Rastreabilidade" (US14, US29, PBI-85) — referência visual: #screen-traceability do
 * Protótipo V1. Linha do tempo lida da auditoria do CKAN (extensão ckanext-dsaudit, ADR-0009),
 * sincronizada ao fim de cada coleta ("Atualizar dados").
 */
export default function RastreabilidadePage() {
  const [filtros, setFiltros] = useState<FiltrosEventos>(FILTROS_VAZIOS);
  const [busca, setBusca] = useState("");

  // A busca é enviada ao backend com uma pequena espera, para não consultar a cada tecla.
  useEffect(() => {
    const t = setTimeout(() => setFiltros((f) => (f.busca === busca ? f : { ...f, busca })), 300);
    return () => clearTimeout(t);
  }, [busca]);

  const lista = useQuery({
    queryKey: ["rastreabilidade", "eventos", filtros],
    queryFn: () => rastreabilidadeApi.eventos(filtros),
    placeholderData: (anterior: EventosLista | undefined) => anterior,
  });
  const set = (campo: keyof FiltrosEventos) => (valor: string) => setFiltros((f) => ({ ...f, [campo]: valor }));
  const limpar = () => { setBusca(""); setFiltros(FILTROS_VAZIOS); };
  const filtrando = Boolean(filtros.busca || filtros.tipo || filtros.orgao || filtros.desde || filtros.ate);
  const dados = lista.data;

  return (
    <section className="screen">
      <PageLede titulo="Rastreabilidade">
        Linha do tempo de alterações observadas no Portal de Dados Abertos.
      </PageLede>

      {dados && <AvisoSincronizacao sinc={dados.sincronizacao} />}

      <div className="panel">
        <div className="filters-bar" style={{ borderRadius: "6px 6px 0 0" }}>
          <div className="search-field">
            <i className="fa-solid fa-magnifying-glass" />
            <input type="text" className="text-input" aria-label="Buscar por dataset ou órgão"
                   placeholder="Buscar por dataset ou órgão (título, nome ou ID)..." value={busca}
                   onChange={(e) => setBusca(e.target.value)} />
          </div>
          <Filtro id="trace-filter-type" rotulo="Tipo de alteração" vazio="Todas" valor={filtros.tipo}
            onMudar={set("tipo")} opcoes={dados?.opcoes.tipos ?? []} />
          <Filtro id="trace-filter-org" rotulo="Órgão" vazio="Todos" valor={filtros.orgao}
            onMudar={set("orgao")} opcoes={dados?.opcoes.orgaos ?? []} classe="filter-field-limitado" />
          <div className="filter-field">
            <label htmlFor="trace-filter-desde">De</label>
            <input id="trace-filter-desde" type="date" className="text-input" value={filtros.desde}
                   max={filtros.ate || undefined} onChange={(e) => set("desde")(e.target.value)} />
          </div>
          <div className="filter-field">
            <label htmlFor="trace-filter-ate">Até</label>
            <input id="trace-filter-ate" type="date" className="text-input" value={filtros.ate}
                   min={filtros.desde || undefined} onChange={(e) => set("ate")(e.target.value)} />
          </div>
          <div className="filter-field">
            <label htmlFor="trace-filter-ordem">Ordenar por data</label>
            <select id="trace-filter-ordem" value={filtros.ordem}
                    onChange={(e) => set("ordem")(e.target.value as FiltrosEventos["ordem"])}>
              <option value="recentes">Mais recentes primeiro</option>
              <option value="antigos">Mais antigos primeiro</option>
            </select>
          </div>
          <div className="filter-actions">
            <button type="button" className="btn btn-ghost btn-sm" onClick={limpar}>
              Limpar filtros
            </button>
          </div>
        </div>
        <div className="panel-head" style={{ borderBottom: "none", paddingBottom: 0 }}>
          <div className="sub" style={{ fontSize: 12.5 }} aria-live="polite">
            {dados ? resumoContagem(dados, filtros.ordem) : lista.isError ? "" : "Carregando…"}
            {lista.isPlaceholderData && " · atualizando…"}
          </div>
        </div>
        <div className="panel-body">
          {lista.isError ? (
            <div className="inline-msg err" role="alert">
              Não foi possível carregar a linha do tempo: {lista.error.message}
            </div>
          ) : !dados ? (
            <div className="empty-state"><p>Carregando…</p></div>
          ) : dados.eventos.length === 0 ? (
            <div className="empty-state">
              <i className="fa-solid fa-clock-rotate-left" />
              <p>{dados.total === 0 && !filtrando
                ? "Nenhum evento registrado ainda: rode a coleta pelo botão \"Atualizar dados\"."
                : "Nenhum evento para os filtros selecionados."}</p>
            </div>
          ) : (
            <div className="timeline">
              {dados.eventos.map((e) => <ItemLinhaDoTempo key={e.id} e={e} />)}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function resumoContagem(d: EventosLista, ordem: FiltrosEventos["ordem"]): string {
  if (d.total === d.exibidos) return `${d.total} evento(s)`;
  return `${d.exibidos} evento(s) ${ordem === "antigos" ? "mais antigos" : "mais recentes"} de ${d.total}`;
}

/** Mesmo mapa do typeIconMap do protótipo V1. */
const ICONE: Record<string, { cls: string; icon: string }> = {
  inclusao: { cls: "create", icon: "fa-plus" },
  alteracao: { cls: "", icon: "fa-pen" },
  exclusao: { cls: "delete", icon: "fa-trash" },
  privacao: { cls: "private", icon: "fa-lock" },
  recurso_atualizado: { cls: "", icon: "fa-rotate" },
};

const fmtDataHora = (iso: string) =>
  new Date(iso).toLocaleString("pt-BR", { timeZone: "America/Sao_Paulo", dateStyle: "short", timeStyle: "short" });

function ItemLinhaDoTempo({ e }: { e: Evento }) {
  const [aberto, setAberto] = useState(false);
  const [diffAberto, setDiffAberto] = useState(false);
  const meta = ICONE[e.tipo] ?? { cls: "", icon: "fa-circle" };
  const orgao = e.origem === "comparacao_coletas";
  return (
    <div className="tl-item">
      <div className={`tl-dot ${meta.cls}`} />
      <div className="tl-card">
        <div className="tl-top">
          <span className="tl-type">
            <i className={`fa-solid ${meta.icon}`} style={{ marginRight: 6, color: "var(--gray-500)" }} />
            {e.tipo_rotulo}
          </span>
          <span className="tl-date">{fmtDataHora(e.ocorrido_em)}</span>
        </div>
        <div className="tl-meta">
          <b>{e.orgao_nome ?? "Órgão não identificado"}</b>
          {orgao
            ? <> · <span className="badge badge-gray">Cadastro do órgão</span></>
            : <> · <span title={e.dataset_id_ckan ?? undefined}>{e.dataset_titulo}</span></>}
          {e.origem === "atividade_nativa" && (
            <> · <span className="badge badge-amber"
                       title="Ação registrada só pelo CKAN, fora da edição auditada pela extensão (ex.: Make public/Make private/Delete em lote na página da organização). Quem e quando vêm do CKAN; o que mudou é deduzido.">
              Fora da auditoria
            </span></>
          )}
          {e.recurso_nome && <> · <span className="mono">{e.recurso_nome}</span></>}
        </div>
        <div className="tl-meta" style={{ marginTop: 4 }}>{e.resumo}</div>
        <div className="tl-meta" style={{ marginTop: 2, color: "var(--gray-500)" }}>
          {orgao && !e.usuario
            ? <span title="A mudança foi detectada comparando o cadastro do órgão entre duas coletas; o CKAN não informou quem alterou (token não configurado ou sem acesso às atividades do órgão).">
                Detectado na coleta · usuário não identificado
              </span>
            : orgao
              ? <span title="O que mudou vem da comparação entre coletas; quem alterou e quando, das atividades do órgão registradas pelo CKAN.">
                  Usuário: {e.usuario} · detectado na coleta
                </span>
              : <>Usuário: {e.usuario ?? "—"}</>}
          {e.detalhes.length > 0 && (
            <>
              {" · "}
              <button type="button" className="btn btn-ghost btn-sm" style={{ padding: "0 4px" }}
                      aria-expanded={aberto} onClick={() => setAberto((v) => !v)}>
                {aberto ? "Ocultar detalhes" : `Ver detalhes (${e.detalhes.length})`}
              </button>
            </>
          )}
          {e.tem_diff && (
            <>
              {" · "}
              <button type="button" className="btn btn-ghost btn-sm" style={{ padding: "0 4px" }}
                      aria-expanded={diffAberto} onClick={() => setDiffAberto((v) => !v)}>
                <i className="fa-solid fa-code-compare" style={{ marginRight: 4 }} />
                {diffAberto ? "Ocultar diff" : "Ver diff do arquivo"}
              </button>
            </>
          )}
        </div>
        {aberto && <Detalhes e={e} />}
        {diffAberto && <DiffArquivo eventoId={e.id} />}
      </div>
    </div>
  );
}

const CLASSE_SITUACAO_LINHA: Record<string, string> = {
  "incluída": "badge-green", "alterada": "badge-amber", "removida": "badge-red",
};

/** Quantas linhas da comparação aparecem na tela; o restante vai no CSV para download. */
const PREVIA_LINHAS_DIFF = 3;

/** Diff linha a linha buscado no CKAN só quando aberto (não fica gravado na solução). Mostra uma
 * prévia de até 3 linhas; todas as alterações detalhadas ficam no CSV para download. */
function DiffArquivo({ eventoId }: { eventoId: number }) {
  const diff = useQuery({
    queryKey: ["rastreabilidade", "diff", eventoId],
    queryFn: () => rastreabilidadeApi.diff(eventoId),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  const [baixando, setBaixando] = useState(false);
  const [erroCsv, setErroCsv] = useState<string | null>(null);

  async function baixarCsv() {
    setBaixando(true);
    setErroCsv(null);
    try {
      const { blob, filename } = await rastreabilidadeApi.baixarDiffCsv(eventoId);
      salvarArquivo(blob, filename);
    } catch (e) {
      setErroCsv(e instanceof Error ? e.message : "Não foi possível baixar o CSV.");
    } finally {
      setBaixando(false);
    }
  }

  if (diff.isError) {
    return <div className="inline-msg err" role="alert" style={{ marginTop: 8 }}>{diff.error.message}</div>;
  }
  if (!diff.data) return <div className="tl-meta" style={{ marginTop: 8 }}>Carregando o diff do CKAN…</div>;
  const d = diff.data;
  const previa = d.linhas.slice(0, PREVIA_LINHAS_DIFF);
  const temMais = d.total_linhas > previa.length;
  const versoes = d.versao_anterior != null && d.versao_nova != null
    ? `versão ${d.versao_anterior} → ${d.versao_nova}` : "";
  return (
    <div style={{ marginTop: 8 }}>
      <div className="tl-meta" style={{ color: "var(--gray-500)", marginBottom: 6 }}>
        {[d.arquivo_novo, versoes].filter(Boolean).join(" · ")}
        {d.colunas_chave.length > 0
          ? ` · linhas comparadas pela chave: ${d.colunas_chave.join(", ")}`
          : " · linhas comparadas pela posição (sem coluna de valores únicos)"}
        {temMais && ` · prévia de ${previa.length} de ${d.total_linhas} linhas`}
      </div>
      <div className="table-scroll">
        <table>
          <thead><tr><th>Linha</th><th>Situação</th><th>Coluna</th><th>Antes</th><th>Depois</th></tr></thead>
          <tbody>
            {previa.flatMap((l, i) => {
              const campos = l.campos.length ? l.campos : [{ campo: "—", anterior: null, novo: null }];
              return campos.map((c, j) => (
                <tr key={`${i}-${j}`}>
                  {j === 0 && <td className="mono" rowSpan={campos.length}>{l.chave}</td>}
                  {j === 0 && (
                    <td rowSpan={campos.length}>
                      <span className={`badge ${CLASSE_SITUACAO_LINHA[l.situacao] ?? "badge-gray"}`}>{l.situacao}</span>
                    </td>
                  )}
                  <td>{c.campo}</td>
                  <td className="cell-muted" style={{ wordBreak: "break-word" }}>{c.anterior ?? "—"}</td>
                  <td style={{ wordBreak: "break-word" }}>{c.novo ?? "—"}</td>
                </tr>
              ));
            })}
          </tbody>
        </table>
      </div>
      <div className="tl-meta" style={{ marginTop: 6, display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        <button type="button" className="btn btn-ghost btn-sm" onClick={baixarCsv} disabled={baixando}>
          <i className="fa-solid fa-file-csv" style={{ marginRight: 4 }} />
          {baixando ? "Gerando CSV…" : "Baixar CSV com todas as alterações"}
        </button>
        {temMais && (
          <span style={{ color: "var(--gray-500)" }}>
            A tela mostra {previa.length} de {d.total_linhas} linhas; o CSV traz todas.
          </span>
        )}
      </div>
      {erroCsv && <div className="inline-msg err" role="alert" style={{ marginTop: 6 }}>{erroCsv}</div>}
    </div>
  );
}

const SITUACAO_RECURSO: Record<string, string> = { added: "incluído", changed: "alterado", removed: "removido" };

function Detalhes({ e }: { e: Evento }) {
  return (
    <div className="table-scroll" style={{ marginTop: 8 }}>
      <table>
        <thead><tr><th>Onde</th><th>Campo</th><th>Antes</th><th>Depois</th></tr></thead>
        <tbody>
          {e.detalhes.map((d, i) => (
            <tr key={i}>
              <td className="cell-muted">
                {d.escopo === "resource"
                  ? `Recurso ${d.recurso ?? ""}${d.situacao && SITUACAO_RECURSO[d.situacao] ? ` (${SITUACAO_RECURSO[d.situacao]})` : ""}`
                  : d.escopo === "dataset" ? "Dataset"
                  : d.escopo === "orgao" ? "Órgão" : "Arquivo / DataStore"}
              </td>
              <td>{d.campo}</td>
              <td className="cell-muted" style={{ wordBreak: "break-word" }}>{d.anterior ?? "—"}</td>
              <td style={{ wordBreak: "break-word" }}>{d.novo ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AvisoSincronizacao({ sinc }: { sinc: Sincronizacao | null }) {
  if (!sinc) {
    return (
      <div className="inline-msg" style={{ marginBottom: 12, background: "var(--gray-100)" }}>
        A auditoria do CKAN ainda não foi lida. Ela é sincronizada ao fim de cada coleta.
      </div>
    );
  }
  const quando = fmtDataHora(sinc.finalizada_em ?? sinc.iniciada_em);
  const orgaos = sinc.orgaos_consultados
    ? ` Cadastro de ${sinc.orgaos_consultados} órgão(s) comparado com a coleta anterior.` : "";
  if (sinc.status === "ignorada" || sinc.status === "erro") {
    return (
      <div className="inline-msg err" role="alert" style={{ marginBottom: 12 }}>
        Última leitura da auditoria do CKAN ({quando}) não concluída: {sinc.erro}{orgaos}
      </div>
    );
  }
  const avisos = [];
  if (sinc.erro) avisos.push(sinc.erro);
  if (sinc.datasets_sem_permissao) avisos.push(`${sinc.datasets_sem_permissao} dataset(s) sem permissão de leitura`);
  if (sinc.datasets_nao_encontrados) avisos.push(`${sinc.datasets_nao_encontrados} não encontrado(s) no CKAN`);
  return (
    <div className="sub" style={{ fontSize: 12.5, marginBottom: 12, color: "var(--gray-500)" }}>
      Auditoria do CKAN lida em {quando}
      {sinc.status === "executando" ? " (em andamento)" : ""}: {sinc.datasets_consultados} dataset(s),
      {" "}{sinc.eventos_novos} evento(s) novo(s){avisos.length ? ` · ${avisos.join(" · ")}` : ""}.{orgaos}
    </div>
  );
}

function Filtro({ id, rotulo, vazio, valor, opcoes, onMudar, classe }: {
  id: string; rotulo: string; vazio: string; valor: string; opcoes: { valor: string; rotulo: string }[];
  onMudar: (v: string) => void; classe?: string;
}) {
  return (
    <div className={classe ? `filter-field ${classe}` : "filter-field"}>
      <label htmlFor={id}>{rotulo}</label>
      <select id={id} value={valor} onChange={(e) => onMudar(e.target.value)}>
        <option value="">{vazio}</option>
        {opcoes.map((o) => <option key={o.valor} value={o.valor}>{o.rotulo}</option>)}
      </select>
    </div>
  );
}
