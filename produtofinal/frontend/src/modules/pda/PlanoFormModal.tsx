import { useMutation } from "@tanstack/react-query";
import type { FormEvent } from "react";
import { useEffect, useState } from "react";
import type { PlanoPda } from "./api";
import { pdaApi } from "./api";
import { Modal } from "@/shared/ui/Modal";

interface Props {
  aberto: boolean;
  /** PDA a editar; null = criar um PDA novo, vazio (sem planilha). */
  plano: PlanoPda | null;
  /** Nenhum PDA cadastrado ainda: o criado vira vigente de qualquer forma. */
  primeiro: boolean;
  onFechar: () => void;
  onSalvo: (plano: PlanoPda, criado: boolean) => void;
}

const FORM_ID = "pda-plano-form";

/** Criação manual e edição de um PDA (nome e vigência). As bases são cadastradas na tela. */
export function PlanoFormModal({ aberto, plano, primeiro, onFechar, onSalvo }: Props) {
  const edicao = plano != null;
  const [nome, setNome] = useState("");
  const [inicio, setInicio] = useState("");
  const [fim, setFim] = useState("");
  const [definirVigente, setDefinirVigente] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  // Preenche ao abrir (edição) e limpa ao fechar. Depende só do ID: recarregar a lista de PDAs
  // enquanto o formulário está aberto não apaga o que foi digitado.
  const planoId = plano?.id ?? null;
  useEffect(() => {
    setNome(aberto && plano ? plano.nome : "");
    setInicio(aberto && plano ? plano.vigencia_inicio ?? "" : "");
    setFim(aberto && plano ? plano.vigencia_fim ?? "" : "");
    setDefinirVigente(false);
    setErro(null);
  }, [aberto, planoId]);

  const salvar = useMutation({
    mutationFn: () => {
      const dados = { nome: nome.trim(), vigencia_inicio: inicio || null, vigencia_fim: fim || null };
      return plano
        ? pdaApi.atualizarPlano(plano.id, dados)
        : pdaApi.criarPlano({ ...dados, definir_vigente: primeiro || definirVigente });
    },
    onSuccess: (p) => onSalvo(p, !edicao),
    onError: (e: Error) => setErro(e.message),
  });

  function enviar(e: FormEvent) {
    e.preventDefault();
    const problema = !nome.trim() ? "Informe o nome do PDA."
      : inicio && fim && fim < inicio ? "O fim da vigência não pode ser anterior ao início." : null;
    setErro(problema);
    if (!problema) salvar.mutate();
  }

  const fechar = () => { if (!salvar.isPending) onFechar(); };

  return (
    <Modal aberto={aberto} onFechar={fechar} titulo={edicao ? "Editar PDA" : "Novo PDA"}
      subtitulo={plano ? plano.nome :"PDA criado manualmente: as bases previstas são incluídas uma a uma."}
      rodape={<>
        <button type="button" className="btn btn-outline btn-sm" onClick={fechar} disabled={salvar.isPending}>
          Cancelar
        </button>
        <button type="submit" form={FORM_ID} className="btn btn-primary btn-sm" disabled={salvar.isPending}>
          <i className="fa-solid fa-floppy-disk" />{salvar.isPending ? "Salvando…" : edicao ? "Salvar" : "Criar PDA"}
        </button>
      </>}>
      <form id={FORM_ID} className="form-grid" onSubmit={enviar} noValidate>
        <div className="form-field full">
          <label htmlFor="pda-plano-nome">Nome do PDA *</label>
          <input id="pda-plano-nome" className="text-input" value={nome} placeholder="PDA 2026-2027"
                 maxLength={200} required onChange={(e) => setNome(e.target.value)} />
        </div>
        <div className="form-field">
          <label htmlFor="pda-plano-inicio">Início da vigência</label>
          <input id="pda-plano-inicio" className="text-input" type="date" value={inicio}
                 onChange={(e) => setInicio(e.target.value)} />
        </div>
        <div className="form-field">
          <label htmlFor="pda-plano-fim">Fim da vigência</label>
          <input id="pda-plano-fim" className="text-input" type="date" value={fim} min={inicio || undefined}
                 onChange={(e) => setFim(e.target.value)} />
        </div>
        {!edicao && (
          <label className="check-line full">
            <input type="checkbox" checked={primeiro || definirVigente} disabled={primeiro}
                   onChange={(e) => setDefinirVigente(e.target.checked)} />
            <span>
              <strong>Definir como vigente</strong> — o PDA vigente rege esta tela e os indicadores e relatórios
              de gestão das bases.
              {primeiro && " Por ser o primeiro PDA cadastrado, ele será o vigente."}
            </span>
          </label>
        )}
        {erro && <div className="inline-msg err full" role="alert">{erro}</div>}
      </form>
    </Modal>
  );
}
