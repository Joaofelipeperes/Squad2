import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { KeyboardEvent } from "react";
import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import type { Achado, AchadosLista, FiltrosLgpd } from "./api";
import { FILTROS_VAZIOS, ROTULO_STATUS, correcoesApi, lgpdApi } from "./api";
import type { GrupoRecurso } from "./agrupar";
import { agruparPorRecurso } from "./agrupar";
import { AchadoModal } from "./AchadoModal";
import { CorrecaoModal } from "./CorrecaoModal";
import { CorrecoesPainel } from "./CorrecoesPainel";
import { NovaCorrecaoModal } from "./NovaCorrecaoModal";
import { PrioridadeTag, StatusAchadoBadge, classeStatusAchado } from "./formato";
import { VarreduraPainel } from "./VarreduraPainel";
import { PageLede } from "@/shared/ui/PageLede";
import type { Direcao, Ordem, Ordenadores } from "@/shared/ui/tabela";
import { ColunaOrdenavel, Paginacao, alternarOrdem, ordenar, useTabela } from "@/shared/ui/tabela";

/** Prioridade como número para ordenar: "desc" = Alta primeiro. */
const NIVEL: Record<string, number> = { Alta: 3, "Média": 2, Baixa: 1 };

type ColunaGrupo = "prioridade" | "orgao" | "dataset" | "arquivo" | "tipos" | "achados" | "situacao";
const ORDENADORES_GRUPO: Ordenadores<GrupoRecurso, ColunaGrupo> = {
  prioridade: (g) => NIVEL[g.prioridade],
  orgao: (g) => g.orgao,
  dataset: (g) => g.dataset_titulo,
  arquivo: (g) => g.recurso_nome,
  tipos: (g) => g.celulas,
  achados: (g) => g.achados.length,
  situacao: (g) => g.status.revisar ?? 0, // quantos ainda aguardam revisão
};

type ColunaAchado = "prioridade" | "tipo" | "coluna" | "linha" | "confianca" | "status";
const ORDENADORES_ACHADO: Ordenadores<Achado, ColunaAchado> = {
  prioridade: (a) => NIVEL[a.prioridade],
  tipo: (a) => a.tipo_rotulo,
  coluna: (a) => a.coluna,
  linha: (a) => a.linha,
  confianca: (a) => a.confianca,
  status: (a) => ROTULO_STATUS[a.status],
};

/**
 * Tela "Riscos de Dados Pessoais" (US11/US12) — referência visual: #screen-lgpd e #modal-lgpd do
 * Protótipo V1. Os achados vêm da varredura do backend (motor do detector3: regras + modelo local);
 * a tela nunca recebe o valor encontrado, só local, tipo e confiança.
 */
export default function LgpdPage() {
  const [filtros, setFiltros] = useState<FiltrosLgpd>(FILTROS_VAZIOS);
  const [aberto, setAberto] = useState<number | null>(null);
  const [anonimizar, setAnonimizar] = useState<number | null>(null);  // recurso da nova prévia
  const [correcao, setCorrecao] = useState<number | null>(null);
  const qc = useQueryClient();
  const correcoes = useQuery({ queryKey: ["lgpd", "correcoes"], queryFn: correcoesApi.lista });

  const lista = useQuery({
    queryKey: ["lgpd", "achados", filtros],
    queryFn: () => lgpdApi.achados(filtros),
    placeholderData: (anterior: AchadosLista | undefined) => anterior,
  });
  const dados = lista.data;
  const grupos = useMemo(() => agruparPorRecurso(dados?.achados ?? []), [dados]);
  const tabela = useTabela(grupos, ORDENADORES_GRUPO);
  const col = { ordem: tabela.ordem, onOrdenar: tabela.ordenarPor };
  const [abertos, setAbertos] = useState<Set<number>>(new Set());
  const alternar = (recursoId: number) => setAbertos((s) => {
    const n = new Set(s);
    if (n.has(recursoId)) n.delete(recursoId); else n.add(recursoId);
    return n;
  });
  const set = (campo: keyof FiltrosLgpd) => (valor: string) => setFiltros((f) => ({ ...f, [campo]: valor }));
  const atualizarAchados = () => qc.invalidateQueries({ queryKey: ["lgpd", "achados"] });
  const atualizarTudo = () => { atualizarAchados(); qc.invalidateQueries({ queryKey: ["lgpd", "correcoes"] }); };

  // Quando uma varredura termina, a lista de achados é recarregada
  const andamentoAnterior = useRef(0);
  const aoMudarAndamento = (emAndamento: number) => {
    if (emAndamento < andamentoAnterior.current) atualizarAchados();
    andamentoAnterior.current = emAndamento;
  };
  useEffect(() => () => { andamentoAnterior.current = 0; }, []);

  const k = dados?.kpis;
  const kpis = [
    { icone: "fa-magnifying-glass", cor: "blue", valor: k?.recursos_analisados, rotulo: "Recursos analisados" },
    { icone: "fa-shield-halved", cor: "red", valor: k?.recursos_com_achados, rotulo: "Recursos com possíveis dados pessoais" },
    { icone: "fa-triangle-exclamation", cor: "red", valor: k?.alertas_criticos, rotulo: "Alertas críticos (prioridade alta)" },
    { icone: "fa-user-check", cor: "amber", valor: k?.alertas_para_revisao, rotulo: "Alertas para revisão" },
  ];

  return (
    <section className="screen">
      <PageLede titulo="Riscos de Dados Pessoais">Detecção e priorização para análise humana.</PageLede>

      <div className="kpi-grid" style={{ gridTemplateColumns: "repeat(4,1fr)" }}>
        {kpis.map((c) => (
          <div className="kpi-card" key={c.rotulo}>
            <div className="kpi-top"><div className={`kpi-icon ${c.cor}`}><i className={`fa-solid ${c.icone}`} /></div></div>
            <div className="kpi-value">{c.valor ?? "—"}</div>
            <div className="kpi-label">{c.rotulo}</div>
          </div>
        ))}
      </div>

      <VarreduraPainel onAndamento={aoMudarAndamento} />
      <CorrecoesPainel dados={correcoes.data} onAbrir={setCorrecao} />

      <div className="panel">
        <div className="filters-bar">
          <Filtro id="lgpd-prioridade" rotulo="Prioridade" valor={filtros.prioridade} onMudar={set("prioridade")}
            opcoes={(dados?.opcoes.prioridades ?? ["Alta", "Média", "Baixa"]).map((p) => ({ valor: p, rotulo: p }))} />
          <Filtro id="lgpd-tipo" rotulo="Tipo de dado" valor={filtros.tipo} onMudar={set("tipo")}
            opcoes={dados?.opcoes.tipos ?? []} />
          <Filtro id="lgpd-orgao" rotulo="Órgão" valor={filtros.orgao} onMudar={set("orgao")}
            opcoes={dados?.opcoes.orgaos ?? []} />
          <Filtro id="lgpd-status" rotulo="Status" valor={filtros.status} onMudar={set("status")}
            opcoes={dados?.opcoes.status ?? []} />
          <div className="filter-actions">
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setFiltros(FILTROS_VAZIOS)}>
              Limpar filtros
            </button>
          </div>
        </div>
        <div className="table-scroll">
          <table className="lgpd-grupos">
            <thead><tr>
              <th style={{ width: 28 }} aria-label="Expandir" />
              <ColunaOrdenavel coluna="prioridade" primeira="desc" {...col}>Prioridade</ColunaOrdenavel>
              <ColunaOrdenavel coluna="orgao" {...col}>Órgão</ColunaOrdenavel>
              <ColunaOrdenavel coluna="dataset" {...col}>Dataset</ColunaOrdenavel>
              <ColunaOrdenavel coluna="arquivo" {...col}>Arquivo</ColunaOrdenavel>
              <ColunaOrdenavel coluna="tipos" primeira="desc" {...col}
                title="Ordena pelo total de células sinalizadas no arquivo">Dados pessoais encontrados</ColunaOrdenavel>
              <ColunaOrdenavel coluna="achados" primeira="desc" {...col}>Achados</ColunaOrdenavel>
              <ColunaOrdenavel coluna="situacao" primeira="desc" {...col}
                title="Ordena pelo número de achados que ainda aguardam revisão">Situação</ColunaOrdenavel>
            </tr></thead>
            <tbody>
              {lista.isError ? (
                <tr><td colSpan={COLUNAS} style={{ padding: 18 }}>
                  <div className="inline-msg err" role="alert">Não foi possível carregar os achados: {lista.error.message}</div>
                </td></tr>
              ) : !dados ? (
                <tr><td colSpan={COLUNAS} className="table-empty">Carregando…</td></tr>
              ) : dados.total === 0 ? (
                <tr><td colSpan={COLUNAS} className="table-empty">
                  <i className="fa-solid fa-inbox" style={{ marginRight: 8 }} />
                  Nenhum possível dado pessoal encontrado até agora. Rode uma varredura no painel acima.
                </td></tr>
              ) : grupos.length === 0 ? (
                <tr><td colSpan={COLUNAS} className="table-empty">Nenhum alerta para os filtros selecionados.</td></tr>
              ) : (
                tabela.itens.map((g) => (
                  <Grupo key={g.recurso_id} g={g} aberto={abertos.has(g.recurso_id)}
                         onAlternar={() => alternar(g.recurso_id)} onAbrir={setAberto} />
                ))
              )}
            </tbody>
          </table>
        </div>
        {dados && (
          <Paginacao id="lgpd" {...tabela.paginacao} carregando={lista.isPlaceholderData}
            resumo={<><strong>{grupos.length}</strong> arquivo(s) · {dados.achados.length} achado(s).
              {grupos.length > 0 && " Clique num arquivo para ver coluna, linha e confiança de cada achado."}</>} />
        )}
      </div>

      <AchadoModal id={aberto} onFechar={() => setAberto(null)} onDecidido={atualizarAchados}
        onAnonimizar={(r) => { setAberto(null); setAnonimizar(r); }} />
      <NovaCorrecaoModal recursoId={anonimizar} onFechar={() => setAnonimizar(null)}
        onCriada={(c) => { setAnonimizar(null); atualizarTudo(); setCorrecao(c.id); }} />
      <CorrecaoModal id={correcao} escritaHabilitada={correcoes.data?.escrita_habilitada ?? false}
        onFechar={() => setCorrecao(null)} onMudou={atualizarTudo} />
    </section>
  );
}

function Filtro({ id, rotulo, valor, opcoes, onMudar }: {
  id: string; rotulo: string; valor: string; opcoes: { valor: string; rotulo: string }[];
  onMudar: (v: string) => void;
}) {
  return (
    <div className="filter-field">
      <label htmlFor={id}>{rotulo}</label>
      <select id={id} value={valor} onChange={(e) => onMudar(e.target.value)}>
        <option value="">{rotulo === "Prioridade" ? "Todas" : "Todos"}</option>
        {opcoes.map((o) => <option key={o.valor} value={o.valor}>{o.rotulo}</option>)}
      </select>
    </div>
  );
}

const COLUNAS = 8;

/** Linha do arquivo (resumo) e, aberta, a tabela com o detalhe de cada achado. */
function Grupo({ g, aberto, onAlternar, onAbrir }: {
  g: GrupoRecurso; aberto: boolean; onAlternar: () => void; onAbrir: (id: number) => void;
}) {
  const teclado = (e: KeyboardEvent<HTMLTableRowElement>) => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onAlternar(); }
  };
  const detalheId = `lgpd-grupo-${g.recurso_id}`;
  const [ordem, setOrdem] = useState<Ordem<ColunaAchado> | null>(null);
  const achados = useMemo(() => ordenar(g.achados, ordem, ORDENADORES_ACHADO), [g.achados, ordem]);
  const col = { ordem, onOrdenar: (c: ColunaAchado, p: Direcao) => setOrdem((o) => alternarOrdem(o, c, p)) };
  return (
    <Fragment>
      <tr className={`lgpd-grupo${aberto ? " aberto" : ""}`} tabIndex={0} onClick={onAlternar}
          onKeyDown={teclado} aria-expanded={aberto} aria-controls={detalheId}>
        <td><i className={`fa-solid fa-chevron-${aberto ? "down" : "right"} cell-muted`} /></td>
        <td><PrioridadeTag prioridade={g.prioridade} /></td>
        <td title={g.orgao_nome ?? undefined}>{g.orgao}</td>
        <td className="cell-strong">{g.dataset_titulo}</td>
        <td className="mono cell-muted">{g.recurso_nome}</td>
        <td>
          <div className="lgpd-tipos">
            {g.tipos.map((t) => (
              <span key={t.rotulo} className="chip-tipo" title={`${t.celulas} célula(s)`}>
                {t.rotulo} <b>{t.celulas}</b>
              </span>
            ))}
          </div>
        </td>
        <td className="cell-muted" title={`${g.celulas} célula(s) sinalizadas no arquivo`}>
          {g.achados.length} {g.achados.length === 1 ? "coluna" : "colunas"}
        </td>
        <td>
          <div className="lgpd-tipos">
            {(Object.entries(g.status) as [keyof typeof ROTULO_STATUS, number][]).map(([st, n]) => (
              <span key={st} className={`badge ${classeStatusAchado(st)}`}>{n} {ROTULO_STATUS[st]}</span>
            ))}
          </div>
        </td>
      </tr>
      {aberto && (
        <tr className="lgpd-detalhe" id={detalheId}>
          <td colSpan={COLUNAS}>
            <table>
              <thead><tr>
                <ColunaOrdenavel coluna="prioridade" primeira="desc" {...col}>Prioridade</ColunaOrdenavel>
                <ColunaOrdenavel coluna="tipo" {...col}>Tipo identificado</ColunaOrdenavel>
                <ColunaOrdenavel coluna="coluna" {...col}>Coluna</ColunaOrdenavel>
                <ColunaOrdenavel coluna="linha" {...col}>Linha</ColunaOrdenavel>
                <ColunaOrdenavel coluna="confianca" primeira="desc" {...col}>Confiança</ColunaOrdenavel>
                <ColunaOrdenavel coluna="status" {...col}>Status</ColunaOrdenavel>
              </tr></thead>
              <tbody>
                {achados.map((a) => <Linha key={a.id} a={a} onAbrir={onAbrir} />)}
              </tbody>
            </table>
          </td>
        </tr>
      )}
    </Fragment>
  );
}

function Linha({ a, onAbrir }: { a: Achado; onAbrir: (id: number) => void }) {
  const teclado = (e: KeyboardEvent<HTMLTableRowElement>) => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onAbrir(a.id); }
  };
  return (
    <tr tabIndex={0} onClick={() => onAbrir(a.id)} onKeyDown={teclado}>
      <td><PrioridadeTag prioridade={a.prioridade} /></td>
      <td>{a.tipo_rotulo}{a.metodo === "ia" && <span className="cell-muted" title="Confirmado pelo modelo local"> · IA</span>}</td>
      <td className="mono">{a.coluna}</td>
      <td className="cell-muted" title={`${a.ocorrencias} célula(s) nesta coluna; a linha é a primeira`}>
        {a.linha ?? "—"}{a.ocorrencias > 1 && ` (+${a.ocorrencias - 1})`}
      </td>
      <td className="cell-muted">{a.confianca}%</td>
      <td><StatusAchadoBadge status={a.status} /></td>
    </tr>
  );
}
