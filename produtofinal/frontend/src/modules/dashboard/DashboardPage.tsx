import { useQuery } from "@tanstack/react-query";
import { Fragment, useState } from "react";
import { Link } from "react-router-dom";
import type { Alerta, Kpis, VisaoGeral } from "./api";
import { dashboardApi } from "./api";
import { BarrasHorizontais } from "./BarrasHorizontais";
import type { Fatia } from "./Rosca";
import { Rosca } from "./Rosca";
import { fmtData, fmtDataHora } from "@/modules/pda/formato";
import { SituacaoBadge } from "@/modules/pda/SituacaoBadge";
import { PageLede } from "@/shared/ui/PageLede";

const fmt = new Intl.NumberFormat("pt-BR");

// Cores de status do design system (sempre acompanhadas do rótulo da situação)
const COR_SITUACAO: Record<string, string> = {
  "Publicado": "var(--green-600)",
  "Em dia": "var(--green-600)",
  "Em atraso": "var(--red-600)",
  "Prazo vencido": "var(--gray-500)",
  "Próximo do prazo": "var(--amber-600)",
  "Não publicado": "var(--gray-500)",
  "Sem recurso": "var(--amber-600)",
};

// Status das atualizações (ADR-0020): cor de status + ícone + rótulo; "não se aplica" hachurado
const FATIA_ATUALIZACAO: Record<string, Omit<Fatia, "rotulo" | "total">> = {
  "Atualizado": { cor: "var(--green-600)", icone: "fa-circle-check" },
  "Próximo do vencimento": { cor: "var(--amber-600)", icone: "fa-clock" },
  "Atrasado": { cor: "var(--red-600)", icone: "fa-triangle-exclamation" },
  "Sem periodicidade definida": { cor: "var(--gray-500)", icone: "fa-minus", hachurada: true },
  "Sem informação": { cor: "var(--gray-500)", icone: "fa-circle-question" },
};
const AGUARDANDO_VINCULO = "Aguardando vínculo";

type Cor = "blue" | "green" | "amber" | "red";
type Pe = "ok" | "warn" | "bad" | "neutro";

interface Cartao {
  icone: string; cor: Cor; valor: number | null; rotulo: string; pe: string; classePe: Pe;
}

function cartoes(k: Kpis, plano: VisaoGeral["plano"]): Cartao[] {
  const pendente = (rotulo: string, icone: string, cor: Cor, motivo: string): Cartao =>
    ({ icone, cor, valor: null, rotulo, pe: motivo, classePe: "neutro" });
  return [
    { icone: "fa-building-columns", cor: "blue", valor: k.orgaos_monitorados, rotulo: "Órgãos monitorados",
      pe: `${fmt.format(k.orgaos_no_pda)} com bases no PDA vigente`, classePe: "ok" },
    { icone: "fa-clipboard-list", cor: "blue", valor: k.bases_previstas, rotulo: "Bases previstas no PDA",
      pe: plano ? plano.nome : "Nenhum PDA vigente", classePe: plano ? "ok" : "warn" },
    { icone: "fa-database", cor: "green", valor: k.datasets_publicados, rotulo: "Datasets publicados",
      pe: k.datasets_fora_do_portal
        ? `${fmt.format(k.datasets_fora_do_portal)} saíram do portal` : "Ativos no portal",
      classePe: k.datasets_fora_do_portal ? "warn" : "ok" },
    { icone: "fa-file-lines", cor: "blue", valor: k.recursos_monitorados, rotulo: "Recursos monitorados",
      pe: "Base: last_modified, sem dicionário", classePe: "ok" },
    k.bases_em_atraso == null
      ? pendente("Bases atrasadas", "fa-triangle-exclamation", "red", "Aguardando vínculo com o portal")
      : { icone: "fa-triangle-exclamation", cor: "red", valor: k.bases_em_atraso, rotulo: "Bases atrasadas",
          pe: `Entre ${fmt.format(k.bases_vinculadas)} base(s) vinculada(s)`,
          classePe: k.bases_em_atraso ? "bad" : "ok" },
    k.atualizacoes_em_atraso == null
      ? pendente("Atualizações em atraso", "fa-hourglass-half", "amber", "")
      : { icone: "fa-hourglass-half", cor: "amber", valor: k.atualizacoes_em_atraso, rotulo: "Atualizações em atraso",
          pe: "Acima da periodicidade do PDA", classePe: k.atualizacoes_em_atraso ? "warn" : "ok" },
    pendente("Possíveis dados pessoais", "fa-shield-halved", "red", ""),
    { icone: "fa-circle-question", cor: "amber", valor: k.datasets_sem_recurso, rotulo: "Datasets sem recurso",
      pe: "Dataset criado, sem arquivo", classePe: k.datasets_sem_recurso ? "warn" : "ok" },
  ];
}

function CartaoKpi({ c }: { c: Cartao }) {
  return (
    <div className="kpi-card">
      <div className="kpi-top">
        <div className={`kpi-icon ${c.cor}`}><i className={`fa-solid ${c.icone}`} /></div>
      </div>
      <div className={`kpi-value${c.valor == null ? " pendente" : ""}`}>
        {c.valor == null ? "—" : fmt.format(c.valor)}
      </div>
      <div className="kpi-label">{c.rotulo}</div>
      <div className={`kpi-foot ${c.classePe}`}>
        {c.pe ? <><i className="fa-solid fa-circle" style={{ fontSize: 5 }} />{c.pe}</> : " "}
      </div>
    </div>
  );
}

const FLUXO: [string, string][] = [
  ["fa-chart-simple", "Dashboard"], ["fa-building-columns", "Órgão"], ["fa-clipboard-check", "Base do PDA"],
  ["fa-database", "Dataset CKAN"], ["fa-file-lines", "Recurso"], ["fa-circle-check", "Status"],
  ["fa-triangle-exclamation", "Problema identificado"], ["fa-user-check", "Conferência humana"],
];

/**
 * Tela "Visão Geral" (US19/PBI-56) — referência visual: #screen-dashboard do Protótipo V1.
 * Cartões, bases do PDA vigente por situação, status das atualizações pela periodicidade do PDA
 * (ADR-0020) e alertas prioritários. Indicadores que dependem de regra ou módulo ainda não implementados
 * aparecem como "—" com o motivo, nunca como 0.
 */
export default function DashboardPage() {
  const dados = useQuery({ queryKey: ["painel", "visao-geral"], queryFn: dashboardApi.visaoGeral });
  const d = dados.data;

  return (
    <section className="screen">
      <PageLede titulo="Visão Geral">
        Monitoramento do Portal de Dados Abertos de Goiás — camada de governança externa ao CKAN, sem
        alteração dos dados publicados.
      </PageLede>

      <div className="layer-banner">
        <i className="fa-solid fa-circle-info" />
        <span>
          Este painel consolida o cumprimento do PDA, a atualização real dos recursos e sinalizações de
          possíveis dados pessoais para conferência humana.
          {d && <> Dados da coleta de <strong>{d.ultima_coleta ? fmtDataHora(d.ultima_coleta) : "—"}</strong>.</>}
        </span>
      </div>

      {dados.isError && (
        <div className="panel"><div className="panel-body">
          <div className="inline-msg err" role="alert">Não foi possível carregar a visão geral: {dados.error.message}</div>
        </div></div>
      )}
      {!d && !dados.isError && <div className="panel"><div className="panel-body cell-muted">Carregando…</div></div>}

      {d && (
        <>
          <div className="kpi-grid">
            {cartoes(d.kpis, d.plano).map((c) => <CartaoKpi key={c.rotulo} c={c} />)}
          </div>

          <div className="charts-row">
            <div className="panel" style={{ marginBottom: 0 }}>
              <div className="panel-head">
                <div>
                  <h3>Cumprimento do PDA por situação</h3>
                  <div className="sub">
                    {d.plano
                      ? `${fmt.format(d.kpis.bases_previstas)} bases previstas no ${d.plano.nome}`
                      : "Nenhum PDA vigente"}
                  </div>
                </div>
              </div>
              <div className="panel-body">
                {d.plano ? (
                  <>
                    <BarrasHorizontais rotuloAcessivel="Bases do PDA vigente por situação" unidade={["base", "bases"]}
                      barras={d.situacoes_pda.map((s) => ({ ...s, cor: COR_SITUACAO[s.rotulo] ?? "var(--gray-500)" }))} />
                    {d.kpis.bases_prazo_vencido > 0 && (
                      <p className="help-texto" style={{ marginTop: 12 }}>
                        “Prazo vencido” = base sem vínculo com o portal e meta já passada: o atraso só é confirmado
                        depois do vínculo ({fmt.format(d.kpis.bases_vinculadas)} de {fmt.format(d.kpis.bases_previstas)} vinculadas).
                      </p>
                    )}
                  </>
                ) : (
                  <p className="help-texto">Cadastre ou importe um PDA e defina-o como vigente.</p>
                )}
              </div>
            </div>

            <StatusAtualizacoes d={d} />
          </div>

          <Alertas d={d} />

          <div className="panel">
            <div className="panel-body">
              <h3 style={{ fontSize: 13.5, marginBottom: 12, color: "var(--gray-700)" }}>Fluxo de governança monitorado</h3>
              <div className="flow-strip">
                {FLUXO.map(([icone, rotulo], i) => (
                  <Fragment key={rotulo}>
                    <div className="flow-step"><i className={`fa-solid ${icone} step-ico`} />{rotulo}</div>
                    {i < FLUXO.length - 1 && <i className="fa-solid fa-chevron-right flow-arrow" />}
                  </Fragment>
                ))}
              </div>
            </div>
          </div>
        </>
      )}
    </section>
  );
}

function StatusAtualizacoes({ d }: { d: VisaoGeral }) {
  const aguardando = d.situacoes_atualizacao.find((c) => c.rotulo === AGUARDANDO_VINCULO)?.total ?? 0;
  const fatias: Fatia[] = d.situacoes_atualizacao
    .filter((c) => c.rotulo !== AGUARDANDO_VINCULO)
    .map((c) => ({ ...c, ...(FATIA_ATUALIZACAO[c.rotulo] ?? { cor: "var(--gray-500)", icone: "fa-circle" }) }));
  const avaliadas = fatias.reduce((s, f) => s + f.total, 0);
  return (
    <div className="panel" style={{ marginBottom: 0 }}>
      <div className="panel-head">
        <div>
          <h3>Status das atualizações</h3>
          <div className="sub">
            {fmt.format(avaliadas)} bases vinculadas do PDA vigente (periodicidade do PDA; base: last_modified)
          </div>
        </div>
      </div>
      <div className="panel-body">
        {avaliadas > 0 ? (
          <Rosca fatias={fatias} unidade={["base", "bases"]}
            rotuloAcessivel="Bases vinculadas do PDA vigente por status de atualização" />
        ) : (
          <p className="help-texto">Nenhuma base do PDA vigente vinculada a um dataset do portal.</p>
        )}
        <p className="help-texto" style={{ marginTop: 12 }}>
          Prazo pela periodicidade do PDA (Mensal = 30 dias, sem tolerância); “próximo do vencimento” a partir
          de 80% do prazo. Eventual e Estática não têm prazo fixo.
          {aguardando > 0 && ` ${fmt.format(aguardando)} base(s) aguardando vínculo não entram no gráfico.`}
          {d.atualizacao_estimada > 0 && ` ${fmt.format(d.atualizacao_estimada)} base(s) sem last_modified usam a data de criação.`}
        </p>
      </div>
    </div>
  );
}

function Situacao({ a }: { a: Alerta }) {
  if (a.tipo === "PDA") return <SituacaoBadge situacao={a.situacao} />;
  if (a.tipo === "Atualização") return <span className="badge badge-red">{a.situacao}</span>;
  return <span className="badge badge-amber">{a.situacao}</span>;
}

const TIPOS = ["PDA", "Atualização", "Inventário"] as const;
const NA_ABA_TODOS = 4; // "Todos" mostra os primeiros de cada tipo

function Alertas({ d }: { d: VisaoGeral }) {
  const [aba, setAba] = useState<string>("Todos");
  const linhas = aba === "Todos"
    ? TIPOS.flatMap((t) => d.alertas.filter((a) => a.tipo === t).slice(0, NA_ABA_TODOS))
      .sort((a, b) => d.alertas.indexOf(a) - d.alertas.indexOf(b))
    : d.alertas.filter((a) => a.tipo === aba);
  const total = aba === "Todos" ? d.total_alertas : (d.alertas_por_tipo[aba] ?? 0);
  const abas: [string, number][] = [["Todos", d.total_alertas], ...TIPOS.map((t): [string, number] => [t, d.alertas_por_tipo[t] ?? 0])];
  return (
    <div className="panel">
      <div className="panel-head">
        <div>
          <h3>Alertas prioritários</h3>
          <div className="sub">
            Itens que exigem conferência da equipe GEDA
            {total > linhas.length && ` · ${linhas.length} de ${fmt.format(total)}`}
          </div>
        </div>
        <Link className="btn btn-outline btn-sm" to="/pda">Ver monitoramento completo</Link>
      </div>
      <div className="abas-alerta" role="tablist" aria-label="Tipo de alerta">
        {abas.map(([nome, n]) => (
          <button key={nome} type="button" role="tab" aria-selected={aba === nome}
            className={`btn btn-sm ${aba === nome ? "btn-primary" : "btn-outline"}`} onClick={() => setAba(nome)}>
            {nome} <span className="abas-alerta-n">{fmt.format(n)}</span>
          </button>
        ))}
      </div>
      <div className="table-scroll" role="tabpanel">
        <table>
          <thead><tr><th>Órgão</th><th>Tipo</th><th>Base / Dataset</th><th>Situação</th><th>Prazo</th><th>Ação</th></tr></thead>
          <tbody>
            {linhas.length === 0 ? (
              <tr><td colSpan={6} className="table-empty">
                {aba === "PDA" || aba === "Todos"
                  ? "Nenhum alerta. Bases com prazo vencido e sem vínculo não entram aqui: o atraso ainda não foi confirmado."
                  : "Nenhum alerta deste tipo."}
              </td></tr>
            ) : linhas.map((a, i) => (
              <tr key={`${a.tipo}-${a.item}-${i}`}>
                <td>{a.orgao ?? "—"}</td>
                <td><span className="badge badge-blue">{a.tipo}</span></td>
                <td className="cell-strong">{a.item}</td>
                <td><Situacao a={a} /></td>
                <td className="cell-muted">{a.prazo ? fmtData(a.prazo) : "—"}</td>
                <td><Link className="row-link" to={a.destino}>Ver</Link></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
