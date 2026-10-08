import { useMutation } from "@tanstack/react-query";
import type { FormEvent } from "react";
import { useEffect, useState } from "react";
import type { ImportacaoResumo } from "./api";
import { TAMANHO_MAX_ARQUIVO, pdaApi } from "./api";
import { plural } from "./formato";
import { ApiError } from "@/shared/api/client";
import { Modal } from "@/shared/ui/Modal";

interface Props {
  aberto: boolean;
  /** Nenhum PDA cadastrado ainda: o importado vira vigente de qualquer forma. */
  primeiro: boolean;
  onFechar: () => void;
  /** Chamado assim que a importação conclui (a tela seleciona o PDA novo e recarrega). */
  onImportado: (resumo: ImportacaoResumo) => void;
}

const EXTENSOES = [".xlsx", ".csv"];
const FORM_ID = "pda-importar-form";

/** Importação da planilha do PDA (PBI-12): formulário e, após o envio, o resumo da importação. */
export function ImportarPdaModal({ aberto, primeiro, onFechar, onImportado }: Props) {
  const [nome, setNome] = useState("");
  const [inicio, setInicio] = useState("");
  const [fim, setFim] = useState("");
  const [arquivo, setArquivo] = useState<File | null>(null);
  const [definirVigente, setDefinirVigente] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [resumo, setResumo] = useState<ImportacaoResumo | null>(null);

  // Limpa o formulário ao fechar (o Modal não renderiza nada fechado; evita piscar o resumo anterior).
  useEffect(() => {
    if (aberto) return;
    setNome(""); setInicio(""); setFim(""); setArquivo(null);
    setDefinirVigente(false); setErro(null); setResumo(null);
  }, [aberto]);

  const importar = useMutation({
    mutationFn: (form: FormData) => pdaApi.importar(form),
    onSuccess: (r) => { setResumo(r); onImportado(r); },
    onError: (e: Error) => setErro(
      e instanceof ApiError && e.status === 413 && e.message.startsWith("Erro ")
        ? "Arquivo maior que o limite de 5 MB." : e.message),
  });

  function validar(): string | null {
    if (!nome.trim()) return "Informe o nome do PDA.";
    if (!arquivo) return "Selecione a planilha do PDA (.xlsx ou .csv).";
    const nomeArq = arquivo.name.toLowerCase();
    if (!EXTENSOES.some((ext) => nomeArq.endsWith(ext))) return "O arquivo deve ser .xlsx ou .csv.";
    if (arquivo.size > TAMANHO_MAX_ARQUIVO) return "Arquivo maior que o limite de 5 MB.";
    if (inicio && fim && fim < inicio) return "O fim da vigência não pode ser anterior ao início.";
    return null;
  }

  function enviar(e: FormEvent) {
    e.preventDefault();
    const problema = validar();
    setErro(problema);
    if (problema || !arquivo) return;
    const form = new FormData();
    form.append("nome", nome.trim());
    if (inicio) form.append("vigencia_inicio", inicio);
    if (fim) form.append("vigencia_fim", fim);
    form.append("definir_vigente", primeiro || definirVigente ? "true" : "false");
    form.append("arquivo", arquivo, arquivo.name);
    importar.mutate(form);
  }

  const fechar = () => { if (!importar.isPending) onFechar(); };

  if (resumo) {
    return (
      <Modal aberto={aberto} onFechar={fechar} titulo="PDA importado"
        subtitulo={`${resumo.plano.nome}${resumo.plano.arquivo_nome ? ` · ${resumo.plano.arquivo_nome}` : ""}`}
        rodape={<button type="button" className="btn btn-primary btn-sm" onClick={onFechar}>
          <i className="fa-solid fa-check" />Concluir
        </button>}>
        <ResumoImportacao resumo={resumo} />
      </Modal>
    );
  }

  return (
    <Modal aberto={aberto} onFechar={fechar} titulo="Importar PDA"
      subtitulo="Planilha do Plano de Dados Abertos (.xlsx ou .csv), com uma linha por base prevista."
      rodape={<>
        <button type="button" className="btn btn-outline btn-sm" onClick={fechar} disabled={importar.isPending}>
          Cancelar
        </button>
        <button type="submit" form={FORM_ID} className="btn btn-primary btn-sm" disabled={importar.isPending}>
          <i className="fa-solid fa-file-import" />{importar.isPending ? "Importando…" : "Importar"}
        </button>
      </>}>
      <form id={FORM_ID} className="form-grid" onSubmit={enviar} noValidate>
        <div className="form-field full">
          <label htmlFor="pda-imp-nome">Nome do PDA *</label>
          <input id="pda-imp-nome" className="text-input" value={nome} placeholder="PDA 2026-2027"
                 maxLength={200} required onChange={(e) => setNome(e.target.value)} />
          <span className="help">Identifica o plano na tela e nos relatórios. Não pode repetir o nome de outro PDA.</span>
        </div>
        <div className="form-field">
          <label htmlFor="pda-imp-inicio">Início da vigência</label>
          <input id="pda-imp-inicio" className="text-input" type="date" value={inicio}
                 onChange={(e) => setInicio(e.target.value)} />
        </div>
        <div className="form-field">
          <label htmlFor="pda-imp-fim">Fim da vigência</label>
          <input id="pda-imp-fim" className="text-input" type="date" value={fim} min={inicio || undefined}
                 onChange={(e) => setFim(e.target.value)} />
        </div>
        <div className="form-field full">
          <label htmlFor="pda-imp-arquivo">Arquivo (.xlsx, .csv) *</label>
          <input id="pda-imp-arquivo" className="text-input" type="file" accept=".xlsx,.csv"
                 required onChange={(e) => setArquivo(e.target.files?.[0] ?? null)} />
          <span className="help">
            Colunas lidas pelo cabeçalho: Orgão, Base de Dados, Descrição, Unidade Responsável, Atualização,
            Políticas Públicas, Possui Conteúdo Sigiloso?, Disponível no Portal e, opcionalmente, Prazo.
            Limite de 5 MB. O arquivo não é guardado; só os dados extraídos.
          </span>
        </div>
        <label className="check-line full">
          <input type="checkbox" checked={primeiro || definirVigente} disabled={primeiro}
                 onChange={(e) => setDefinirVigente(e.target.checked)} />
          <span>
            <strong>Definir como vigente</strong> — o PDA vigente rege esta tela e os indicadores e relatórios
            de gestão das bases.
            {primeiro && " Por ser o primeiro PDA cadastrado, ele será o vigente."}
          </span>
        </label>
        {erro && <div className="inline-msg err full" role="alert">{erro}</div>}
      </form>
    </Modal>
  );
}

function ResumoImportacao({ resumo }: { resumo: ImportacaoResumo }) {
  const r = resumo;
  return (
    <>
      <div className="inline-msg ok">
        {plural(r.bases_importadas, "base prevista importada", "bases previstas importadas")} para o
        “{r.plano.nome}”.{r.plano.vigente && " Este é o PDA vigente."}
      </div>
      {!r.tem_coluna_prazo && (
        <div className="inline-msg err" style={{ marginTop: 10 }} role="alert">
          A planilha não tem a coluna “Prazo” (ou “Prazo de abertura”): as bases não publicadas aparecem
          como “Não publicado” e os filtros Ano e Prazo ficam vazios.
        </div>
      )}
      {r.colunas_opcionais_ausentes.filter((c) => c !== "Prazo").length > 0 && (
        <p className="help-texto" style={{ marginTop: 8 }}>
          Colunas opcionais não encontradas:{" "}
          {r.colunas_opcionais_ausentes.filter((c) => c !== "Prazo").join(", ")}.
        </p>
      )}
      <div className="def-grid" style={{ marginTop: 16 }}>
        <div className="def-item"><label>Bases importadas</label><div className="val">{r.bases_importadas}</div></div>
        <div className="def-item"><label>Linhas ignoradas</label><div className="val">{r.linhas_ignoradas.length}</div></div>
        <div className="def-item"><label>Vínculos resolvidos</label><div className="val">{r.vinculos_resolvidos}</div></div>
        <div className="def-item">
          <label>Vínculos pendentes</label>
          <div className="val">{r.vinculos_pendentes}</div>
        </div>
        <div className="def-item"><label>Sem vínculo (não publicadas)</label><div className="val">{r.sem_vinculo}</div></div>
        <div className="def-item">
          <label>Órgãos sem correspondência</label>
          <div className="val">{r.orgaos_sem_correspondencia.length}</div>
        </div>
      </div>
      {r.vinculos_pendentes > 0 && (
        <p className="help-texto" style={{ marginTop: 12 }}>
          Vínculo pendente: a URL do portal informada na planilha não corresponde a nenhum dataset do inventário
          atual. Depois da próxima coleta, use “Atualizar vínculos” na tela do PDA.
        </p>
      )}
      {r.linhas_ignoradas.length > 0 && (
        <div className="def-item full" style={{ marginTop: 16 }}>
          <label>Linhas ignoradas</label>
          <div className="lista-rolavel">
            {r.linhas_ignoradas.map((l) => (
              <div key={`${l.linha}-${l.motivo}`} className="hist-row">
                <span className="date">Linha {l.linha}</span><span>{l.motivo}</span>
              </div>
            ))}
          </div>
        </div>
      )}
      {r.orgaos_sem_correspondencia.length > 0 && (
        <div className="def-item full" style={{ marginTop: 16 }}>
          <label>Órgãos sem correspondência no portal</label>
          <div className="lista-badges">
            {r.orgaos_sem_correspondencia.map((s) => <span key={s} className="badge badge-gray">{s}</span>)}
          </div>
          <p className="help-texto" style={{ marginTop: 6 }}>
            Siglas da planilha que não foram associadas a uma organização do CKAN. As bases continuam
            monitoradas pela sigla; usuários restritos a um órgão não as veem.
          </p>
        </div>
      )}
    </>
  );
}
