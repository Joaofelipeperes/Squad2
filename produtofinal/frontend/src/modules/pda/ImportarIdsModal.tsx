import { useMutation } from "@tanstack/react-query";
import type { FormEvent } from "react";
import { useEffect, useState } from "react";
import type { IdsCkanResumo, LinhaIdCkan, PlanoPda } from "./api";
import { TAMANHO_MAX_ARQUIVO, pdaApi } from "./api";
import { abreviarId, plural } from "./formato";
import { ApiError } from "@/shared/api/client";
import { Modal } from "@/shared/ui/Modal";

interface Props {
  aberto: boolean;
  plano: PlanoPda;
  onFechar: () => void;
  /** Chamado depois de gravar (a tela recarrega as bases). */
  onGravado: (resumo: IdsCkanResumo) => void;
}

const FORM_ID = "pda-ids-form";

/**
 * Importação em lote do ID do CKAN de cada base (CSV SIGLA, NOME_PDA, NOME_DATASET, ID_DATASET).
 * Duas etapas: análise (nada é gravado) com o resumo e, se houver, a confirmação para sobrescrever IDs
 * diferentes; depois a gravação e o resumo final.
 */
export function ImportarIdsModal({ aberto, plano, onFechar, onGravado }: Props) {
  const [arquivo, setArquivo] = useState<File | null>(null);
  const [analise, setAnalise] = useState<IdsCkanResumo | null>(null);
  const [final, setFinal] = useState<IdsCkanResumo | null>(null);
  const [sobrescrever, setSobrescrever] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    if (aberto) return;
    setArquivo(null); setAnalise(null); setFinal(null); setSobrescrever(false); setErro(null);
  }, [aberto]);

  const enviar = useMutation({
    mutationFn: (aplicar: boolean) => {
      if (!arquivo) throw new Error("Selecione o arquivo.");
      return pdaApi.importarIds(plano.id, arquivo, aplicar, aplicar && sobrescrever);
    },
    onSuccess: (r) => {
      setErro(null);
      if (r.aplicado) { setFinal(r); onGravado(r); } else setAnalise(r);
    },
    onError: (e: Error) => setErro(
      e instanceof ApiError && e.status === 413 && e.message.startsWith("Erro ")
        ? "Arquivo maior que o limite de 5 MB." : e.message),
  });

  function analisar(e: FormEvent) {
    e.preventDefault();
    const nome = arquivo?.name.toLowerCase() ?? "";
    const problema = !arquivo ? "Selecione o arquivo CSV com os IDs."
      : !nome.endsWith(".csv") && !nome.endsWith(".xlsx") ? "O arquivo deve ser .csv (ou .xlsx)."
      : arquivo.size > TAMANHO_MAX_ARQUIVO ? "Arquivo maior que o limite de 5 MB." : null;
    setErro(problema);
    if (!problema) enviar.mutate(false);
  }

  const fechar = () => { if (!enviar.isPending) onFechar(); };

  if (final) {
    return (
      <Modal aberto={aberto} onFechar={fechar} titulo="IDs do CKAN importados" subtitulo={plano.nome}
        rodape={<button type="button" className="btn btn-primary btn-sm" onClick={onFechar}>
          <i className="fa-solid fa-check" />Concluir
        </button>}>
        <div className="inline-msg ok">
          {plural(final.atualizadas, "base atualizada", "bases atualizadas")} com o ID do dataset no CKAN.
        </div>
        <Resumo r={final} />
      </Modal>
    );
  }

  if (analise) {
    const gravar = analise.atualizar.length + (sobrescrever ? analise.substituir.length : 0);
    return (
      <Modal aberto={aberto} onFechar={fechar} titulo="Importar IDs do CKAN · conferir"
        subtitulo={`${plano.nome} · ${arquivo?.name ?? ""}`}
        rodape={<>
          <button type="button" className="btn btn-outline btn-sm" disabled={enviar.isPending}
            onClick={() => { setAnalise(null); setSobrescrever(false); }}>
            <i className="fa-solid fa-arrow-left" />Voltar
          </button>
          <button type="button" className="btn btn-primary btn-sm" disabled={enviar.isPending || gravar === 0}
            onClick={() => enviar.mutate(true)}>
            <i className="fa-solid fa-link" />
            {enviar.isPending ? "Gravando…" : `Gravar ${plural(gravar, "ID", "IDs")}`}
          </button>
        </>}>
        <p className="help-texto">Análise do arquivo: nada foi gravado ainda.</p>
        <Resumo r={analise} />
        {analise.substituir.length > 0 && (
          <label className="check-line" style={{ marginTop: 14 }}>
            <input type="checkbox" checked={sobrescrever} onChange={(e) => setSobrescrever(e.target.checked)} />
            <span>
              <strong>Sobrescrever {plural(analise.substituir.length, "base que já tem", "bases que já têm")} outro
              ID</strong> — sem marcar, essas bases ficam com o ID atual.
            </span>
          </label>
        )}
        {erro && <div className="inline-msg err" role="alert" style={{ marginTop: 10 }}>{erro}</div>}
      </Modal>
    );
  }

  return (
    <Modal aberto={aberto} onFechar={fechar} titulo="Importar IDs do CKAN"
      subtitulo={`Grava o ID do dataset no portal nas bases do ${plano.nome}.`}
      rodape={<>
        <button type="button" className="btn btn-outline btn-sm" onClick={fechar} disabled={enviar.isPending}>
          Cancelar
        </button>
        <button type="submit" form={FORM_ID} className="btn btn-primary btn-sm" disabled={enviar.isPending}>
          <i className="fa-solid fa-magnifying-glass" />{enviar.isPending ? "Analisando…" : "Analisar arquivo"}
        </button>
      </>}>
      <form id={FORM_ID} className="form-grid" onSubmit={analisar} noValidate>
        <div className="form-field full">
          <label htmlFor="pda-ids-arquivo">Arquivo CSV *</label>
          <input id="pda-ids-arquivo" className="text-input" type="file" accept=".csv,.xlsx" required
                 onChange={(e) => setArquivo(e.target.files?.[0] ?? null)} />
          <span className="help">
            Colunas SIGLA, NOME_PDA e ID_DATASET (ou ID_UNICO); NOME_ORGAO e NOME_DATASET são opcionais. Cada
            linha vai para a base com a mesma sigla e nome no PDA (sem diferença de maiúsculas, acentos e
            espaços). UTF-8 ou Latin-1, separador “;” ou “,”. Linhas sem ID (“Não encontrado”) são ignoradas.
          </span>
        </div>
        {erro && <div className="inline-msg err full" role="alert">{erro}</div>}
      </form>
    </Modal>
  );
}

function Resumo({ r }: { r: IdsCkanResumo }) {
  return (
    <>
      <div className="def-grid" style={{ marginTop: 12 }}>
        <div className="def-item"><label>Linhas no arquivo</label><div className="val">{r.total_linhas}</div></div>
        <div className="def-item"><label>Bases sem ID que recebem</label><div className="val">{r.atualizar.length}</div></div>
        <div className="def-item"><label>Bases com outro ID</label><div className="val">{r.substituir.length}</div></div>
        <div className="def-item"><label>Já com o mesmo ID</label><div className="val">{r.iguais}</div></div>
        <div className="def-item"><label>Sem base correspondente</label><div className="val">{r.sem_base.length}</div></div>
        <div className="def-item"><label>Com problema no ID</label><div className="val">{r.invalidas.length}</div></div>
        <div className="def-item"><label>Linhas sem ID</label><div className="val">{r.sem_id}</div></div>
      </div>
      <Lista titulo="Bases que já têm outro ID" linhas={r.substituir}
        detalhe={(l) => `${abreviarId(l.id_atual ?? "")} → ${abreviarId(l.dataset_id ?? "")}`} />
      <Lista titulo="Linhas sem base correspondente no PDA" linhas={r.sem_base} detalhe={(l) => l.motivo ?? ""} />
      <Lista titulo="Linhas com problema no ID" linhas={r.invalidas}
        detalhe={(l) => `${l.dataset_id ?? ""} · ${l.motivo ?? ""}`} />
    </>
  );
}

function Lista({ titulo, linhas, detalhe }: {
  titulo: string; linhas: LinhaIdCkan[]; detalhe: (l: LinhaIdCkan) => string;
}) {
  if (linhas.length === 0) return null;
  return (
    <div className="def-item full" style={{ marginTop: 16 }}>
      <label>{titulo} ({linhas.length})</label>
      <div className="lista-rolavel">
        {linhas.map((l) => (
          <div key={`${l.linha}-${l.dataset_id}`} className="hist-row">
            <span className="date">Linha {l.linha}</span>
            <span><strong>{l.sigla}</strong> · {l.nome_pda} — <span className="mono">{detalhe(l)}</span></span>
          </div>
        ))}
      </div>
    </div>
  );
}
