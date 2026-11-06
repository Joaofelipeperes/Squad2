import { useQuery } from "@tanstack/react-query";
import type { KeyboardEvent, ReactNode } from "react";
import { useMemo, useState } from "react";
import type { CriterioAtencao, Organizacao } from "./api";
import { organizacoesApi } from "./api";
import { OrganizacaoDetalheModal } from "./OrganizacaoDetalheModal";
import type { ColunaExportacao } from "@/shared/ui/ExportarTabela";
import { ExportarTabela, descreverFiltros } from "@/shared/ui/ExportarTabela";
import { PageLede } from "@/shared/ui/PageLede";
import type { Ordenadores } from "@/shared/ui/tabela";
import { ColunaOrdenavel, Paginacao, useTabela } from "@/shared/ui/tabela";

type Coluna = "orgao" | "previstas" | "publicadas" | "atraso" | "atualizacao" | "lgpd" | "atencao";

const ORDENADORES: Ordenadores<Organizacao, Coluna> = {
  orgao: (o) => o.nome,
  previstas: (o) => o.bases_previstas,
  publicadas: (o) => (o.bases_vinculadas > 0 ? o.bases_publicadas : null),
  atraso: (o) => o.bases_em_atraso,
  atualizacao: (o) => o.atualizacao_pct,
  lgpd: (o) => o.riscos_lgpd,
  atencao: (o) => o.indice_atencao_valor,
};

/**
 * Tela "Organizações" (US19) — referência visual: #screen-organizations do Protótipo V1.
 * Bases vêm do PDA vigente; datasets e formatos, do inventário do portal; riscos LGPD, das
 * varreduras de dados pessoais; o índice de atenção combina risco LGPD e atraso de atualização
 * (ADR-0030). Indicadores que ainda dependem do vínculo PDA × portal ou de varredura aparecem como
 * pendentes, não como 0.
 */
export default function OrganizacoesPage() {
  const dados = useQuery({ queryKey: ["painel", "organizacoes"], queryFn: organizacoesApi.lista });
  const [detalhe, setDetalhe] = useState<Organizacao | null>(null);
  const [filtros, setFiltros] = useState<FiltrosOrganizacoes>(FILTROS_VAZIOS);
  const d = dados.data;
  // A lista vem inteira (um registro por órgão, poucas dezenas): o filtro é feito na própria tela.
  const visiveis = useMemo(() => (d ? d.organizacoes.filter((o) => atende(o, filtros)) : []), [d, filtros]);

  const set = (campo: keyof FiltrosOrganizacoes) => (valor: string) => setFiltros((f) => ({ ...f, [campo]: valor }));
  const tabela = useTabela(visiveis, ORDENADORES);
  const col = { ordem: tabela.ordem, onOrdenar: tabela.ordenarPor };

  return (
    <section className="screen">
      <PageLede titulo="Organizações">
        Situação consolidada de cumprimento do PDA por órgão publicador.
      </PageLede>

      <div className="panel">
        <div className="filters-bar">
          <div className="search-field">
            <i className="fa-solid fa-magnifying-glass" />
            <input type="text" className="text-input" aria-label="Buscar por nome ou sigla do órgão"
                   placeholder="Buscar por nome ou sigla do órgão..." value={filtros.busca}
                   onChange={(e) => set("busca")(e.target.value)} />
          </div>
          <Filtro id="org-filtro-atraso" rotulo="Em atraso" valor={filtros.atraso} onMudar={set("atraso")}
            opcoes={OPCOES_ATRASO} />
          <Filtro id="org-filtro-pda" rotulo="Bases no PDA" valor={filtros.pda} onMudar={set("pda")}
            opcoes={OPCOES_PDA} />
          <Filtro id="org-filtro-portal" rotulo="Organização no portal" valor={filtros.portal}
            onMudar={set("portal")} opcoes={OPCOES_PORTAL} />
          <Filtro id="org-filtro-atencao" rotulo="Índice de atenção" valor={filtros.atencao}
            onMudar={set("atencao")} opcoes={OPCOES_ATENCAO} />
          <div className="filter-actions">
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setFiltros(FILTROS_VAZIOS)}>
              Limpar filtros</button>
            {d && (
              <ExportarTabela titulo="Organizações" colunas={exportacao(d.lgpd_visivel)} linhas={tabela.todas}
                filtros={descreverFiltros([
                  ["PDA", d.plano?.nome], ["Busca", filtros.busca],
                  ["Em atraso", rotulo(OPCOES_ATRASO, filtros.atraso)],
                  ["Bases no PDA", rotulo(OPCOES_PDA, filtros.pda)],
                  ["Organização no portal", rotulo(OPCOES_PORTAL, filtros.portal)],
                  ["Índice de atenção", rotulo(OPCOES_ATENCAO, filtros.atencao)]])} />
            )}
          </div>
        </div>
        <div className="panel-head" style={{ borderBottom: "none", paddingBottom: 0 }}>
          <div className="sub" style={{ fontSize: 12.5 }} aria-live="polite">
            {d && (d.plano
              ? <>Bases do PDA vigente: <strong>{d.plano.nome}</strong></>
              : "Nenhum PDA vigente: as colunas de bases ficam zeradas até um PDA ser cadastrado.")}
          </div>
        </div>
        <div className="table-scroll">
          <table>
            <thead><tr>
              <ColunaOrdenavel coluna="orgao" {...col}>Órgão</ColunaOrdenavel>
              <ColunaOrdenavel coluna="previstas" primeira="desc" {...col}>Bases previstas</ColunaOrdenavel>
              <ColunaOrdenavel coluna="publicadas" primeira="desc" {...col}>Bases publicadas</ColunaOrdenavel>
              <ColunaOrdenavel coluna="atraso" primeira="desc" {...col}
                title="Bases vinculadas com prazo vencido e sem publicação no portal">Em atraso</ColunaOrdenavel>
              <ColunaOrdenavel coluna="atualizacao" {...col}>Atualização</ColunaOrdenavel>
              <ColunaOrdenavel coluna="lgpd" primeira="desc" {...col}
                title="Recursos com possível dado pessoal aguardando revisão ou confirmado, entre os varridos">
                Riscos LGPD</ColunaOrdenavel>
              <ColunaOrdenavel coluna="atencao" primeira="desc" {...col}
                title="Média ponderada do risco LGPD e do atraso de atualização (pesos em Parâmetros)">
                Índice de atenção</ColunaOrdenavel>
            </tr></thead>
            <tbody>
              {dados.isError ? (
                <tr><td colSpan={7} style={{ padding: 18 }}>
                  <div className="inline-msg err" role="alert">
                    Não foi possível carregar as organizações: {dados.error.message}
                  </div>
                </td></tr>
              ) : !d ? (
                <tr><td colSpan={7} className="table-empty">Carregando…</td></tr>
              ) : d.organizacoes.length === 0 ? (
                <tr><td colSpan={7} className="table-empty">
                  Nenhum órgão no inventário: rode a coleta pelo botão "Atualizar dados".
                </td></tr>
              ) : visiveis.length === 0 ? (
                <tr><td colSpan={7} className="table-empty">Nenhum órgão encontrado.</td></tr>
              ) : (
                tabela.itens.map((o) => (
                  <Linha key={o.chave} o={o} onAbrir={setDetalhe} lgpdVisivel={d.lgpd_visivel}
                    criterio={d.criterio_atencao} />
                ))
              )}
            </tbody>
          </table>
        </div>
        {d && (
          <Paginacao id="org" {...tabela.paginacao}
            resumo={visiveis.length === d.organizacoes.length
              ? <><strong>{d.organizacoes.length}</strong> órgão(s)</>
              : <><strong>{visiveis.length}</strong> de {d.organizacoes.length} órgão(s)</>} />
        )}
        <div className="panel-body" style={{ paddingTop: 10 }}>
          <p className="help-texto">
            <Pendente>aguardando vínculo</Pendente> depende de ligar as bases do PDA aos datasets do portal
            (pelo ID). <Pendente>não varrido</Pendente>: nenhum recurso do órgão passou pela varredura de
            dados pessoais.
          </p>
          <p className="help-texto">
            Em atraso conta só bases vinculadas cujo prazo venceu sem publicação: sem o vínculo não há como
            saber se a base já está no portal.
          </p>
          <p className="help-texto">
            Atualização: % das bases vinculadas que estão dentro do prazo da periodicidade do PDA (Mensal = 30
            dias, sem tolerância). Bases Eventual ou Estática e as sem data de atualização não entram na conta.
          </p>
          <p className="help-texto">
            Riscos LGPD: recursos com possível dado pessoal aguardando revisão ou confirmado (falso positivo e
            tratado não contam), entre os recursos do órgão já varridos.
          </p>
          {d && (
            <p className="help-texto">
              Índice de atenção (0 a 100): média ponderada do risco LGPD (% dos recursos varridos com possível
              dado pessoal, peso {d.criterio_atencao.peso_lgpd}) e do atraso de atualização (% das bases
              avaliadas que estão atrasadas, peso {d.criterio_atencao.peso_atualizacao}). Médio a partir
              de {d.criterio_atencao.limite_medio}, Alto a partir de {d.criterio_atencao.limite_alto}. Sem um
              dos dois, o índice usa só o outro. Pesos e faixas ficam em Parâmetros.
            </p>
          )}
        </div>
      </div>

      {d && (
        <OrganizacaoDetalheModal key={detalhe?.chave} org={detalhe} formatosAbertos={d.formatos_abertos}
          lgpdVisivel={d.lgpd_visivel} criterio={d.criterio_atencao} onFechar={() => setDetalhe(null)} />
      )}
    </section>
  );
}

interface FiltrosOrganizacoes {
  busca: string;
  atraso: string; // "" | "com" | "sem" | "proximas" | "aguardando"
  pda: string; // "" | "com" | "sem"
  portal: string; // "" | "com" | "sem"
  atencao: string; // "" | "Alto" | "Médio" | "Baixo" | "sem"
}

const FILTROS_VAZIOS: FiltrosOrganizacoes = { busca: "", atraso: "", pda: "", portal: "", atencao: "" };

const OPCOES_ATRASO = [
  { valor: "com", rotulo: "Com bases em atraso" },
  { valor: "sem", rotulo: "Sem atraso (entre as vinculadas)" },
  { valor: "proximas", rotulo: "Com bases próximas do prazo" },
  { valor: "aguardando", rotulo: "Aguardando vínculo" },
];
const OPCOES_PDA = [
  { valor: "com", rotulo: "Com bases previstas" },
  { valor: "sem", rotulo: "Sem bases previstas" },
];
const OPCOES_PORTAL = [
  { valor: "com", rotulo: "Com organização no portal" },
  { valor: "sem", rotulo: "Sem organização no portal" },
];
const OPCOES_ATENCAO = [
  { valor: "Alto", rotulo: "Alto" },
  { valor: "Médio", rotulo: "Médio" },
  { valor: "Baixo", rotulo: "Baixo" },
  { valor: "sem", rotulo: "Sem dados" },
];

const rotulo = (opcoes: { valor: string; rotulo: string }[], valor: string) =>
  opcoes.find((o) => o.valor === valor)?.rotulo ?? null;

/** Colunas do Excel/PDF: as da tabela, com os valores como a tela mostra (Riscos LGPD só com acesso). */
function exportacao(lgpdVisivel: boolean): ColunaExportacao<Organizacao>[] {
  return [
    { titulo: "Órgão", valor: (o) => o.nome },
    { titulo: "Siglas no PDA", valor: (o) => o.siglas.join(", ") || "—" },
    { titulo: "Bases previstas", valor: (o) => o.bases_previstas },
    { titulo: "Bases publicadas",
      valor: (o) => (o.bases_vinculadas > 0 ? `${o.bases_publicadas} de ${o.bases_vinculadas} vinculada(s)` : "aguardando vínculo") },
    { titulo: "Em atraso", valor: (o) => (o.bases_em_atraso == null ? "aguardando vínculo" : o.bases_em_atraso) },
    { titulo: "Atualização (% no prazo)",
      valor: (o) => (o.atualizacao_pct != null ? `${o.atualizacao_pct}%`
        : o.bases_vinculadas === 0 ? "aguardando vínculo" : "sem prazo definido") },
    ...(lgpdVisivel ? [{ titulo: "Riscos LGPD (recursos varridos)",
      valor: (o: Organizacao) => (o.riscos_lgpd == null ? "não varrido" : `${o.riscos_lgpd} de ${o.lgpd_recursos_analisados}`) }] : []),
    { titulo: "Índice de atenção",
      valor: (o) => (o.indice_atencao ? `${o.indice_atencao} (${o.indice_atencao_valor})` : "sem dados") },
  ];
}

/** Busca sem diferenciar maiúsculas nem acentos ("saude" acha "Saúde"). */
function normalizar(t: string) {
  return t.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
}

function atende(o: Organizacao, f: FiltrosOrganizacoes) {
  const termo = normalizar(f.busca);
  if (termo && ![o.nome, ...o.siglas].some((t) => normalizar(t).includes(termo))) return false;
  if (f.atraso === "com" && !(o.bases_em_atraso != null && o.bases_em_atraso > 0)) return false;
  if (f.atraso === "sem" && o.bases_em_atraso !== 0) return false;
  if (f.atraso === "proximas" && o.bases_proximas_do_prazo === 0) return false;
  if (f.atraso === "aguardando" && o.bases_em_atraso != null) return false;
  if (f.pda === "com" && o.bases_previstas === 0) return false;
  if (f.pda === "sem" && o.bases_previstas > 0) return false;
  if (f.portal === "com" && o.organizacao_id == null) return false;
  if (f.portal === "sem" && o.organizacao_id != null) return false;
  if (f.atencao === "sem" ? o.indice_atencao != null : f.atencao && o.indice_atencao !== f.atencao) return false;
  return true;
}

function Filtro({ id, rotulo, valor, opcoes, onMudar }: {
  id: string; rotulo: string; valor: string; opcoes: { valor: string; rotulo: string }[];
  onMudar: (v: string) => void;
}) {
  return (
    <div className="filter-field">
      <label htmlFor={id}>{rotulo}</label>
      <select id={id} value={valor} onChange={(e) => onMudar(e.target.value)}>
        <option value="">Todos</option>
        {opcoes.map((o) => <option key={o.valor} value={o.valor}>{o.rotulo}</option>)}
      </select>
    </div>
  );
}

/** Ressalva para as bases sem vínculo: não há como conferir se já foram publicadas. */
export const NAO_CONFIRMADO = "Publicação ainda não confirmada: aguardando vínculo";

/** Indicador ainda não calculável: badge cinza com o motivo. */
export function Pendente({ children }: { children: ReactNode }) {
  return <span className="badge badge-gray" style={{ fontWeight: 500 }}>{children}</span>;
}

function Linha({ o, onAbrir, lgpdVisivel, criterio }: {
  o: Organizacao; onAbrir: (o: Organizacao) => void; lgpdVisivel: boolean; criterio: CriterioAtencao;
}) {
  const teclado = (e: KeyboardEvent<HTMLTableRowElement>) => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onAbrir(o); }
  };
  const semOrgao = o.organizacao_id == null;
  const semConfirmacao = o.bases_vinculadas < o.bases_previstas;
  return (
    <tr tabIndex={0} onClick={() => onAbrir(o)} onKeyDown={teclado}>
      <td className="cell-strong">
        {o.nome}
        {!semOrgao && o.siglas.length > 0 && (
          <span className="cell-muted mono" style={{ marginLeft: 4 }}>({o.siglas.join(", ")})</span>
        )}
        {semOrgao && (
          <>{" "}<span className="badge badge-amber" title="Sigla do PDA sem correspondência com organização do portal">
            sem organização no portal</span></>
        )}
      </td>
      <td>{o.bases_previstas}</td>
      <td>{o.bases_vinculadas > 0 ? `${o.bases_publicadas} de ${o.bases_vinculadas} vinculada(s)` : <Pendente>aguardando vínculo</Pendente>}</td>
      <td>
        {o.bases_em_atraso == null
          ? <Pendente>aguardando vínculo</Pendente>
          : <span className={`badge ${o.bases_em_atraso > 0 ? "badge-red" : "badge-green"}`}
              title={semConfirmacao ? `Entre as ${o.bases_vinculadas} base(s) vinculada(s). ${NAO_CONFIRMADO} nas demais.` : undefined}>
              {o.bases_em_atraso}{semConfirmacao ? ` de ${o.bases_vinculadas} vinculada(s)` : ""}
            </span>}
      </td>
      <td><Atualizacao o={o} /></td>
      <td><RiscosLgpd o={o} visivel={lgpdVisivel} /></td>
      <td><IndiceAtencao o={o} criterio={criterio} /></td>
    </tr>
  );
}

/** Coluna Atualização: % dentro do prazo pela periodicidade do PDA vigente (ADR-0023). */
function Atualizacao({ o }: { o: Organizacao }) {
  if (o.atualizacao_pct == null) {
    return o.bases_vinculadas === 0
      ? <Pendente>aguardando vínculo</Pendente>
      : <Pendente>sem prazo definido</Pendente>;
  }
  const atrasadas = o.atualizacoes_atrasadas ?? 0;
  const classe = atrasadas === 0 ? "badge-green" : o.atualizacao_pct >= 50 ? "badge-amber" : "badge-red";
  return (
    <span className={`badge ${classe}`}
      title={`${o.atualizacoes_avaliadas - atrasadas} de ${o.atualizacoes_avaliadas} base(s) com prazo dentro da periodicidade do PDA; ${atrasadas} atrasada(s)`}>
      {o.atualizacao_pct}%
    </span>
  );
}

/** Riscos LGPD: recursos com achado em aberto entre os varridos (só com lgpd.acessar). */
export function RiscosLgpd({ o, visivel }: { o: Organizacao; visivel: boolean }) {
  if (!visivel) {
    return <span title="Disponível para quem tem acesso ao módulo de dados pessoais"><Pendente>sem acesso</Pendente></span>;
  }
  if (o.riscos_lgpd == null) {
    return <span title="Nenhum recurso do órgão passou pela varredura de dados pessoais"><Pendente>não varrido</Pendente></span>;
  }
  return (
    <span className={`badge ${o.riscos_lgpd > 0 ? "badge-amber" : "badge-green"}`}
      title={`${o.riscos_lgpd} de ${o.lgpd_recursos_analisados} recurso(s) varrido(s) com possível dado pessoal em aberto: `
        + `${o.lgpd_aguardando_revisao} achado(s) aguardando revisão, ${o.lgpd_confirmados} confirmado(s)`}>
      {o.riscos_lgpd} de {o.lgpd_recursos_analisados}
    </span>
  );
}

const CLASSE_ATENCAO = { Alto: "badge-red", Médio: "badge-amber", Baixo: "badge-green" } as const;

/** Como o índice foi calculado, em texto (dica da coluna e detalhe do órgão). */
export function explicarIndice(o: Organizacao, c: CriterioAtencao): string {
  const partes = [
    o.indice_atencao_componentes.includes("Risco LGPD") ? `risco LGPD ${o.risco_lgpd_pct}% (peso ${c.peso_lgpd})` : null,
    o.indice_atencao_componentes.includes("Atraso de atualização")
      ? `atraso de atualização ${o.atraso_atualizacao_pct}% (peso ${c.peso_atualizacao})` : null,
  ].filter(Boolean);
  return `Média ponderada de ${partes.join(" e ")} = ${o.indice_atencao_valor}. `
    + `Médio a partir de ${c.limite_medio}, Alto a partir de ${c.limite_alto}.`;
}

/** Índice de atenção (ADR-0030): faixa e valor de 0 a 100. */
export function IndiceAtencao({ o, criterio }: { o: Organizacao; criterio: CriterioAtencao }) {
  if (!o.indice_atencao) {
    return (
      <span title="Sem risco LGPD (nenhum recurso varrido) e sem atualização avaliada (nenhuma base vinculada com prazo)">
        <Pendente>sem dados</Pendente>
      </span>
    );
  }
  return (
    <span className={`badge ${CLASSE_ATENCAO[o.indice_atencao]}`} title={explicarIndice(o, criterio)}>
      {o.indice_atencao} · {o.indice_atencao_valor}
    </span>
  );
}
