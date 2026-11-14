import { useQuery } from "@tanstack/react-query";
import type { KeyboardEvent } from "react";
import { useEffect, useState } from "react";
import type { AtualizacaoLinha, AtualizacoesLista, FiltrosAtualizacoes } from "./api";
import { FILTROS_VAZIOS, atualizacoesApi } from "./api";
import { DatasetDetalheModal } from "@/modules/datasets/DatasetDetalheModal";
import { TipoBaseBadge } from "@/modules/datasets/formato";
import { fmtData, fmtDataHora } from "@/modules/pda/formato";
import type { ColunaExportacao } from "@/shared/ui/ExportarTabela";
import { ExportarTabela, descreverFiltros, rotuloDe } from "@/shared/ui/ExportarTabela";
import { PageLede } from "@/shared/ui/PageLede";
import type { Ordenadores } from "@/shared/ui/tabela";
import { ColunaOrdenavel, Paginacao, dataOrdenavel, useTabela } from "@/shared/ui/tabela";

type Coluna = "dataset" | "orgao" | "tipo" | "periodicidade" | "atualizado" | "dias" | "prazo" | "situacao";

const ORDENADORES: Ordenadores<AtualizacaoLinha, Coluna> = {
  dataset: (d) => d.dataset_titulo,
  orgao: (d) => d.orgao_sigla,
  tipo: (d) => d.tipo_base,
  periodicidade: (d) => d.periodicidade,
  atualizado: (d) => dataOrdenavel(d.ultima_atualizacao),
  dias: (d) => d.dias_desde_atualizacao,
  prazo: (d) => d.prazo_esperado,
  situacao: (d) => d.situacao,
};

const NAO_INFORMADA = "Periodicidade não informada";

/**
 * Tela "Monitoramento de Atualizações" (US9/US10) — referência visual: #screen-updates do
 * Protótipo V1. TODOS os datasets publicados no portal, previstos no PDA ou espontâneos (ADR-0037):
 * o vínculo com o PDA só identifica o tipo de base. A periodicidade vem do campo "Atualização" do
 * CKAN e a última atualização do `last_modified` do RECURSO, nunca do `metadata_modified`.
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
  const tabela = useTabela(dados?.datasets, ORDENADORES);
  const col = { ordem: tabela.ordem, onOrdenar: tabela.ordenarPor };
  const r = dados?.resumo;

  return (
    <section className="screen">
      <PageLede titulo="Monitoramento de Atualizações">
        Atualização real do conteúdo de todas as bases publicadas no portal, previstas no PDA ou espontâneas,
        pela periodicidade declarada no campo “Atualização” do CKAN.
      </PageLede>

      <div className="kpi-grid">
        <Cartao cor="green" icone="fa-check" valor={r?.atualizados} rotulo="Atualizados no período" />
        <Cartao cor="red" icone="fa-triangle-exclamation" valor={r?.atrasados} rotulo="Em atraso" />
        <Cartao cor="amber" icone="fa-hourglass-half" valor={r?.proximos_do_vencimento}
          rotulo="Próximos do vencimento" />
        <Cartao cor="blue" icone="fa-circle-exclamation" valor={r?.periodicidade_nao_informada}
          rotulo="Periodicidade não informada"
          dica="Campo “Atualização” vazio ou com valor inválido no CKAN: metadado obrigatório não conforme." />
      </div>
      {r && (
        <p className="help-texto" style={{ margin: "-12px 0 18px" }}>
          {r.sem_atualizacao_periodica} declarada(s) sem atualização periódica (válido, fica fora do prazo)
          {r.sem_data > 0 && ` · ${r.sem_data} sem data de atualização (nenhum recurso válido)`}
          {" · "}{r.previstas_no_pda} prevista(s) no PDA{dados?.plano_nome ? ` (${dados.plano_nome})` : ""} e{" "}
          {r.espontaneas} espontânea(s)
        </p>
      )}

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
          <Filtro id="at-filtro-tipo-base" rotulo="Tipo de base" valor={filtros.tipo_base} onMudar={set("tipo_base")}
            opcoes={(dados?.opcoes.tipos_base ?? []).map((t) => ({ valor: t, rotulo: t }))} />
          <Filtro id="at-filtro-periodicidade" rotulo="Periodicidade" valor={filtros.periodicidade}
            onMudar={set("periodicidade")}
            opcoes={(dados?.opcoes.periodicidades ?? []).map((p) => ({ valor: p, rotulo: p }))} />
          <Filtro id="at-filtro-situacao" rotulo="Situação" valor={filtros.situacao} onMudar={set("situacao")}
            opcoes={(dados?.opcoes.situacoes ?? []).map((s) => ({ valor: s, rotulo: s }))} />
          <div className="filter-actions">
            <button type="button" className="btn btn-ghost btn-sm" onClick={limpar}>Limpar filtros</button>
            <ExportarTabela titulo="Monitoramento de Atualizações" colunas={EXPORTACAO} linhas={tabela.todas}
              filtros={descreverFiltros([
                ["Dataset", filtros.dataset],
                ["Órgão", rotuloDe(dados?.opcoes.orgaos, filtros.orgao)], ["Tipo de base", filtros.tipo_base],
                ["Periodicidade", filtros.periodicidade], ["Situação", filtros.situacao]])} />
          </div>
        </div>
        <div className="table-scroll">
          <table>
            <thead><tr>
              <ColunaOrdenavel coluna="dataset" {...col}>Dataset</ColunaOrdenavel>
              <ColunaOrdenavel coluna="orgao" {...col}>Órgão</ColunaOrdenavel>
              <ColunaOrdenavel coluna="tipo" {...col}>Tipo de base</ColunaOrdenavel>
              <ColunaOrdenavel coluna="periodicidade" {...col}>Periodicidade</ColunaOrdenavel>
              <ColunaOrdenavel coluna="atualizado" primeira="desc" {...col}>Último recurso atualizado</ColunaOrdenavel>
              <ColunaOrdenavel coluna="dias" primeira="desc" {...col}>Dias desde atualização</ColunaOrdenavel>
              <ColunaOrdenavel coluna="prazo" {...col}>Prazo esperado</ColunaOrdenavel>
              <ColunaOrdenavel coluna="situacao" {...col}>Situação</ColunaOrdenavel>
            </tr></thead>
            <tbody>
              {lista.isError ? (
                <tr><td colSpan={8} style={{ padding: 18 }}>
                  <div className="inline-msg err" role="alert">
                    Não foi possível carregar as atualizações: {lista.error.message}
                  </div>
                </td></tr>
              ) : !dados ? (
                <tr><td colSpan={8} className="table-empty">Carregando…</td></tr>
              ) : dados.total === 0 ? (
                <tr><td colSpan={8} className="table-empty">
                  <i className="fa-solid fa-inbox" style={{ marginRight: 8 }} />
                  Nenhum dataset publicado no portal para monitorar. Rode a coleta do CKAN.
                </td></tr>
              ) : dados.datasets.length === 0 ? (
                <tr><td colSpan={8} className="table-empty">Nenhum registro para os filtros selecionados.</td></tr>
              ) : (
                tabela.itens.map((d) => <Linha key={d.dataset_id} d={d} onAbrir={setDetalhe} />)
              )}
            </tbody>
          </table>
        </div>
        {dados && (
          <Paginacao id="at" {...tabela.paginacao} carregando={lista.isPlaceholderData}
            resumo={<><strong>{dados.datasets.length}</strong> dataset(s) encontrado(s) de {dados.total} publicados no
              portal</>} />
        )}
      </div>

      <DatasetDetalheModal datasetId={detalhe} onFechar={() => setDetalhe(null)} />
    </section>
  );
}

/** "Não informada" com o texto do CKAN quando o órgão preencheu algo inválido. */
function dicaPeriodicidade(d: AtualizacaoLinha): string | undefined {
  if (d.periodicidade !== NAO_INFORMADA) return undefined;
  return d.periodicidade_declarada
    ? `Valor inválido no campo “Atualização” do CKAN: “${d.periodicidade_declarada}”`
    : "Campo “Atualização” vazio no CKAN";
}

/** Colunas do Excel/PDF: as mesmas da tabela, com os valores como a tela mostra. */
const EXPORTACAO: ColunaExportacao<AtualizacaoLinha>[] = [
  { titulo: "Dataset", valor: (d) => d.dataset_titulo },
  { titulo: "Órgão", valor: (d) => d.orgao_sigla },
  { titulo: "Tipo de base", valor: (d) => d.tipo_base },
  { titulo: "Periodicidade", valor: (d) => d.periodicidade },
  { titulo: "Atualização no CKAN", valor: (d) => d.periodicidade_declarada ?? "" },
  { titulo: "Último recurso atualizado",
    valor: (d) => fmtDataHora(d.ultima_atualizacao) + (d.ultima_atualizacao && d.ultima_atualizacao_estimada ? " (est.)" : "") },
  { titulo: "Dias desde atualização", valor: (d) => d.dias_desde_atualizacao },
  { titulo: "Prazo esperado", valor: (d) => fmtData(d.prazo_esperado) },
  { titulo: "Situação", valor: (d) => d.situacao },
];

function Cartao({ cor, icone, valor, rotulo, dica }: {
  cor: string; icone: string; valor?: number; rotulo: string; dica?: string;
}) {
  return (
    <div className="kpi-card" title={dica}>
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

// "Periodicidade não informada" é não conformidade de metadado (âmbar); "Sem atualização periódica"
// é declaração válida do órgão e "Sem data de atualização" não tem como ser avaliada (cinza).
const CLASSE_SITUACAO: Record<string, string> = {
  "Atualizado": "badge-green",
  "Próximo do vencimento": "badge-amber",
  "Atrasado": "badge-red",
  [NAO_INFORMADA]: "badge-amber",
};

function Linha({ d, onAbrir }: { d: AtualizacaoLinha; onAbrir: (id: number) => void }) {
  const teclado = (e: KeyboardEvent<HTMLTableRowElement>) => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onAbrir(d.dataset_id); }
  };
  return (
    <tr tabIndex={0} onClick={() => onAbrir(d.dataset_id)} onKeyDown={teclado}>
      <td className="cell-strong" title={d.dataset_name ?? undefined}>{d.dataset_titulo}</td>
      <td title={d.orgao_nome ?? undefined}>{d.orgao_sigla}</td>
      <td><TipoBaseBadge tipo={d.tipo_base} /></td>
      <td title={dicaPeriodicidade(d)}>{d.periodicidade}</td>
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
