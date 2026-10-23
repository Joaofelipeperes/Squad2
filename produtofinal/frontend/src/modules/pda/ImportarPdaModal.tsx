import { useMutation } from "@tanstack/react-query";
import type { FormEvent } from "react";
import { useEffect, useState } from "react";
import type { ColunasPlanilha, ImportacaoResumo } from "./api";
import { TAMANHO_MAX_ARQUIVO, pdaApi } from "./api";
import { plural } from "./formato";
import type { Escolhas } from "./MapeamentoColunas";
import { MapeamentoColunas, escolhasIniciais, pendentes } from "./MapeamentoColunas";
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

/**
 * Importação da planilha do PDA (PBI-12) em etapas: dados do PDA e arquivo → mapeamento das colunas
 * (campo do sistema × coluna da planilha, com prévia) → resumo da importação. O arquivo é enviado de
 * novo na confirmação: o servidor não guarda a planilha.
 */
export function ImportarPdaModal({ aberto, primeiro, onFechar, onImportado }: Props) {
  const [nome, setNome] = useState("");
  const [inicio, setInicio] = useState("");
  const [fim, setFim] = useState("");
  const [arquivo, setArquivo] = useState<File | null>(null);
  const [definirVigente, setDefinirVigente] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [resumo, setResumo] = useState<ImportacaoResumo | null>(null);
  const [colunas, setColunas] = useState<ColunasPlanilha | null>(null);
  const [escolhas, setEscolhas] = useState<Escolhas>({});

  // Limpa o formulário ao fechar (o Modal não renderiza nada fechado; evita piscar o resumo anterior).
  useEffect(() => {
    if (aberto) return;
    setNome(""); setInicio(""); setFim(""); setArquivo(null);
    setDefinirVigente(false); setErro(null); setResumo(null); setColunas(null); setEscolhas({});
  }, [aberto]);

  const erroDeEnvio = (e: Error) =>
    e instanceof ApiError && e.status === 413 && e.message.startsWith("Erro ")
      ? "Arquivo maior que o limite de 5 MB." : e.message;

  const lerColunas = useMutation({
    mutationFn: (f: File) => pdaApi.colunasPlanilha(f),
    onSuccess: (c) => { setColunas(c); setEscolhas(escolhasIniciais(c)); setErro(null); },
    onError: (e: Error) => setErro(erroDeEnvio(e)),
  });

  const importar = useMutation({
    mutationFn: (form: FormData) => pdaApi.importar(form),
    onSuccess: (r) => { setResumo(r); onImportado(r); },
    onError: (e: Error) => setErro(erroDeEnvio(e)),
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

  /** Etapa 1 → 2: lê o cabeçalho da planilha para o mapeamento. */
  function continuar(e: FormEvent) {
    e.preventDefault();
    const problema = validar();
    setErro(problema);
    if (!problema && arquivo) lerColunas.mutate(arquivo);
  }

  /** Etapa 2: importa com as colunas escolhidas. */
  function importarMapeado() {
    if (!arquivo || !colunas || pendentes(colunas, escolhas).length > 0) return;
    const mapa = Object.fromEntries(Object.entries(escolhas).filter(([, i]) => i != null));
    const form = new FormData();
    form.append("nome", nome.trim());
    if (inicio) form.append("vigencia_inicio", inicio);
    if (fim) form.append("vigencia_fim", fim);
    form.append("definir_vigente", primeiro || definirVigente ? "true" : "false");
    form.append("arquivo", arquivo, arquivo.name);
    form.append("mapeamento", JSON.stringify({ aba: colunas.aba, linha: colunas.linha, colunas: mapa }));
    setErro(null);
    importar.mutate(form);
  }

  const ocupado = importar.isPending || lerColunas.isPending;
  const fechar = () => { if (!ocupado) onFechar(); };

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

  if (colunas) {
    const faltando = pendentes(colunas, escolhas).length;
    return (
      <Modal aberto={aberto} onFechar={fechar} titulo="Importar PDA · mapear colunas"
        subtitulo={`${nome.trim()} · ${arquivo?.name ?? ""}`}
        rodape={<>
          <button type="button" className="btn btn-outline btn-sm" disabled={ocupado}
            onClick={() => { setColunas(null); setErro(null); }}>
            <i className="fa-solid fa-arrow-left" />Voltar
          </button>
          <button type="button" className="btn btn-primary btn-sm" disabled={ocupado || faltando > 0}
            title={faltando > 0 ? "Escolha a coluna dos campos obrigatórios" : undefined} onClick={importarMapeado}>
            <i className="fa-solid fa-file-import" />{importar.isPending ? "Importando…" : "Importar"}
          </button>
        </>}>
        <MapeamentoColunas colunas={colunas} escolhas={escolhas} onMudar={setEscolhas} />
        {erro && <div className="inline-msg err" role="alert" style={{ marginTop: 10 }}>{erro}</div>}
      </Modal>
    );
  }

  return (
    <Modal aberto={aberto} onFechar={fechar} titulo="Importar PDA"
      subtitulo="Planilha do Plano de Dados Abertos (.xlsx ou .csv), com uma linha por base prevista."
      rodape={<>
        <button type="button" className="btn btn-outline btn-sm" onClick={fechar} disabled={ocupado}>
          Cancelar
        </button>
        <button type="submit" form={FORM_ID} className="btn btn-primary btn-sm" disabled={ocupado}>
          <i className="fa-solid fa-arrow-right" />{lerColunas.isPending ? "Lendo colunas…" : "Continuar"}
        </button>
      </>}>
      <form id={FORM_ID} className="form-grid" onSubmit={continuar} noValidate>
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
                 required onChange={(e) => { setArquivo(e.target.files?.[0] ?? null); setColunas(null); }} />
          <span className="help">
            Na próxima etapa você confere qual coluna da planilha corresponde a cada campo (Órgão e Base de
            Dados são obrigatórios; Descrição, Unidade Responsável, Atualização, Meta/Prazo para abertura,
            Políticas Públicas, Possui Conteúdo Sigiloso? e Disponível no Portal, opcionais). Prazo em mês/ano
            (ex.: Março/2025, vale até o fim do mês) ou data. Limite de 5 MB. O arquivo não é guardado; só os
            dados extraídos.
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

/** Colunas opcionais ausentes, menos as que já têm aviso próprio (prazo e portal). */
const COM_AVISO_PROPRIO = ["Meta/Prazo para abertura", "Disponível no Portal"];
const outrasAusentes = (r: ImportacaoResumo) =>
  r.colunas_opcionais_ausentes.filter((c) => !COM_AVISO_PROPRIO.includes(c));

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
          A planilha não tem a coluna “Meta/Prazo para abertura” (ou “Prazo”): as bases não publicadas
          aparecem como “Não publicado” e os filtros Ano e Prazo ficam vazios.
        </div>
      )}
      {!r.tem_coluna_portal && (
        <div className="inline-msg err" style={{ marginTop: 10 }} role="alert">
          A planilha não tem a coluna “Disponível no Portal”: nenhuma base foi vinculada a um dataset do
          portal, então nenhuma aparece como publicada.
        </div>
      )}
      {outrasAusentes(r).length > 0 && (
        <p className="help-texto" style={{ marginTop: 8 }}>
          Colunas opcionais não encontradas: {outrasAusentes(r).join(", ")}.
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
