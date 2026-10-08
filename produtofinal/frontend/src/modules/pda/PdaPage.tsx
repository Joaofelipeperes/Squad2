import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { KeyboardEvent } from "react";
import { useState } from "react";
import type { BasePda, BasesPda, FiltrosPda, ImportacaoResumo, Opcao, PlanoPda } from "./api";
import { FILTROS_VAZIOS, SITUACOES, pdaApi } from "./api";
import { BaseDetalheModal } from "./BaseDetalheModal";
import { ConfirmarModal } from "./ConfirmarModal";
import { abreviarId, fmtData, fmtDataHora, plural } from "./formato";
import { ImportarPdaModal } from "./ImportarPdaModal";
import { SituacaoBadge } from "./SituacaoBadge";
import { Pode } from "@/shared/acesso/Pode";
import { PageLede } from "@/shared/ui/PageLede";
import { useToast } from "@/shared/ui/Toast";

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
  const [filtros, setFiltros] = useState<FiltrosPda>(FILTROS_VAZIOS);
  const [importarAberto, setImportarAberto] = useState(false);
  const [confirmacao, setConfirmacao] = useState<"vigente" | "excluir" | null>(null);
  const [detalhe, setDetalhe] = useState<BasePda | null>(null);

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
      {planos.isSuccess && !plano && <SemPda onImportar={() => setImportarAberto(true)} />}

      {plano && (
        <>
          <PainelPlano planos={lista} plano={plano} onTrocar={trocarPlano}
            onImportar={() => setImportarAberto(true)}
            onDefinirVigente={() => setConfirmacao("vigente")}
            onExcluir={() => setConfirmacao("excluir")}
            onVincular={() => vincular.mutate(plano)} vinculando={vincular.isPending} />

          <div className="panel">
            <Filtros filtros={filtros} onMudar={setFiltros} dados={bases.data} />
            <div className="panel-head" style={{ borderBottom: "none", paddingBottom: 0 }}>
              <div className="sub" style={{ fontSize: 12.5 }} aria-live="polite">
                {bases.data
                  ? `${bases.data.bases.length} base(s) encontrada(s) de ${bases.data.total_previstas} previstas`
                  : bases.isError ? "" : "Carregando…"}
                {bases.isPlaceholderData && " · atualizando…"}
              </div>
            </div>
            <div className="table-scroll">
              <table>
                <thead><tr>
                  <th>Órgão</th><th>Base prevista (PDA)</th><th>Dataset CKAN</th><th>ID CKAN</th>
                  <th>Prazo</th><th>Periodicidade</th><th>Última atualização</th><th>Situação</th>
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
                    bases.data.bases.map((b) => <LinhaBase key={b.id} base={b} onAbrir={setDetalhe} />)
                  )}
                </tbody>
              </table>
            </div>
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
            <p>Nada é alterado no portal CKAN. A exclusão não pode ser desfeita: para recuperar, importe a planilha novamente.</p>
          </ConfirmarModal>
        </>
      )}

      <ImportarPdaModal aberto={importarAberto} primeiro={planos.isSuccess && lista.length === 0}
        onFechar={() => setImportarAberto(false)} onImportado={aoImportar} />
      <BaseDetalheModal base={detalhe} onFechar={() => setDetalhe(null)} />
    </section>
  );
}

/* ------------------------------------------------------------------ Estado vazio */

function SemPda({ onImportar }: { onImportar: () => void }) {
  return (
    <div className="panel">
      <div className="empty-state">
        <i className="fa-solid fa-clipboard-list" />
        <p>
          Nenhum PDA cadastrado. Importe a planilha do Plano de Dados Abertos (.xlsx ou .csv) para acompanhar
          as bases previstas em relação ao que está publicado no portal.
        </p>
        <Pode permissao="pda.gerenciar_planos"
          senao={<p style={{ marginTop: 8 }}>Peça à Gerência de Dados Abertos para importar o PDA.</p>}>
          <button type="button" className="btn btn-primary btn-sm" style={{ marginTop: 14 }} onClick={onImportar}>
            Importar PDA
          </button>
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
  onDefinirVigente: () => void;
  onExcluir: () => void;
  onVincular: () => void;
  vinculando: boolean;
}

function vigencia(p: PlanoPda): string | null {
  if (p.vigencia_inicio && p.vigencia_fim) return `vigência ${fmtData(p.vigencia_inicio)} a ${fmtData(p.vigencia_fim)}`;
  if (p.vigencia_inicio) return `vigência a partir de ${fmtData(p.vigencia_inicio)}`;
  if (p.vigencia_fim) return `vigência até ${fmtData(p.vigencia_fim)}`;
  return null;
}

function PainelPlano({ planos, plano, onTrocar, onImportar, onDefinirVigente, onExcluir, onVincular, vinculando }: PainelPlanoProps) {
  const info = [
    plural(plano.total_bases, "base prevista", "bases previstas"),
    `importado em ${fmtDataHora(plano.importado_em)}${plano.importado_por ? ` por ${plano.importado_por}` : ""}`,
    vigencia(plano),
  ].filter(Boolean).join(" · ");

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
          </Pode>
          <Pode permissao="pda.gerenciar_planos">
            {!plano.vigente && (
              <>
                <button type="button" className="btn btn-outline btn-sm" onClick={onDefinirVigente}>
                  <i className="fa-solid fa-star" />Definir como vigente
                </button>
                <button type="button" className="btn btn-outline btn-sm" onClick={onExcluir}>
                  <i className="fa-solid fa-trash" />Excluir PDA
                </button>
              </>
            )}
            <button type="button" className="btn btn-primary btn-sm" onClick={onImportar}>
              <i className="fa-solid fa-file-import" />Importar PDA
            </button>
          </Pode>
        </div>
      </div>
      <div className="panel-head" style={{ borderBottom: "none" }}>
        <div className="sub" style={{ fontSize: 12.5 }}>
          {info}{plano.arquivo_nome && <span title="Arquivo de origem"> · {plano.arquivo_nome}</span>}
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

function Filtros({ filtros, onMudar, dados }: {
  filtros: FiltrosPda; onMudar: (f: FiltrosPda) => void; dados: BasesPda | undefined;
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
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ Tabela */

function CelulaDataset({ b }: { b: BasePda }) {
  if (b.vinculo === "resolvido") {
    return (
      <>
        <span title={b.dataset_titulo ?? undefined}>{b.dataset_name ?? "—"}</span>
        {b.dataset_ativo === false && (
          <>{" "}<span className="badge badge-red" title="Dataset vinculado não está mais visível no portal">fora do portal</span></>
        )}
      </>
    );
  }
  if (b.vinculo === "pendente") {
    return (
      <>
        <span className="cell-muted">{b.dataset_name_planilha}</span>{" "}
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
      <td className="mono cell-muted" title={b.dataset_id ?? undefined}>{b.dataset_id ? abreviarId(b.dataset_id) : "—"}</td>
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
