import { useQuery } from "@tanstack/react-query";
import type { KeyboardEvent, ReactNode } from "react";
import { useRef } from "react";
import { Link, useSearchParams } from "react-router-dom";
import type { Alerta, DadosPessoais, Espontaneas, Kpis, VisaoGeral } from "./api";
import { dashboardApi } from "./api";
import { BarrasHorizontais } from "./BarrasHorizontais";
import type { Fatia } from "./Rosca";
import { Rosca } from "./Rosca";
import { fmtData, fmtDataHora } from "@/modules/pda/formato";
import { SituacaoBadge } from "@/modules/pda/SituacaoBadge";
import { Pode } from "@/shared/acesso/Pode";

const fmt = new Intl.NumberFormat("pt-BR");
/** Quantidade com singular/plural: qtd(1, "base", "bases") → "1 base". */
const qtd = (n: number, um: string, varios: string) => `${fmt.format(n)} ${n === 1 ? um : varios}`;
/** Percentual inteiro que não esconde valores pequenos: 0,3% vira "<1%", não "0%". */
const pctTexto = (parte: number, todo: number) => {
  if (!todo || !parte) return "0%";
  const p = (parte / todo) * 100;
  return p < 1 ? "<1%" : `${Math.round(p)}%`;
};

// Cores de status do design system (sempre acompanhadas do rótulo da situação). Cada situação tem
// um tom próprio: "Prazo vencido" (atraso não confirmado) é cinza escuro; "Não publicado", cinza claro.
const COR_SITUACAO: Record<string, string> = {
  "Publicado": "var(--green-600)",
  "Em dia": "var(--green-600)",
  "Em atraso": "var(--red-600)",
  "Prazo vencido": "var(--gray-700)",
  "Próximo do prazo": "var(--amber-400)",
  "Não publicado": "var(--gray-300)",
  "Sem recurso": "var(--amber-600)",
};

// Status das atualizações (ADR-0023): cor de status + ícone + rótulo; "não se aplica" hachurado
const FATIA_ATUALIZACAO: Record<string, Omit<Fatia, "rotulo" | "total">> = {
  "Atualizado": { cor: "var(--green-600)", icone: "fa-circle-check" },
  "Próximo do vencimento": { cor: "var(--amber-400)", icone: "fa-clock" },
  "Atrasado": { cor: "var(--red-600)", icone: "fa-triangle-exclamation" },
  "Sem periodicidade definida": { cor: "var(--gray-500)", icone: "fa-minus", hachurada: true },
  "Sem informação": { cor: "var(--gray-300)", icone: "fa-circle-question" },
};
const AGUARDANDO_VINCULO = "Aguardando vínculo";

/** Estado de um indicador de problema: a cor vem do valor, não do indicador. */
type Estado = "grave" | "atencao" | "ok" | "pendente";

interface Problema {
  rotulo: string; valor: number | null; nota: string; estado: Estado; destino: string;
}

/**
 * Indicadores que pedem ação. Com valor > 0 ganham a cor da gravidade; com 0 ficam verdes; sem
 * cálculo possível mostram "—" e o motivo (nunca 0). "Possíveis dados pessoais" só aparece para
 * quem tem lgpd.acessar (a API devolve null para os demais).
 */
function problemas(k: Kpis): Problema[] {
  const estado = (v: number | null, gravidade: "grave" | "atencao"): Estado =>
    v == null ? "pendente" : v > 0 ? gravidade : "ok";
  const lista: Problema[] = [
    { rotulo: "Bases atrasadas", valor: k.bases_em_atraso, estado: estado(k.bases_em_atraso, "grave"),
      nota: k.bases_em_atraso == null ? "Nenhuma base vinculada ao portal ainda"
        : `Entre ${qtd(k.bases_vinculadas, "base vinculada", "bases vinculadas")} ao portal`,
      destino: `/pda?situacao=${encodeURIComponent("Em atraso")}` },
    { rotulo: "Atualizações em atraso", valor: k.atualizacoes_em_atraso,
      estado: estado(k.atualizacoes_em_atraso, "atencao"),
      nota: k.atualizacoes_em_atraso == null ? "Nenhuma base vinculada ao portal ainda"
        : "Recurso sem atualização dentro da periodicidade do PDA",
      destino: "/atualizacoes" },
  ];
  if (k.possiveis_dados_pessoais != null) {
    lista.push({ rotulo: "Possíveis dados pessoais", valor: k.possiveis_dados_pessoais,
      estado: estado(k.possiveis_dados_pessoais, "grave"), nota: "Aguardando revisão humana", destino: "/lgpd" });
  }
  lista.push({ rotulo: "Datasets sem recurso", valor: k.datasets_sem_recurso,
    estado: estado(k.datasets_sem_recurso, "atencao"), nota: "Dataset criado no portal, sem arquivo",
    destino: "/datasets" });
  return lista;
}

function Problemas({ k }: { k: Kpis }) {
  return (
    <section className="painel-problemas" aria-labelledby="painel-problemas-titulo">
      <h2 id="painel-problemas-titulo" className="sr-only">Pontos que pedem conferência</h2>
      <ul>
        {problemas(k).map((p) => (
          <li key={p.rotulo}>
            <Link to={p.destino} className={`problema ${p.estado}`}>
              <span className="problema-rotulo">{p.rotulo}</span>
              <span className="problema-valor">{p.valor == null ? "—" : fmt.format(p.valor)}</span>
              <span className="problema-nota">{p.nota}</span>
              <i className="fa-solid fa-arrow-right problema-seta" aria-hidden="true" />
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** Números de inventário: contexto, não alerta. Ficam numa linha discreta abaixo dos problemas. */
function Inventario({ k, plano }: { k: Kpis; plano: VisaoGeral["plano"] }) {
  const itens: [string, number, ReactNode, boolean][] = [
    ["Órgãos monitorados", k.orgaos_monitorados, `${fmt.format(k.orgaos_no_pda)} com bases no PDA`, false],
    ["Bases previstas", k.bases_previstas, plano ? plano.nome : "Nenhum PDA vigente", !plano],
    ["Datasets publicados", k.datasets_publicados,
      k.datasets_fora_do_portal ? `${qtd(k.datasets_fora_do_portal, "saiu", "saíram")} do portal` : "Todos ativos no portal",
      k.datasets_fora_do_portal > 0],
    ["Recursos monitorados", k.recursos_monitorados, "Sem contar dicionários de dados", false],
  ];
  return (
    <dl className="painel-inventario" aria-label="Inventário monitorado">
      {itens.map(([rotulo, valor, detalhe, alerta]) => (
        <div key={rotulo}>
          <dt>{rotulo}</dt>
          <dd className="inventario-valor">{fmt.format(valor)}</dd>
          <dd className={`inventario-detalhe${alerta ? " alerta" : ""}`}>{detalhe}</dd>
        </div>
      ))}
    </dl>
  );
}

/** Explicações de cálculo, recolhidas por padrão. */
function ComoCalculamos({ children }: { children: ReactNode }) {
  return (
    <details className="como-calculamos">
      <summary>Como calculamos</summary>
      <div>{children}</div>
    </details>
  );
}

/**
 * Tela "Visão Geral" (US19/PBI-56). Ordem pensada para a rotina da GEDA: primeiro o que pede
 * conferência (indicadores de problema e alertas), depois o inventário e os gráficos de contexto.
 * Indicadores que dependem de regra ou módulo ainda não implementados aparecem como "—" com o
 * motivo, nunca como 0.
 */
export default function DashboardPage() {
  const dados = useQuery({ queryKey: ["painel", "visao-geral"], queryFn: dashboardApi.visaoGeral });
  const d = dados.data;

  return (
    <section className="screen painel">
      <p className="painel-lede">
        Cumprimento do PDA, atualização real dos recursos e possíveis dados pessoais no Portal de Dados
        Abertos de Goiás, monitorados fora do CKAN, sem alterar o que está publicado.
        {d?.ultima_coleta && (
          <span className="painel-coleta"> Dados da coleta de {fmtDataHora(d.ultima_coleta)}.</span>
        )}
      </p>

      {dados.isError && !d && (
        <div className="panel"><div className="panel-body painel-erro" role="alert">
          <p><strong>Não foi possível carregar a visão geral.</strong> Verifique a conexão e tente de novo;
            se continuar, avise o administrador do sistema.</p>
          <p className="help-texto">Detalhe técnico: {dados.error.message}</p>
          <button type="button" className="btn btn-outline btn-sm" onClick={() => dados.refetch()}
            disabled={dados.isFetching}>
            <i className="fa-solid fa-rotate-right" aria-hidden="true" />
            {dados.isFetching ? "Tentando…" : "Tentar novamente"}
          </button>
        </div></div>
      )}
      {!d && !dados.isError && <Esqueleto />}

      {d && (
        <>
          <Problemas k={d.kpis} />
          <Inventario k={d.kpis} plano={d.plano} />
          <Alertas d={d} />

          <div className="charts-row">
            <CumprimentoPda d={d} />
            <StatusAtualizacoes d={d} />
          </div>

          <div className={`charts-row${d.dados_pessoais ? "" : " um"}`}>
            <Pode permissao="lgpd.acessar">
              {d.dados_pessoais && <DadosPessoaisPainel p={d.dados_pessoais} />}
            </Pode>
            <EspontaneasPainel e={d.espontaneas} plano={d.plano} />
          </div>
        </>
      )}
    </section>
  );
}

/** Esqueleto com a forma da tela, enquanto os dados chegam. */
function Esqueleto() {
  return (
    <div className="painel-esqueleto" aria-busy="true" aria-live="polite">
      <span className="sr-only">Carregando a visão geral…</span>
      <div className="esq-linha esq-problemas" />
      <div className="esq-linha esq-inventario" />
      <div className="esq-linha esq-tabela" />
    </div>
  );
}

function CumprimentoPda({ d }: { d: VisaoGeral }) {
  return (
    <div className="panel" style={{ marginBottom: 0 }}>
      <div className="panel-head">
        <div>
          <h2>Cumprimento do PDA por situação</h2>
          <div className="sub">
            {d.plano
              ? `${qtd(d.kpis.bases_previstas, "base prevista", "bases previstas")} no ${d.plano.nome}`
              : "Nenhum PDA vigente"}
          </div>
        </div>
      </div>
      <div className="panel-body">
        {d.plano ? (
          <>
            <BarrasHorizontais rotuloAcessivel="Bases do PDA vigente por situação" unidade={["base", "bases"]}
              barras={d.situacoes_pda.map((s) => ({ ...s, cor: COR_SITUACAO[s.rotulo] ?? "var(--gray-500)" }))} />
            <ComoCalculamos>
              <p>
                “Em atraso” só vale para bases vinculadas a um dataset do portal ({fmt.format(d.kpis.bases_vinculadas)}{" "}
                de {fmt.format(d.kpis.bases_previstas)}). “Prazo vencido” é a base ainda sem vínculo cuja meta já
                passou: o atraso só se confirma depois do vínculo.
              </p>
            </ComoCalculamos>
          </>
        ) : (
          <p className="help-texto">
            Cadastre ou importe um PDA e defina-o como vigente na tela <Link to="/pda">Monitoramento do PDA</Link>.
          </p>
        )}
      </div>
    </div>
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
          <h2>Status das atualizações</h2>
          <div className="sub">
            {qtd(avaliadas, "base vinculada", "bases vinculadas")} ao portal
            {aguardando > 0 && ` · ${qtd(aguardando, "aguarda", "aguardam")} vínculo`}
          </div>
        </div>
        <Link className="btn btn-outline btn-sm" to="/atualizacoes">Ver atualizações</Link>
      </div>
      <div className="panel-body">
        {avaliadas > 0 ? (
          <Rosca fatias={fatias} unidade={["base", "bases"]}
            rotuloAcessivel="Bases vinculadas do PDA vigente por status de atualização" />
        ) : (
          <p className="help-texto">Nenhuma base do PDA vigente vinculada a um dataset do portal.</p>
        )}
        <ComoCalculamos>
          <p>
            O prazo segue a periodicidade do PDA (Mensal = 30 dias, sem tolerância), contado da última alteração
            do recurso no portal (<code>last_modified</code>). “Próximo do vencimento” começa em 80% do prazo.
            Eventual e Estática não têm prazo fixo.
          </p>
          {aguardando > 0 && (
            <p>{qtd(aguardando, "base aguardando vínculo não entra", "bases aguardando vínculo não entram")} no gráfico.</p>
          )}
          {d.atualizacao_estimada > 0 && (
            <p>
              {qtd(d.atualizacao_estimada, "base sem data de alteração usa", "bases sem data de alteração usam")}{" "}
              a data de criação.
            </p>
          )}
        </ComoCalculamos>
      </div>
    </div>
  );
}

function DadosPessoaisPainel({ p }: { p: DadosPessoais }) {
  const total = p.por_tipo.reduce((s, c) => s + c.total, 0);
  return (
    <div className="panel" style={{ marginBottom: 0 }}>
      <div className="panel-head">
        <div>
          <h2>Possíveis dados pessoais</h2>
          <div className="sub">
            {qtd(total, "achado", "achados")} em {fmt.format(p.recursos_com_achados)} de{" "}
            {qtd(p.recursos_analisados, "recurso analisado", "recursos analisados")}
          </div>
        </div>
        <Link className="btn btn-outline btn-sm" to="/lgpd">Ver dados pessoais</Link>
      </div>
      <div className="panel-body">
        {total > 0 ? (
          <BarrasHorizontais rotuloAcessivel="Possíveis dados pessoais por tipo" unidade={["achado", "achados"]}
            barras={p.por_tipo.map((c) => ({ ...c, cor: "var(--blue-500)" }))} />
        ) : (
          <p className="help-texto">
            {p.recursos_analisados ? "Nenhum possível dado pessoal nos recursos analisados."
              : <>Nenhum recurso analisado ainda: rode a varredura na tela <Link to="/lgpd">Dados Pessoais</Link>.</>}
          </p>
        )}
        <div className="status-triagem" role="group" aria-label="Situação da triagem">
          {p.por_status.map((c) => (
            <span key={c.rotulo}>{c.rotulo} <strong>{fmt.format(c.total)}</strong></span>
          ))}
        </div>
        <ComoCalculamos>
          <p>
            Por tipo, sem os descartados como falso positivo.{" "}
            {qtd(p.criticos, "achado de prioridade alta aguarda", "achados de prioridade alta aguardam")} revisão.
            Só contagens: o valor encontrado nunca é guardado.
          </p>
        </ComoCalculamos>
      </div>
    </div>
  );
}

function EspontaneasPainel({ e, plano }: { e: Espontaneas; plano: VisaoGeral["plano"] }) {
  return (
    <div className="panel" style={{ marginBottom: 0 }}>
      <div className="panel-head">
        <div>
          <h2>Bases espontâneas</h2>
          <div className="sub">
            {fmt.format(e.espontaneas)} de {qtd(e.datasets_no_portal, "dataset", "datasets")} do portal (
            {pctTexto(e.espontaneas, e.datasets_no_portal)}) sem base
            {plano ? ` no ${plano.nome}` : " no PDA (nenhum PDA vigente)"}
          </div>
        </div>
        <Link className="btn btn-outline btn-sm" to="/datasets">Ver datasets</Link>
      </div>
      <div className="panel-body">
        {e.espontaneas > 0 ? (
          <BarrasHorizontais rotuloAcessivel="Bases espontâneas por órgão" unidade={["base", "bases"]}
            barras={e.por_orgao.map((c) => ({ ...c, cor: "var(--blue-500)" }))} />
        ) : (
          <p className="help-texto">Todos os datasets ativos do portal estão vinculados a uma base do PDA vigente.</p>
        )}
        <ComoCalculamos>
          <p>
            Base espontânea é o dataset publicado no portal que nenhuma base do PDA vigente vincula pelo ID do CKAN
            ({qtd(e.no_pda, "está", "estão")} no PDA). Órgãos com mais espontâneas aparecem primeiro.
          </p>
        </ComoCalculamos>
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
const ABAS = ["Todos", ...TIPOS] as const;
type Aba = (typeof ABAS)[number];
const NA_ABA_TODOS = 4; // "Todos" mostra os mais urgentes de cada tipo
// Onde a lista completa de cada aba é tratada
const LISTA_COMPLETA: Record<Aba, [string, string]> = {
  "Todos": ["/pda", "Ver monitoramento do PDA"],
  "PDA": ["/pda", "Ver monitoramento do PDA"],
  "Atualização": ["/atualizacoes", "Ver atualizações"],
  "Inventário": ["/datasets", "Ver datasets"],
};

/**
 * Alertas prioritários com abas por tipo. A aba fica na URL (?alertas=PDA), sobrevive a recarregar
 * e ao voltar do navegador. Abas no padrão WAI-ARIA: setas, Home e End trocam de aba.
 */
function Alertas({ d }: { d: VisaoGeral }) {
  const [params, setParams] = useSearchParams();
  const pedida = params.get("alertas");
  const aba: Aba = (ABAS as readonly string[]).includes(pedida ?? "") ? (pedida as Aba) : "Todos";
  const refs = useRef<(HTMLButtonElement | null)[]>([]);

  const escolher = (nova: Aba) => {
    const p = new URLSearchParams(params);
    if (nova === "Todos") p.delete("alertas"); else p.set("alertas", nova);
    setParams(p, { replace: true });
  };
  const teclado = (e: KeyboardEvent<HTMLDivElement>) => {
    const i = ABAS.indexOf(aba);
    const destino = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: ABAS.length - 1 }[e.key];
    if (destino == null) return;
    e.preventDefault();
    const j = (destino + ABAS.length) % ABAS.length;
    escolher(ABAS[j]);
    refs.current[j]?.focus();
  };

  const linhas = aba === "Todos"
    ? TIPOS.flatMap((t) => d.alertas.filter((a) => a.tipo === t).slice(0, NA_ABA_TODOS))
      .sort((a, b) => d.alertas.indexOf(a) - d.alertas.indexOf(b))
    : d.alertas.filter((a) => a.tipo === aba);
  const total = aba === "Todos" ? d.total_alertas : (d.alertas_por_tipo[aba] ?? 0);
  const contagem = (nome: Aba) => (nome === "Todos" ? d.total_alertas : (d.alertas_por_tipo[nome] ?? 0));
  const mostraTipo = aba === "Todos";
  const [destinoLista, rotuloLista] = LISTA_COMPLETA[aba];

  return (
    <div className="panel painel-alertas">
      <div className="panel-head">
        <div>
          <h2 id="alertas-titulo">Alertas prioritários</h2>
          <div className="sub">
            {total === 0 ? "Nada pendente de conferência"
              : total > linhas.length
                ? `Os ${fmt.format(linhas.length)} mais urgentes de ${fmt.format(total)}`
                : qtd(total, "item pede conferência da GEDA", "itens pedem conferência da GEDA")}
          </div>
        </div>
        <Link className="btn btn-outline btn-sm" to={destinoLista}>{rotuloLista}</Link>
      </div>
      <div className="abas-alerta" role="tablist" aria-labelledby="alertas-titulo" onKeyDown={teclado}>
        {ABAS.map((nome, i) => (
          <button key={nome} type="button" role="tab" id={`alertas-aba-${i}`} aria-controls="alertas-painel"
            aria-selected={aba === nome} tabIndex={aba === nome ? 0 : -1}
            ref={(el) => { refs.current[i] = el; }}
            className={`btn btn-sm ${aba === nome ? "btn-primary" : "btn-outline"}`} onClick={() => escolher(nome)}>
            {nome} <span className="abas-alerta-n">{fmt.format(contagem(nome))}</span>
          </button>
        ))}
      </div>
      <div className="table-scroll" role="tabpanel" id="alertas-painel"
        aria-labelledby={`alertas-aba-${ABAS.indexOf(aba)}`}>
        <table>
          <thead>
            <tr>
              <th>Órgão</th>{mostraTipo && <th>Tipo</th>}<th>Base / Dataset</th><th>Situação</th><th>Prazo</th>
              <th><span className="sr-only">Ação</span></th>
            </tr>
          </thead>
          <tbody>
            {linhas.length === 0 ? (
              <tr><td colSpan={mostraTipo ? 6 : 5} className="table-empty">
                {aba === "PDA" || aba === "Todos"
                  ? "Nenhum alerta. Bases com prazo vencido e sem vínculo não entram aqui: o atraso ainda não foi confirmado."
                  : "Nenhum alerta deste tipo."}
              </td></tr>
            ) : linhas.map((a, i) => (
              <tr key={`${a.tipo}-${a.item}-${i}`}>
                <td>{a.orgao ?? <span className="cell-muted">Órgão não identificado</span>}</td>
                {mostraTipo && <td><span className="badge badge-blue">{a.tipo}</span></td>}
                <td className="cell-strong">{a.item}</td>
                <td><Situacao a={a} /></td>
                <td className="cell-muted">{a.prazo ? fmtData(a.prazo) : "Sem prazo"}</td>
                <td>
                  <Link className="row-link" to={a.destino}>
                    Abrir<span className="sr-only">: {a.item}</span>
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
