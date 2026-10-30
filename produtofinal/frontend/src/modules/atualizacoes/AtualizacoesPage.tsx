import { useQuery } from "@tanstack/react-query";
import type { KeyboardEvent } from "react";
import { useEffect, useState } from "react";
import type { AtualizacaoLinha, AtualizacoesLista, FiltrosAtualizacoes } from "./api";
import { FILTROS_VAZIOS, atualizacoesApi } from "./api";
import { DatasetDetalheModal } from "@/modules/datasets/DatasetDetalheModal";
import { fmtData, fmtDataHora } from "@/modules/pda/formato";
import { PageLede } from "@/shared/ui/PageLede";

/**
 * Tela "Monitoramento de Atualizações" (US9/US10) — referência visual: #screen-updates do
 * Protótipo V1. Datasets vinculados às bases do PDA vigente; a situação usa a periodicidade do
 * PDA e o `last_modified` do RECURSO (ADR-0023), nunca o `metadata_modified` do dataset.
 */
export default function AtualizacoesPage() {
  const [filtros, setFiltros] = useState<FiltrosAtualizacoes>(FILTROS_VAZIOS);
  const [busca, setBusca] = useState("");
  const [detalhe, setDetalhe] = useState<number | null>(null);

  // A busca por dataset é enviada ao backend com uma pequena espera, para não consultar a cada tecla.
  useEffect(() => {
    const t = setTimeout(() => setFiltros((f) => (f.dataset === busca ? f : { ...f, dataset: busca })), 300);
    return () => clearTimeout(t);
  }, [busca]);

  const lista = useQuery({
    queryKey: ["atualizacoes", "datasets", filtros],
    queryFn: () => atualizacoesApi.lista(filtros),
    placeholderData: (anterior: AtualizacoesLista | undefined) => anterior,
  });

  const set = (campo: keyof FiltrosAtualizacoes) => (valor: string) => setFiltros((f) => ({ ...f, [campo]: valor }));
  const limpar = () => { setBusca(""); setFiltros(FILTROS_VAZIOS); };
  const dados = lista.data;

  return (
    <section className="screen">
      <PageLede titulo="Monitoramento de Atualizações">
        Avaliação da atualização real do conteúdo dos recursos publicados.
      </PageLede>

      <div className="layer-banner">
        <i className="fa-solid fa-circle-info" />
        <span>
          O sistema utiliza a data de atualização do recurso <code>last_modified</code> para avaliar a atualização
          real do conteúdo. O campo <code>metadata_modified</code> não é utilizado como indicador, pois reflete
          apenas alterações de metadados no CKAN.
        </span>
      </div>

      {dados && dados.plano_nome === null && (
        <div className="inline-msg err" role="status" style={{ marginBottom: 18 }}>
          Não há PDA vigente: a periodicidade de cada dataset vem do PDA. Importe ou defina um PDA vigente
          em "Monitoramento PDA".
        </div>
      )}

      <div className="kpi-grid">
        <Cartao cor="green" icone="fa-check" valor={dados?.resumo.atualizados} rotulo="Atualizados no período" />
        <Cartao cor="red" icone="fa-triangle-exclamation" valor={dados?.resumo.atrasados} rotulo="Em atraso" />
        <Cartao cor="amber" icone="fa-hourglass-half" valor={dados?.resumo.proximos_do_vencimento}
          rotulo="Próximos do vencimento" />
        <Cartao cor="blue" icone="fa-circle-question" valor={dados?.resumo.sem_informacao}
          rotulo="Sem periodicidade definida" />
      </div>

      <div className="panel">
        <div className="filters-bar">
          <div className="search-field">
            <i className="fa-solid fa-magnifying-glass" />
            <input type="text" className="text-input" aria-label="Buscar por nome do dataset"
                   placeholder="Buscar por nome do dataset..." value={busca}
                   onChange={(e) => setBusca(e.target.value)} />
          </div>
          <Filtro id="at-filtro-orgao" rotulo="Órgão" valor={filtros.orgao} onMudar={set("orgao")}
            opcoes={dados?.opcoes.orgaos ?? []} classe="filter-field-limitado" />
          <Filtro id="at-filtro-periodicidade" rotulo="Periodicidade" valor={filtros.periodicidade}
            onMudar={set("periodicidade")}
            opcoes={(dados?.opcoes.periodicidades ?? []).map((p) => ({ valor: p, rotulo: p }))} />
          <Filtro id="at-filtro-situacao" rotulo="Situação" valor={filtros.situacao} onMudar={set("situacao")}
            opcoes={(dados?.opcoes.situacoes ?? []).map((s) => ({ valor: s, rotulo: s }))} />
          <div className="filter-actions">
            <button type="button" className="btn btn-ghost btn-sm" onClick={limpar}>Limpar filtros</button>
          </div>
        </div>
        <div className="panel-head" style={{ borderBottom: "none", paddingBottom: 0 }}>
          <div className="sub" style={{ fontSize: 12.5 }} aria-live="polite">
            {dados ? `${dados.datasets.length} dataset(s) encontrado(s) de ${dados.total} monitorados${dados.plano_nome ? ` no ${dados.plano_nome}` : ""}`
              : lista.isError ? "" : "Carregando…"}
            {lista.isPlaceholderData && " · atualizando…"}
          </div>
        </div>
        <div className="table-scroll">
          <table>
            <thead><tr>
              <th>Dataset</th><th>Órgão</th><th>Periodicidade</th><th>Último recurso atualizado</th>
              <th>Dias desde atualização</th><th>Prazo esperado</th><th>Situação</th>
            </tr></thead>
            <tbody>
              {lista.isError ? (
                <tr><td colSpan={7} style={{ padding: 18 }}>
                  <div className="inline-msg err" role="alert">
                    Não foi possível carregar as atualizações: {lista.error.message}
                  </div>
                </td></tr>
              ) : !dados ? (
                <tr><td colSpan={7} className="table-empty">Carregando…</td></tr>
              ) : dados.total === 0 ? (
                <tr><td colSpan={7} className="table-empty">
                  <i className="fa-solid fa-inbox" style={{ marginRight: 8 }} />
                  Nenhum dataset vinculado ao PDA vigente para monitorar.
                </td></tr>
              ) : dados.datasets.length === 0 ? (
                <tr><td colSpan={7} className="table-empty">Nenhum registro para os filtros selecionados.</td></tr>
              ) : (
                dados.datasets.map((d) => <Linha key={d.base_id} d={d} onAbrir={setDetalhe} />)
              )}
            </tbody>
          </table>
        </div>
      </div>

      <DatasetDetalheModal datasetId={detalhe} onFechar={() => setDetalhe(null)} />
    </section>
  );
}

function Cartao({ cor, icone, valor, rotulo }: { cor: string; icone: string; valor?: number; rotulo: string }) {
  return (
    <div className="kpi-card">
      <div className="kpi-top"><div className={`kpi-icon ${cor}`}><i className={`fa-solid ${icone}`} /></div></div>
      <div className="kpi-value">{valor ?? "—"}</div>
      <div className="kpi-label">{rotulo}</div>
    </div>
  );
}

function Filtro({ id, rotulo, valor, opcoes, onMudar, classe }: {
  id: string; rotulo: string; valor: string; opcoes: { valor: string; rotulo: string }[];
  onMudar: (v: string) => void; classe?: string;
}) {
  return (
    <div className={classe ? `filter-field ${classe}` : "filter-field"}>
      <label htmlFor={id}>{rotulo}</label>
      <select id={id} value={valor} onChange={(e) => onMudar(e.target.value)}>
        <option value="">Todos</option>
        {opcoes.map((o) => <option key={o.valor} value={o.valor}>{o.rotulo}</option>)}
      </select>
    </div>
  );
}

const CLASSE_SITUACAO: Record<string, string> = {
  "Atualizado": "badge-green",
  "Próximo do vencimento": "badge-amber",
  "Atrasado": "badge-red",
};

function Linha({ d, onAbrir }: { d: AtualizacaoLinha; onAbrir: (id: number) => void }) {
  const teclado = (e: KeyboardEvent<HTMLTableRowElement>) => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onAbrir(d.dataset_id); }
  };
  return (
    <tr tabIndex={0} onClick={() => onAbrir(d.dataset_id)} onKeyDown={teclado}>
      <td className="cell-strong" title={d.dataset_name ?? undefined}>{d.dataset_titulo}</td>
      <td title={d.orgao_nome ?? undefined}>{d.orgao_sigla}</td>
      <td>{d.periodicidade}</td>
      <td className="cell-muted">
        {fmtDataHora(d.ultima_atualizacao)}
        {d.ultima_atualizacao && d.ultima_atualizacao_estimada && (
          <span title="Estimada pela data de criação do recurso (sem last_modified)"> (est.)</span>
        )}
      </td>
      <td className="cell-muted">{d.dias_desde_atualizacao != null ? `${d.dias_desde_atualizacao} dias` : "—"}</td>
      <td className="cell-muted">{fmtData(d.prazo_esperado)}</td>
      <td><span className={`badge ${CLASSE_SITUACAO[d.situacao] ?? "badge-gray"}`}>{d.situacao}</span></td>
    </tr>
  );
}
