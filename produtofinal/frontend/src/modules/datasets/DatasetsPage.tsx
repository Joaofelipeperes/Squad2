import { useQuery } from "@tanstack/react-query";
import type { KeyboardEvent } from "react";
import { useEffect, useState } from "react";
import type { DatasetLinha, DatasetsLista, FiltrosDatasets } from "./api";
import { FILTROS_VAZIOS, datasetsApi } from "./api";
import { DatasetDetalheModal } from "./DatasetDetalheModal";
import { SituacaoPortalBadge, abreviarId, fmtDataHora } from "./formato";
import type { ColunaExportacao } from "@/shared/ui/ExportarTabela";
import { ExportarTabela, descreverFiltros, rotuloDe } from "@/shared/ui/ExportarTabela";
import { PageLede } from "@/shared/ui/PageLede";
import type { Ordenadores } from "@/shared/ui/tabela";
import { ColunaOrdenavel, Paginacao, dataOrdenavel, useTabela } from "@/shared/ui/tabela";

type Coluna = "titulo" | "orgao" | "id_ckan" | "recursos" | "criado" | "atualizado" | "formato" | "tipo" | "situacao";

const ORDENADORES: Ordenadores<DatasetLinha, Coluna> = {
  titulo: (d) => d.titulo,
  orgao: (d) => d.orgao_nome,
  id_ckan: (d) => d.id_ckan,
  recursos: (d) => d.recursos_validos,
  criado: (d) => dataOrdenavel(d.metadata_created),
  atualizado: (d) => dataOrdenavel(d.ultima_atualizacao),
  formato: (d) => d.formatos.join(", "),
  tipo: (d) => d.tipo_base,
  situacao: (d) => d.situacao,
};

/**
 * Tela "Datasets" (PBI-83) — referência visual: #screen-datasets do Protótipo V1.
 * Inventário do portal vindo da coleta (não consulta o CKAN em tempo de tela). "Última
 * atualização" é a do RECURSO (last_modified), nunca a data de metadado do dataset. Ordem padrão:
 * criação no CKAN, mais recente primeiro; qualquer coluna ordena (ADR-0028).
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
  const tabela = useTabela(dados?.datasets, ORDENADORES, { coluna: "criado", direcao: "desc" });
  const col = { ordem: tabela.ordem, onOrdenar: tabela.ordenarPor };

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
          <Filtro id="ds-filtro-tipo-base" rotulo="Tipo de base" valor={filtros.tipo_base} onMudar={set("tipo_base")}
            opcoes={(dados?.opcoes.tipos_base ?? []).map((t) => ({ valor: t, rotulo: t }))}
            dica="Prevista no PDA: vinculada pelo ID a uma base do PDA vigente. Espontânea: publicada no portal sem estar no PDA vigente." />
          <div className="filter-actions">
            <button type="button" className="btn btn-ghost btn-sm" onClick={limpar}>Limpar filtros</button>
            <ExportarTabela titulo="Datasets" colunas={EXPORTACAO} linhas={tabela.todas}
              filtros={descreverFiltros([
                ["Busca", filtros.busca], ["Órgão", rotuloDe(dados?.opcoes.orgaos, filtros.orgao)],
                ["Formato", filtros.formato], ["Status", filtros.situacao], ["Tipo de base", filtros.tipo_base]])} />
          </div>
        </div>
        <div className="table-scroll">
          <table>
            <thead><tr>
              <ColunaOrdenavel coluna="titulo" {...col}>Dataset</ColunaOrdenavel>
              <ColunaOrdenavel coluna="orgao" {...col}>Órgão</ColunaOrdenavel>
              <ColunaOrdenavel coluna="id_ckan" {...col}>ID CKAN</ColunaOrdenavel>
              <ColunaOrdenavel coluna="recursos" primeira="desc" {...col}>Qtd. recursos</ColunaOrdenavel>
              <ColunaOrdenavel coluna="criado" primeira="desc" {...col}
                title="Data de criação do dataset no CKAN">Criado no CKAN</ColunaOrdenavel>
              <ColunaOrdenavel coluna="atualizado" primeira="desc" {...col}>Última atualização</ColunaOrdenavel>
              <ColunaOrdenavel coluna="formato" {...col}>Formato</ColunaOrdenavel>
              <ColunaOrdenavel coluna="tipo" {...col}>Tipo de base</ColunaOrdenavel>
              <ColunaOrdenavel coluna="situacao" {...col}>Status</ColunaOrdenavel>
            </tr></thead>
            <tbody>
              {lista.isError ? (
                <tr><td colSpan={COLUNAS} style={{ padding: 18 }}>
                  <div className="inline-msg err" role="alert">
                    Não foi possível carregar o inventário: {lista.error.message}
                  </div>
                </td></tr>
              ) : !dados ? (
                <tr><td colSpan={COLUNAS} className="table-empty">Carregando…</td></tr>
              ) : dados.total === 0 ? (
                <tr><td colSpan={COLUNAS} className="table-empty">
                  <i className="fa-solid fa-inbox" style={{ marginRight: 8 }} />
                  O inventário está vazio: rode a coleta pelo botão "Atualizar dados".
                </td></tr>
              ) : dados.datasets.length === 0 ? (
                <tr><td colSpan={COLUNAS} className="table-empty">Nenhum dataset encontrado.</td></tr>
              ) : (
                tabela.itens.map((d) => <Linha key={d.id} d={d} onAbrir={setDetalhe} />)
              )}
            </tbody>
          </table>
        </div>
        {dados && (
          <Paginacao id="ds" {...tabela.paginacao} carregando={lista.isPlaceholderData}
            resumo={<><strong>{dados.datasets.length}</strong> dataset(s) encontrado(s) de {dados.total} no inventário</>} />
        )}
      </div>

      <DatasetDetalheModal datasetId={detalhe} onFechar={() => setDetalhe(null)} />
    </section>
  );
}

const COLUNAS = 9;

/** Colunas do Excel/PDF: as mesmas da tabela (ID do CKAN completo), com os valores como a tela mostra. */
const EXPORTACAO: ColunaExportacao<DatasetLinha>[] = [
  { titulo: "Dataset", valor: (d) => d.titulo },
  { titulo: "Órgão", valor: (d) => d.orgao_nome },
  { titulo: "ID CKAN", valor: (d) => d.id_ckan },
  { titulo: "Qtd. recursos", valor: (d) => d.recursos_validos },
  { titulo: "Criado no CKAN", valor: (d) => fmtDataHora(d.metadata_created) },
  { titulo: "Última atualização",
    valor: (d) => fmtDataHora(d.ultima_atualizacao) + (d.ultima_atualizacao && d.ultima_atualizacao_estimada ? " (est.)" : "") },
  { titulo: "Formato", valor: (d) => d.formatos.join(", ") || "—" },
  { titulo: "Tipo de base", valor: (d) => d.tipo_base ?? "—" },
  { titulo: "Status", valor: (d) => d.situacao },
];

function Filtro({ id, rotulo, valor, opcoes, onMudar, classe, dica }: {
  id: string; rotulo: string; valor: string; opcoes: { valor: string; rotulo: string }[];
  onMudar: (v: string) => void; classe?: string; dica?: string;
}) {
  return (
    <div className={classe ? `filter-field ${classe}` : "filter-field"} title={dica}>
      <label htmlFor={id}>{rotulo}</label>
      <select id={id} value={valor} onChange={(e) => onMudar(e.target.value)}>
        <option value="">Todos</option>
        {opcoes.map((o) => <option key={o.valor} value={o.valor}>{o.rotulo}</option>)}
      </select>
    </div>
  );
}

function TipoBaseBadge({ tipo }: { tipo: string | null }) {
  if (!tipo) return <span className="cell-muted" title="Fora do portal e sem vínculo com o PDA vigente">—</span>;
  return <span className={`badge ${tipo === "Espontânea" ? "badge-amber" : "badge-blue"}`}>{tipo}</span>;
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
      <td className="cell-muted">{fmtDataHora(d.metadata_created)}</td>
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
      <td><TipoBaseBadge tipo={d.tipo_base} /></td>
      <td><SituacaoPortalBadge situacao={d.situacao} /></td>
    </tr>
  );
}
