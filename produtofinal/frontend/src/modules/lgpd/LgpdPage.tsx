import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { KeyboardEvent } from "react";
import { useEffect, useRef, useState } from "react";
import type { Achado, AchadosLista, FiltrosLgpd } from "./api";
import { FILTROS_VAZIOS, correcoesApi, lgpdApi } from "./api";
import { AchadoModal } from "./AchadoModal";
import { CorrecaoModal } from "./CorrecaoModal";
import { CorrecoesPainel } from "./CorrecoesPainel";
import { NovaCorrecaoModal } from "./NovaCorrecaoModal";
import { PrioridadeTag, StatusAchadoBadge } from "./formato";
import { VarreduraPainel } from "./VarreduraPainel";
import { PageLede } from "@/shared/ui/PageLede";

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
          <table>
            <thead><tr>
              <th>Prioridade</th><th>Órgão</th><th>Dataset</th><th>Recurso</th><th>Tipo identificado</th>
              <th>Coluna</th><th>Linha</th><th>Confiança</th><th>Status</th>
            </tr></thead>
            <tbody>
              {lista.isError ? (
                <tr><td colSpan={9} style={{ padding: 18 }}>
                  <div className="inline-msg err" role="alert">Não foi possível carregar os achados: {lista.error.message}</div>
                </td></tr>
              ) : !dados ? (
                <tr><td colSpan={9} className="table-empty">Carregando…</td></tr>
              ) : dados.total === 0 ? (
                <tr><td colSpan={9} className="table-empty">
                  <i className="fa-solid fa-inbox" style={{ marginRight: 8 }} />
                  Nenhum possível dado pessoal encontrado até agora. Rode uma varredura no painel acima.
                </td></tr>
              ) : dados.achados.length === 0 ? (
                <tr><td colSpan={9} className="table-empty">Nenhum alerta para os filtros selecionados.</td></tr>
              ) : (
                dados.achados.map((a) => <Linha key={a.id} a={a} onAbrir={setAberto} />)
              )}
            </tbody>
          </table>
        </div>
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

function Linha({ a, onAbrir }: { a: Achado; onAbrir: (id: number) => void }) {
  const teclado = (e: KeyboardEvent<HTMLTableRowElement>) => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onAbrir(a.id); }
  };
  return (
    <tr tabIndex={0} onClick={() => onAbrir(a.id)} onKeyDown={teclado}>
      <td><PrioridadeTag prioridade={a.prioridade} /></td>
      <td title={a.orgao_nome ?? undefined}>{a.orgao_sigla ?? a.orgao_nome ?? "—"}</td>
      <td className="cell-strong">{a.dataset_titulo}</td>
      <td className="mono cell-muted">{a.recurso_nome ?? a.recurso_id}</td>
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
