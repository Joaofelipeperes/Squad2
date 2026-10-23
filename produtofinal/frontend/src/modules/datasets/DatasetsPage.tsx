import { useQuery } from "@tanstack/react-query";
import type { KeyboardEvent } from "react";
import { useEffect, useState } from "react";
import type { DatasetLinha, DatasetsLista, FiltrosDatasets } from "./api";
import { FILTROS_VAZIOS, datasetsApi } from "./api";
import { DatasetDetalheModal } from "./DatasetDetalheModal";
import { SituacaoPortalBadge, abreviarId, fmtDataHora } from "./formato";
import { PageLede } from "@/shared/ui/PageLede";

/**
 * Tela "Datasets" (PBI-83) — referência visual: #screen-datasets do Protótipo V1.
 * Inventário do portal vindo da coleta (não consulta o CKAN em tempo de tela). "Última
 * atualização" é a do RECURSO (last_modified), nunca a data de metadado do dataset.
 */
export default function DatasetsPage() {
  const [filtros, setFiltros] = useState<FiltrosDatasets>(FILTROS_VAZIOS);
  const [busca, setBusca] = useState("");
  const [detalhe, setDetalhe] = useState<number | null>(null);

  // A busca é enviada ao backend com uma pequena espera, para não consultar a cada tecla.
  useEffect(() => {
    const t = setTimeout(() => setFiltros((f) => (f.busca === busca ? f : { ...f, busca })), 300);
    return () => clearTimeout(t);
  }, [busca]);

  const lista = useQuery({
    queryKey: ["inventario", "datasets", filtros],
    queryFn: () => datasetsApi.lista(filtros),
    placeholderData: (anterior: DatasetsLista | undefined) => anterior,
  });

  const set = (campo: keyof FiltrosDatasets) => (valor: string) => setFiltros((f) => ({ ...f, [campo]: valor }));
  const limpar = () => { setBusca(""); setFiltros(FILTROS_VAZIOS); };
  const dados = lista.data;

  return (
    <section className="screen">
      <PageLede titulo="Datasets">
        Inventário de datasets publicados no Portal de Dados Abertos (CKAN).
      </PageLede>

      <div className="panel">
        <div className="filters-bar">
          <div className="search-field">
            <i className="fa-solid fa-magnifying-glass" />
            <input type="text" className="text-input" aria-label="Buscar por nome do dataset"
                   placeholder="Buscar por nome do dataset..." value={busca}
                   onChange={(e) => setBusca(e.target.value)} />
          </div>
          <Filtro id="ds-filtro-orgao" rotulo="Órgão" valor={filtros.orgao} onMudar={set("orgao")}
            opcoes={dados?.opcoes.orgaos ?? []} classe="filter-field-limitado" />
          <Filtro id="ds-filtro-formato" rotulo="Formato" valor={filtros.formato} onMudar={set("formato")}
            opcoes={(dados?.opcoes.formatos ?? []).map((f) => ({ valor: f, rotulo: f }))} />
          <Filtro id="ds-filtro-situacao" rotulo="Status" valor={filtros.situacao} onMudar={set("situacao")}
            opcoes={(dados?.opcoes.situacoes ?? []).map((s) => ({ valor: s, rotulo: s }))} />
          <div className="filter-actions">
            <button type="button" className="btn btn-ghost btn-sm" onClick={limpar}>Limpar filtros</button>
          </div>
        </div>
        <div className="panel-head" style={{ borderBottom: "none", paddingBottom: 0 }}>
          <div className="sub" style={{ fontSize: 12.5 }} aria-live="polite">
            {dados ? `${dados.datasets.length} dataset(s) encontrado(s) de ${dados.total} no inventário`
              : lista.isError ? "" : "Carregando…"}
            {lista.isPlaceholderData && " · atualizando…"}
          </div>
        </div>
        <div className="table-scroll">
          <table>
            <thead><tr>
              <th>Dataset</th><th>Órgão</th><th>ID CKAN</th><th>Qtd. recursos</th>
              <th>Última atualização</th><th>Formato</th><th>Status</th>
            </tr></thead>
            <tbody>
              {lista.isError ? (
                <tr><td colSpan={7} style={{ padding: 18 }}>
                  <div className="inline-msg err" role="alert">
                    Não foi possível carregar o inventário: {lista.error.message}
                  </div>
                </td></tr>
              ) : !dados ? (
                <tr><td colSpan={7} className="table-empty">Carregando…</td></tr>
              ) : dados.total === 0 ? (
                <tr><td colSpan={7} className="table-empty">
                  <i className="fa-solid fa-inbox" style={{ marginRight: 8 }} />
                  O inventário está vazio: rode a coleta pelo botão "Atualizar dados".
                </td></tr>
              ) : dados.datasets.length === 0 ? (
                <tr><td colSpan={7} className="table-empty">Nenhum dataset encontrado.</td></tr>
              ) : (
                dados.datasets.map((d) => <Linha key={d.id} d={d} onAbrir={setDetalhe} />)
              )}
            </tbody>
          </table>
        </div>
      </div>

      <DatasetDetalheModal datasetId={detalhe} onFechar={() => setDetalhe(null)} />
    </section>
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

function Linha({ d, onAbrir }: { d: DatasetLinha; onAbrir: (id: number) => void }) {
  const teclado = (e: KeyboardEvent<HTMLTableRowElement>) => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onAbrir(d.id); }
  };
  return (
    <tr tabIndex={0} onClick={() => onAbrir(d.id)} onKeyDown={teclado}>
      <td className="cell-strong" title={d.name}>{d.titulo}</td>
      <td title={d.orgao_nome ?? undefined}>{d.orgao_nome ?? "—"}</td>
      <td className="mono cell-muted" title={d.id_ckan ?? undefined}>{d.id_ckan ? abreviarId(d.id_ckan) : "—"}</td>
      <td>{d.recursos_validos}</td>
      <td className="cell-muted">
        {fmtDataHora(d.ultima_atualizacao)}
        {d.ultima_atualizacao && d.ultima_atualizacao_estimada && (
          <span title="Estimada pela data de criação do recurso (sem last_modified)"> (est.)</span>
        )}
      </td>
      <td>
        {d.formatos.length
          ? d.formatos.map((f) => <span key={f} className="badge badge-blue" style={{ marginRight: 4 }}>{f}</span>)
          : <span className="cell-muted">—</span>}
      </td>
      <td><SituacaoPortalBadge situacao={d.situacao} /></td>
    </tr>
  );
}
