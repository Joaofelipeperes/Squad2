import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { KeyboardEvent, ReactNode } from "react";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { BasePda, BasesPda, FiltrosPda, ImportacaoResumo, Opcao, PlanoPda } from "./api";
import { FILTROS_VAZIOS, SITUACOES, pdaApi } from "./api";
import { BaseDetalheModal } from "./BaseDetalheModal";
import { BaseFormModal } from "./BaseFormModal";
import { ConfirmarModal } from "./ConfirmarModal";
import { abreviarId, fmtData, fmtDataHora, plural } from "./formato";
import { ImportarIdsModal } from "./ImportarIdsModal";
import { ImportarPdaModal } from "./ImportarPdaModal";
import { PlanoFormModal } from "./PlanoFormModal";
import { SituacaoBadge } from "./SituacaoBadge";
import { Pode } from "@/shared/acesso/Pode";
import type { ColunaExportacao } from "@/shared/ui/ExportarTabela";
import { ExportarTabela, descreverFiltros, rotuloDe } from "@/shared/ui/ExportarTabela";
import { PageLede } from "@/shared/ui/PageLede";
import { useToast } from "@/shared/ui/Toast";
import type { Ordenadores } from "@/shared/ui/tabela";
import { ColunaOrdenavel, Paginacao, dataOrdenavel, useTabela } from "@/shared/ui/tabela";

type ColunaBase = "orgao" | "nome" | "dataset" | "id_ckan" | "prazo" | "periodicidade" | "atualizado" | "situacao";

const ORDENADORES_BASE: Ordenadores<BasePda, ColunaBase> = {
  orgao: (b) => b.orgao_sigla,
  nome: (b) => b.nome_previsto,
  dataset: (b) => b.dataset_titulo ?? b.dataset_name ?? b.dataset_name_planilha ?? b.dataset_id_ckan_planilha,
  id_ckan: (b) => b.dataset_id_ckan,
  prazo: (b) => b.prazo_abertura,
  periodicidade: (b) => b.periodicidade,
  atualizado: (b) => dataOrdenavel(b.ultima_atualizacao),
  situacao: (b) => b.situacao,
};

/**
 * Tela "Monitoramento do PDA" (US6, US7, US8) — referência visual: #screen-pda do Protótipo V1.
 * Vários PDAs podem estar cadastrados; o vigente é o padrão e rege os indicadores de gestão
 * (decisão de 07/10/2026, pendente de validação da GEDA). Situação e filtros vêm do backend.
 */
export default function PdaPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const planos = useQuery({ queryKey: ["pda", "planos"], queryFn: pdaApi.planos });
  const [planoSel, setPlanoSel] = useState<number | null>(null);
  // "?orgao=<chave>" vem do botão "Ver bases no PDA" da tela Organizações;
  // "?situacao=<situação>" vem dos indicadores da Visão Geral
  const [params] = useSearchParams();
  const [filtros, setFiltros] = useState<FiltrosPda>(
    () => ({ ...FILTROS_VAZIOS, orgao: params.get("orgao") ?? "", situacao: params.get("situacao") ?? "" }));
  const [importarAberto, setImportarAberto] = useState(false);
  const [idsAberto, setIdsAberto] = useState(false);
  const [confirmacao, setConfirmacao] = useState<"vigente" | "excluir" | null>(null);
  const [detalhe, setDetalhe] = useState<BasePda | null>(null);
  // Formulários do CRUD manual: PDA (novo/editar) e base (null = incluir; BasePda = editar)
  const [planoForm, setPlanoForm] = useState<"novo" | "editar" | null>(null);
  const [baseForm, setBaseForm] = useState<{ base: BasePda | null } | null>(null);
  const [baseExcluir, setBaseExcluir] = useState<BasePda | null>(null);

  const lista = planos.data ?? [];
  const vigente = lista.find((p) => p.vigente) ?? null;
  // Padrão = vigente. Se o PDA escolhido sumiu (excluído), volta para o vigente.
  const plano = lista.find((p) => p.id === planoSel) ?? vigente ?? lista[0] ?? null;
  const planoId = plano?.id ?? null;

  const bases = useQuery({
    queryKey: ["pda", "bases", planoId, filtros],
    queryFn: () => pdaApi.bases(planoId, filtros),
    enabled: planoId != null,
    // Ao trocar só os filtros, mantém a tabela na tela enquanto carrega; ao trocar o PDA, não.
    placeholderData: (anterior: BasesPda | undefined) =>
      anterior && anterior.plano?.id === planoId ? anterior : undefined,
  });

  const recarregar = () => qc.invalidateQueries({ queryKey: ["pda"] });
  const tabela = useTabela(bases.data?.bases, ORDENADORES_BASE);
  const col = { ordem: tabela.ordem, onOrdenar: tabela.ordenarPor };

  function trocarPlano(id: number | null) {
    setPlanoSel(id);
    setFiltros(FILTROS_VAZIOS);
    setDetalhe(null);
  }

  function aoImportar(r: ImportacaoResumo) {
    // Já seleciona o PDA novo (sem esperar a lista recarregar) e atualiza tudo do módulo.
    qc.setQueryData<PlanoPda[]>(["pda", "planos"], (atual) => {
      const outros = (atual ?? []).filter((p) => p.id !== r.plano.id)
        .map((p) => (r.plano.vigente ? { ...p, vigente: false } : p));
      return [...outros, r.plano];
    });
    trocarPlano(r.plano.id);
    recarregar();
  }

  function aoSalvarPlano(p: PlanoPda, criado: boolean) {
    setPlanoForm(null);
    toast(criado ? `PDA “${p.nome}” criado. Inclua as bases previstas.` : `PDA “${p.nome}” atualizado.`);
    if (criado) {
      qc.setQueryData<PlanoPda[]>(["pda", "planos"], (atual) => [
        ...(atual ?? []).map((x) => (p.vigente ? { ...x, vigente: false } : x)), p]);
      trocarPlano(p.id);
    }
    recarregar();
  }

  function aoSalvarBase(b: BasePda, criada: boolean) {
    setBaseForm(null);
    if (!criada && detalhe?.id === b.id) setDetalhe(b);
    toast(criada ? `Base “${b.nome_previsto}” incluída.` : `Base “${b.nome_previsto}” atualizada.`);
    recarregar();
  }

  const excluirBase = useMutation({
    mutationFn: (b: BasePda) => pdaApi.excluirBase(b.id).then(() => b),
    onSuccess: (b) => {
      toast(`Base “${b.nome_previsto}” removida do PDA.`);
      setDetalhe(null);
      recarregar();
    },
    onError: (e: Error) => toast(e.message, true),
    onSettled: () => setBaseExcluir(null),
  });

  const definirVigente = useMutation({
    mutationFn: (p: PlanoPda) => pdaApi.definirVigente(p.id),
    onSuccess: (p) => { toast(`“${p.nome}” agora é o PDA vigente.`); recarregar(); },
    onError: (e: Error) => toast(e.message, true),
    onSettled: () => setConfirmacao(null),
  });
  const excluir = useMutation({
    mutationFn: (p: PlanoPda) => pdaApi.excluir(p.id).then(() => p),
    onSuccess: (p) => {
      toast(`PDA “${p.nome}” excluído.`);
      trocarPlano(null);
      qc.removeQueries({ queryKey: ["pda", "bases", p.id] });
      recarregar();
    },
    onError: (e: Error) => toast(e.message, true),
    onSettled: () => setConfirmacao(null),
  });
  const vincular = useMutation({
    mutationFn: (p: PlanoPda) => pdaApi.vincular(p.id),
    onSuccess: (r) => {
      toast(`Vínculos atualizados: ${r.vinculos_resolvidos} resolvido(s), ${r.vinculos_pendentes} pendente(s).`);
      recarregar();
    },
    onError: (e: Error) => toast(e.message, true),
  });

  return (
    <section className="screen">
      <PageLede titulo="Monitoramento do PDA">
        Acompanhamento das bases previstas no Plano de Dados Abertos em relação à publicação efetiva no CKAN.
      </PageLede>

      {planos.isPending && (
        <div className="panel"><div className="panel-body cell-muted">Carregando…</div></div>
      )}
      {planos.isError && (
        <div className="panel"><div className="panel-body">
          <div className="inline-msg err" role="alert">Não foi possível carregar os PDAs: {planos.error.message}</div>
        </div></div>
      )}
      {planos.isSuccess && !plano && (
        <SemPda onImportar={() => setImportarAberto(true)} onCriar={() => setPlanoForm("novo")} />
      )}

      {plano && (
        <>
          <PainelPlano planos={lista} plano={plano} onTrocar={trocarPlano}
            onImportar={() => setImportarAberto(true)}
            onNovo={() => setPlanoForm("novo")} onEditar={() => setPlanoForm("editar")}
            onDefinirVigente={() => setConfirmacao("vigente")}
            onExcluir={() => setConfirmacao("excluir")}
            onVincular={() => vincular.mutate(plano)} vinculando={vincular.isPending}
            onImportarIds={() => setIdsAberto(true)}
            onIncluirBase={() => setBaseForm({ base: null })} />

          <div className="panel">
            <Filtros filtros={filtros} onMudar={setFiltros} dados={bases.data}
              exportar={
                <ExportarTabela titulo="Monitoramento do PDA" colunas={EXPORTACAO_BASES} linhas={tabela.todas}
                  filtros={descreverFiltros([
                    ["PDA", plano.nome], ["Órgão", rotuloDe(bases.data?.opcoes.orgaos, filtros.orgao)],
                    ["Situação", filtros.situacao], ["Periodicidade", filtros.periodicidade],
                    ["Ano", filtros.ano], ["Prazo", filtros.prazo === "vencido" ? "Vencido"
                      : filtros.prazo === "proximo" ? "Próximo do prazo" : filtros.prazo]])} />
              } />
            <div className="table-scroll">
              <table>
                <thead><tr>
                  <ColunaOrdenavel coluna="orgao" {...col}>Órgão</ColunaOrdenavel>
                  <ColunaOrdenavel coluna="nome" {...col}>Base prevista (PDA)</ColunaOrdenavel>
                  <ColunaOrdenavel coluna="dataset" {...col}>Dataset CKAN</ColunaOrdenavel>
                  <ColunaOrdenavel coluna="id_ckan" {...col}>ID CKAN</ColunaOrdenavel>
                  <ColunaOrdenavel coluna="prazo" {...col}>Prazo</ColunaOrdenavel>
                  <ColunaOrdenavel coluna="periodicidade" {...col}>Periodicidade</ColunaOrdenavel>
                  <ColunaOrdenavel coluna="atualizado" primeira="desc" {...col}>Última atualização</ColunaOrdenavel>
                  <ColunaOrdenavel coluna="situacao" {...col}>Situação</ColunaOrdenavel>
                </tr></thead>
                <tbody>
                  {bases.isError ? (
                    <tr><td colSpan={8} style={{ padding: 18 }}>
                      <div className="inline-msg err" role="alert">
                        Não foi possível carregar as bases do PDA: {bases.error.message}
                      </div>
                    </td></tr>
                  ) : !bases.data ? (
                    <tr><td colSpan={8} className="table-empty">Carregando…</td></tr>
                  ) : bases.data.bases.length === 0 ? (
                    <tr><td colSpan={8} className="table-empty">
                      <i className="fa-solid fa-inbox" style={{ marginRight: 8 }} />
                      Nenhuma base encontrada para os filtros selecionados.
                    </td></tr>
                  ) : (
                    tabela.itens.map((b) => <LinhaBase key={b.id} base={b} onAbrir={setDetalhe} />)
                  )}
                </tbody>
              </table>
            </div>
            {bases.data && (
              <Paginacao id="pda" {...tabela.paginacao} carregando={bases.isPlaceholderData}
                resumo={<><strong>{bases.data.bases.length}</strong> base(s) encontrada(s) de {bases.data.total_previstas} previstas</>} />
            )}
          </div>

          <ConfirmarModal aberto={confirmacao === "vigente"} titulo="Definir PDA vigente"
            rotuloConfirmar="Definir como vigente" icone="fa-star" processando={definirVigente.isPending}
            onConfirmar={() => definirVigente.mutate(plano)} onFechar={() => setConfirmacao(null)}>
            <p>
              O <strong>{plano.nome}</strong> passará a reger esta tela e os indicadores e relatórios de
              gestão das bases.
            </p>
            {vigente && vigente.id !== plano.id && (
              <p>O <strong>{vigente.nome}</strong> deixa de ser o vigente, mas continua cadastrado para consulta.</p>
            )}
          </ConfirmarModal>

          <ConfirmarModal aberto={confirmacao === "excluir"} titulo="Excluir PDA" perigo
            rotuloConfirmar="Excluir PDA" icone="fa-trash" processando={excluir.isPending}
            onConfirmar={() => excluir.mutate(plano)} onFechar={() => setConfirmacao(null)}>
            <p>
              O <strong>{plano.nome}</strong> e suas {plural(plano.total_bases, "base prevista", "bases previstas")} serão
              removidos do monitor.
            </p>
            <p>
              Nada é alterado no portal CKAN. A exclusão não pode ser desfeita
              {plano.arquivo_nome ? ": para recuperar, importe a planilha novamente." : "."}
            </p>
          </ConfirmarModal>

          <ConfirmarModal aberto={baseExcluir != null} titulo="Excluir base prevista" perigo
            rotuloConfirmar="Excluir base" icone="fa-trash" processando={excluirBase.isPending}
            onConfirmar={() => baseExcluir && excluirBase.mutate(baseExcluir)} onFechar={() => setBaseExcluir(null)}>
            <p>
              A base <strong>{baseExcluir?.nome_previsto}</strong> ({baseExcluir?.orgao_sigla}) será removida
              do <strong>{plano.nome}</strong>.
            </p>
            <p>Nada é alterado no portal CKAN. A exclusão não pode ser desfeita.</p>
          </ConfirmarModal>

          <PlanoFormModal aberto={planoForm != null} plano={planoForm === "editar" ? plano : null}
            primeiro={false} onFechar={() => setPlanoForm(null)} onSalvo={aoSalvarPlano} />
          <BaseFormModal aberto={baseForm != null} plano={plano} base={baseForm?.base ?? null}
            onFechar={() => setBaseForm(null)} onSalva={aoSalvarBase} />
          <ImportarIdsModal aberto={idsAberto} plano={plano} onFechar={() => setIdsAberto(false)}
            onGravado={(r) => { toast(`IDs do CKAN gravados em ${r.atualizadas} base(s).`); recarregar(); }} />
        </>
      )}

      <ImportarPdaModal aberto={importarAberto} primeiro={planos.isSuccess && lista.length === 0}
        onFechar={() => setImportarAberto(false)} onImportado={aoImportar} />
      {!plano && (
        <PlanoFormModal aberto={planoForm === "novo"} plano={null} primeiro={planos.isSuccess && lista.length === 0}
          onFechar={() => setPlanoForm(null)} onSalvo={aoSalvarPlano} />
      )}
      <BaseDetalheModal base={detalhe} onFechar={() => setDetalhe(null)}
        onEditar={(b) => setBaseForm({ base: b })} onExcluir={setBaseExcluir} />
    </section>
  );
}

/* ------------------------------------------------------------------ Estado vazio */

function SemPda({ onImportar, onCriar }: { onImportar: () => void; onCriar: () => void }) {
  return (
    <div className="panel">
      <div className="empty-state">
        <i className="fa-solid fa-clipboard-list" />
        <p>
          Nenhum PDA cadastrado. Importe a planilha do Plano de Dados Abertos (.xlsx ou .csv) ou crie o PDA e
          inclua as bases previstas manualmente para acompanhá-las em relação ao que está publicado no portal.
        </p>
        <Pode permissao="pda.gerenciar_planos"
          senao={<p style={{ marginTop: 8 }}>Peça à Gerência de Dados Abertos para cadastrar o PDA.</p>}>
          <div style={{ marginTop: 14, display: "flex", gap: 8, justifyContent: "center", flexWrap: "wrap" }}>
            <button type="button" className="btn btn-outline btn-sm" onClick={onCriar}>
              <i className="fa-solid fa-plus" />Criar PDA manualmente
            </button>
            <button type="button" className="btn btn-primary btn-sm" onClick={onImportar}>
              <i className="fa-solid fa-file-import" />Importar PDA
            </button>
          </div>
        </Pode>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ Seleção do PDA */

interface PainelPlanoProps {
  planos: PlanoPda[];
  plano: PlanoPda;
  onTrocar: (id: number) => void;
  onImportar: () => void;
  onNovo: () => void;
  onEditar: () => void;
  onDefinirVigente: () => void;
  onExcluir: () => void;
  onVincular: () => void;
  vinculando: boolean;
  onImportarIds: () => void;
  onIncluirBase: () => void;
}

function PainelPlano({
  planos, plano, onTrocar, onImportar, onNovo, onEditar, onDefinirVigente, onExcluir, onVincular, vinculando,
  onImportarIds, onIncluirBase,
}: PainelPlanoProps) {
  // O vigente só pode ser excluído quando é o único PDA (regra do backend)
  const podeExcluir = !plano.vigente || planos.length === 1;

  return (
    <div className="panel">
      <div className="filters-bar">
        <div className="filter-field filter-field-largo">
          <label htmlFor="pda-plano">PDA</label>
          <select id="pda-plano" title={plano.nome} value={plano.id} onChange={(e) => onTrocar(Number(e.target.value))}>
            {planos.map((p) => (
              <option key={p.id} value={p.id}>{p.nome}{p.vigente ? " (vigente)" : ""}</option>
            ))}
          </select>
        </div>
        <div className="filter-badge">
          {plano.vigente
            ? <span className="badge badge-green">Vigente</span>
            : <span className="badge badge-gray">Não vigente</span>}
        </div>
        <div className="filter-actions filter-actions-quebra">
          <Pode permissao="pda.editar_vinculos">
            {plano.vinculos_pendentes > 0 && (
              <button type="button" className="btn btn-outline btn-sm" onClick={onVincular} disabled={vinculando}>
                <i className="fa-solid fa-link" />
                {vinculando ? "Atualizando vínculos…"
                  : `Atualizar vínculos (${plural(plano.vinculos_pendentes, "pendente", "pendentes")})`}
              </button>
            )}
            <button type="button" className="btn btn-outline btn-sm" onClick={onImportarIds}
              title="Grava o ID do dataset no CKAN nas bases deste PDA a partir de um CSV">
              <i className="fa-solid fa-fingerprint" />Importar IDs do CKAN
            </button>
          </Pode>
          <Pode permissao="pda.gerenciar_planos">
            <button type="button" className="btn btn-outline btn-sm" onClick={onIncluirBase}>
              <i className="fa-solid fa-plus" />Incluir base
            </button>
            {!plano.vigente && (
              <button type="button" className="btn btn-outline btn-sm" onClick={onDefinirVigente}>
                <i className="fa-solid fa-star" />Definir como vigente
              </button>
            )}
            <button type="button" className="btn btn-outline btn-sm" onClick={onEditar}>
              <i className="fa-solid fa-pen" />Editar PDA
            </button>
            {podeExcluir && (
              <button type="button" className="btn btn-outline btn-sm" onClick={onExcluir}>
                <i className="fa-solid fa-trash" />Excluir PDA
              </button>
            )}
            <button type="button" className="btn btn-outline btn-sm" onClick={onNovo}>
              <i className="fa-solid fa-plus" />Novo PDA
            </button>
            <button type="button" className="btn btn-primary btn-sm" onClick={onImportar}>
              <i className="fa-solid fa-file-import" />Importar PDA
            </button>
          </Pode>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ Filtros */

function Filtro({ id, rotulo, todos, valor, opcoes, onMudar, classe }: {
  id: string; rotulo: string; todos: string; valor: string; opcoes: Opcao[]; onMudar: (v: string) => void;
  classe?: string;
}) {
  return (
    <div className={classe ? `filter-field ${classe}` : "filter-field"}>
      <label htmlFor={id}>{rotulo}</label>
      <select id={id} value={valor} onChange={(e) => onMudar(e.target.value)}>
        <option value="">{todos}</option>
        {opcoes.map((o) => <option key={o.valor} value={o.valor}>{o.rotulo}</option>)}
      </select>
    </div>
  );
}

const simples = (v: string): Opcao => ({ valor: v, rotulo: v });

function Filtros({ filtros, onMudar, dados, exportar }: {
  filtros: FiltrosPda; onMudar: (f: FiltrosPda) => void; dados: BasesPda | undefined; exportar?: ReactNode;
}) {
  const set = (campo: keyof FiltrosPda) => (valor: string) => onMudar({ ...filtros, [campo]: valor });
  const janela = dados?.janela_alerta_dias;
  const opcoesPrazo: Opcao[] = [
    { valor: "vencido", rotulo: "Vencido" },
    { valor: "proximo", rotulo: janela != null ? `Próximos ${janela} dias` : "Próximo do prazo" },
  ];
  return (
    <div className="filters-bar">
      <Filtro id="pda-filtro-orgao" rotulo="Órgão" todos="Todos" valor={filtros.orgao}
        opcoes={dados?.opcoes.orgaos ?? []} onMudar={set("orgao")} classe="filter-field-limitado" />
      <Filtro id="pda-filtro-situacao" rotulo="Situação" todos="Todas" valor={filtros.situacao}
        opcoes={SITUACOES.map(simples)} onMudar={set("situacao")} />
      <Filtro id="pda-filtro-periodicidade" rotulo="Periodicidade" todos="Todas" valor={filtros.periodicidade}
        opcoes={(dados?.opcoes.periodicidades ?? []).map(simples)} onMudar={set("periodicidade")} />
      <Filtro id="pda-filtro-ano" rotulo="Ano" todos="Todos" valor={filtros.ano}
        opcoes={(dados?.opcoes.anos ?? []).map((a) => simples(String(a)))} onMudar={set("ano")} />
      <Filtro id="pda-filtro-prazo" rotulo="Prazo" todos="Todos" valor={filtros.prazo}
        opcoes={opcoesPrazo} onMudar={set("prazo")} />
      <div className="filter-actions">
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => onMudar(FILTROS_VAZIOS)}>
          Limpar filtros
        </button>
        {exportar}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ Tabela */

/** Dataset do CKAN na exportação: título do vinculado, ou o informado na planilha (vínculo pendente). */
function datasetExportado(b: BasePda): string {
  if (b.vinculo === "resolvido") {
    return (b.dataset_titulo ?? b.dataset_name ?? "—") + (b.dataset_ativo === false ? " (fora do portal)" : "");
  }
  if (b.vinculo === "pendente") {
    return `${b.dataset_name_planilha ?? b.dataset_id_ckan_planilha ?? "—"} (vínculo pendente)`;
  }
  return "—";
}

/** Colunas do Excel/PDF: as mesmas da tabela (ID do CKAN completo), com os valores como a tela mostra. */
const EXPORTACAO_BASES: ColunaExportacao<BasePda>[] = [
  { titulo: "Órgão", valor: (b) => b.orgao_sigla },
  { titulo: "Base prevista (PDA)", valor: (b) => b.nome_previsto },
  { titulo: "Dataset CKAN", valor: datasetExportado },
  { titulo: "ID CKAN", valor: (b) => b.dataset_id_ckan },
  { titulo: "Prazo", valor: (b) => fmtData(b.prazo_abertura) },
  { titulo: "Periodicidade", valor: (b) => b.periodicidade },
  { titulo: "Última atualização",
    valor: (b) => fmtDataHora(b.ultima_atualizacao) + (b.ultima_atualizacao && b.ultima_atualizacao_estimada ? " (est.)" : "") },
  { titulo: "Situação", valor: (b) => b.situacao },
];

function CelulaDataset({ b }: { b: BasePda }) {
  if (b.vinculo === "resolvido") {
    return (
      <>
        <span>{b.dataset_titulo ?? b.dataset_name ?? "—"}</span>
        {b.dataset_ativo === false && (
          <>{" "}<span className="badge badge-red" title="Dataset vinculado não está mais visível no portal">fora do portal</span></>
        )}
      </>
    );
  }
  if (b.vinculo === "pendente") {
    return (
      <>
        <span className="cell-muted" title={b.dataset_id_ckan_planilha ?? undefined}>
          {b.dataset_name_planilha ?? (b.dataset_id_ckan_planilha && abreviarId(b.dataset_id_ckan_planilha))}
        </span>{" "}
        <span className="badge badge-amber">vínculo pendente</span>
      </>
    );
  }
  return <span className="cell-muted">—</span>;
}

function LinhaBase({ base: b, onAbrir }: { base: BasePda; onAbrir: (b: BasePda) => void }) {
  const teclado = (e: KeyboardEvent<HTMLTableRowElement>) => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onAbrir(b); }
  };
  const periodicidadeOriginal =
    b.periodicidade_original && b.periodicidade_original.trim() !== b.periodicidade
      ? `Na planilha: ${b.periodicidade_original}` : undefined;
  return (
    <tr tabIndex={0} onClick={() => onAbrir(b)} onKeyDown={teclado}>
      <td title={b.orgao_nome ?? undefined}>{b.orgao_sigla}</td>
      <td className="cell-strong">{b.nome_previsto}</td>
      <td><CelulaDataset b={b} /></td>
      <td className="mono cell-muted" title={b.dataset_id_ckan ?? undefined}>{b.dataset_id_ckan ? abreviarId(b.dataset_id_ckan) : "—"}</td>
      <td className="cell-muted">{fmtData(b.prazo_abertura)}</td>
      <td title={periodicidadeOriginal}>{b.periodicidade}</td>
      <td className="cell-muted">
        {fmtDataHora(b.ultima_atualizacao)}
        {b.ultima_atualizacao && b.ultima_atualizacao_estimada && (
          <span title="Estimada pela data de criação do recurso (sem last_modified)"> (est.)</span>
        )}
      </td>
      <td><SituacaoBadge situacao={b.situacao} /></td>
    </tr>
  );
}
