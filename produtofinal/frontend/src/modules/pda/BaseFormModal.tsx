import { useMutation, useQuery } from "@tanstack/react-query";
import type { FormEvent } from "react";
import { useEffect, useState } from "react";
import type { BaseEntrada, BasePda, DatasetOpcao, PlanoPda } from "./api";
import { pdaApi } from "./api";
import { DatasetBusca } from "./DatasetBusca";
import { Modal } from "@/shared/ui/Modal";

interface Props {
  aberto: boolean;
  plano: PlanoPda;
  /** Base a editar; null = incluir uma base nova no PDA. */
  base: BasePda | null;
  onFechar: () => void;
  onSalva: (base: BasePda, criada: boolean) => void;
}

interface Campos {
  orgao_sigla: string;
  organizacao_id: string;
  nome_previsto: string;
  descricao: string;
  unidade_responsavel: string;
  periodicidade: string;
  prazo_abertura: string;
  politicas_publicas: string;
  sigiloso: "" | "sim" | "nao";
  /** name da planilha ainda sem dataset no inventário (vínculo pendente); mantido ao salvar. */
  dataset_link: string;
}

const VAZIO: Campos = {
  orgao_sigla: "", organizacao_id: "", nome_previsto: "", descricao: "", unidade_responsavel: "",
  periodicidade: "", prazo_abertura: "", politicas_publicas: "", sigiloso: "", dataset_link: "",
};

function camposDaBase(b: BasePda): Campos {
  return {
    orgao_sigla: b.orgao_sigla,
    organizacao_id: b.orgao_chave.startsWith("sigla:") ? "" : b.orgao_chave,
    nome_previsto: b.nome_previsto,
    descricao: b.descricao ?? "",
    unidade_responsavel: b.unidade_responsavel ?? "",
    periodicidade: b.periodicidade === "Sem informação" ? "" : b.periodicidade,
    prazo_abertura: b.prazo_abertura ?? "",
    politicas_publicas: b.politicas_publicas ?? "",
    sigiloso: b.possui_conteudo_sigiloso == null ? "" : b.possui_conteudo_sigiloso ? "sim" : "nao",
    dataset_link: b.dataset_id != null ? "" : b.dataset_name_planilha ?? "",
  };
}

/** Dataset já vinculado à base, no formato da busca. */
function datasetDaBase(b: BasePda): DatasetOpcao | null {
  if (b.dataset_id == null) return null;
  return {
    id: b.dataset_id,
    id_ckan: b.dataset_id_ckan,
    name: b.dataset_name ?? String(b.dataset_id),
    titulo: b.dataset_titulo ?? b.dataset_name ?? String(b.dataset_id),
    organizacao_id: b.orgao_chave.startsWith("sigla:") ? null : Number(b.orgao_chave),
    orgao_nome: b.orgao_nome,
    ativo_no_portal: b.dataset_ativo ?? true,
  };
}

const ouNulo = (v: string) => (v.trim() ? v.trim() : null);

function entrada(c: Campos, dataset: DatasetOpcao | null): BaseEntrada {
  return {
    orgao_sigla: c.orgao_sigla.trim(),
    organizacao_id: c.organizacao_id ? Number(c.organizacao_id) : null,
    nome_previsto: c.nome_previsto.trim(),
    descricao: ouNulo(c.descricao),
    unidade_responsavel: ouNulo(c.unidade_responsavel),
    periodicidade: ouNulo(c.periodicidade),
    prazo_abertura: ouNulo(c.prazo_abertura),
    politicas_publicas: ouNulo(c.politicas_publicas),
    possui_conteudo_sigiloso: c.sigiloso === "" ? null : c.sigiloso === "sim",
    dataset_id: dataset?.id ?? null,
    dataset_link: dataset ? null : ouNulo(c.dataset_link),
  };
}

const FORM_ID = "pda-base-form";

/** Inclusão e edição manual de uma base prevista do PDA (mesmos campos da planilha). */
export function BaseFormModal({ aberto, plano, base, onFechar, onSalva }: Props) {
  const [c, setC] = useState<Campos>(VAZIO);
  const [dataset, setDataset] = useState<DatasetOpcao | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const opcoes = useQuery({ queryKey: ["pda", "formulario"], queryFn: pdaApi.formulario, enabled: aberto,
    staleTime: 5 * 60_000 });

  useEffect(() => {
    setC(aberto && base ? camposDaBase(base) : VAZIO);
    setDataset(aberto && base ? datasetDaBase(base) : null);
    setErro(null);
  }, [aberto, base]);

  const salvar = useMutation({
    mutationFn: () => (base ? pdaApi.atualizarBase(base.id, entrada(c, dataset))
      : pdaApi.criarBase(plano.id, entrada(c, dataset))),
    onSuccess: (b) => onSalva(b, !base),
    onError: (e: Error) => setErro(e.message),
  });

  const set = (campo: keyof Campos) => (e: { target: { value: string } }) =>
    setC((atual) => ({ ...atual, [campo]: e.target.value }));

  /** O órgão da base acompanha o do dataset escolhido (o backend recusa órgãos incoerentes). */
  function escolherDataset(d: DatasetOpcao | null) {
    setDataset(d);
    if (d) setC((atual) => ({ ...atual, dataset_link: "", organizacao_id: d.organizacao_id != null ? String(d.organizacao_id) : atual.organizacao_id }));
  }

  function enviar(e: FormEvent) {
    e.preventDefault();
    const problema = !c.orgao_sigla.trim() ? "Informe o órgão (sigla)."
      : !c.nome_previsto.trim() ? "Informe o nome da base prevista." : null;
    setErro(problema);
    if (!problema) salvar.mutate();
  }

  const fechar = () => { if (!salvar.isPending) onFechar(); };
  const periodicidades = opcoes.data?.periodicidades ?? [];

  return (
    <Modal aberto={aberto} onFechar={fechar} titulo={base ? "Editar base prevista" : "Incluir base prevista"}
      subtitulo={base ? `${base.nome_previsto} · ${plano.nome}` : plano.nome}
      rodape={<>
        <button type="button" className="btn btn-outline btn-sm" onClick={fechar} disabled={salvar.isPending}>
          Cancelar
        </button>
        <button type="submit" form={FORM_ID} className="btn btn-primary btn-sm" disabled={salvar.isPending}>
          <i className="fa-solid fa-floppy-disk" />{salvar.isPending ? "Salvando…" : base ? "Salvar" : "Incluir base"}
        </button>
      </>}>
      <form id={FORM_ID} className="form-grid" onSubmit={enviar} noValidate>
        <div className="form-field">
          <label htmlFor="pda-base-sigla">Órgão (sigla) *</label>
          <input id="pda-base-sigla" className="text-input" value={c.orgao_sigla} maxLength={100} required
                 placeholder="SEAD" onChange={set("orgao_sigla")} />
        </div>
        <div className="form-field">
          <label htmlFor="pda-base-org">Organização no portal</label>
          <select id="pda-base-org" value={c.organizacao_id} onChange={set("organizacao_id")}>
            <option value="">Identificar pela sigla</option>
            {(opcoes.data?.organizacoes ?? []).map((o) => <option key={o.valor} value={o.valor}>{o.rotulo}</option>)}
          </select>
        </div>
        <div className="form-field full">
          <label htmlFor="pda-base-nome">Base de dados *</label>
          <input id="pda-base-nome" className="text-input" value={c.nome_previsto} maxLength={500} required
                 onChange={set("nome_previsto")} />
        </div>
        <div className="form-field full">
          <label htmlFor="pda-base-desc">Descrição</label>
          <textarea id="pda-base-desc" className="text-input" value={c.descricao} onChange={set("descricao")} />
        </div>
        <div className="form-field full">
          <label htmlFor="pda-base-unidade">Unidade responsável</label>
          <input id="pda-base-unidade" className="text-input" value={c.unidade_responsavel} maxLength={500}
                 onChange={set("unidade_responsavel")} />
        </div>
        <div className="form-field">
          <label htmlFor="pda-base-periodicidade">Atualização (periodicidade)</label>
          <select id="pda-base-periodicidade" value={c.periodicidade} onChange={set("periodicidade")}>
            <option value="">Sem informação</option>
            {/* valor atual fora do domínio (texto antigo) continua selecionável */}
            {c.periodicidade && !periodicidades.includes(c.periodicidade) && (
              <option value={c.periodicidade}>{c.periodicidade}</option>
            )}
            {periodicidades.filter((p) => p !== "Sem informação").map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>
        <div className="form-field">
          <label htmlFor="pda-base-prazo">Meta/Prazo para abertura</label>
          <input id="pda-base-prazo" className="text-input" type="date" value={c.prazo_abertura}
                 onChange={set("prazo_abertura")} />
        </div>
        <div className="form-field">
          <label htmlFor="pda-base-sigiloso">Possui conteúdo sigiloso?</label>
          <select id="pda-base-sigiloso" value={c.sigiloso} onChange={set("sigiloso")}>
            <option value="">Não informado</option>
            <option value="sim">Sim</option>
            <option value="nao">Não</option>
          </select>
        </div>
        <div className="form-field">
          <label htmlFor="pda-base-politicas">Políticas públicas</label>
          <input id="pda-base-politicas" className="text-input" value={c.politicas_publicas} maxLength={500}
                 onChange={set("politicas_publicas")} />
        </div>
        <div className="form-field full">
          <label htmlFor="pda-base-dataset">Dataset no portal</label>
          <DatasetBusca id="pda-base-dataset" valor={dataset} onEscolher={escolherDataset} />
          {!dataset && c.dataset_link && (
            <span className="help">
              <i className="fa-solid fa-triangle-exclamation" /> Vínculo pendente: o name <span className="mono">
              {c.dataset_link}</span> não foi encontrado no inventário. Busque o dataset para vincular ou{" "}
              <button type="button" className="link-btn" onClick={() => setC((a) => ({ ...a, dataset_link: "" }))}>
                descarte o vínculo pendente
              </button>.
            </span>
          )}
          <span className="help">
            Datasets do inventário coletado do portal. O vínculo gravado é o ID do dataset; deixe vazio se a base
            ainda não foi publicada.
          </span>
        </div>
        {opcoes.isError && (
          <div className="inline-msg err full" role="alert">
            Não foi possível carregar as organizações do portal: {opcoes.error.message}
          </div>
        )}
        {erro && <div className="inline-msg err full" role="alert">{erro}</div>}
      </form>
    </Modal>
  );
}
