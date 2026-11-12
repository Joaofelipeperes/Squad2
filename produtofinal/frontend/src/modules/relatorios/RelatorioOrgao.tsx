import { useMutation, useQuery } from "@tanstack/react-query";
import type { KeyboardEvent } from "react";
import { useMemo, useState } from "react";
import type { Formato, OrgaoOpcao, Previa } from "./api";
import { relatoriosApi } from "./api";
import { Pode } from "@/shared/acesso/Pode";
import { Modal } from "@/shared/ui/Modal";
import { useToast } from "@/shared/ui/Toast";

const LINHAS_NA_PREVIA = 10; // por seção, na tela (a exportação leva todas)

/** Busca sem diferenciar maiúsculas nem acentos ("saude" acha "Saúde"). */
const normalizar = (t: string) => t.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();

/**
 * Relatório detalhado de um órgão (pedido da GEDA): escolhe o órgão digitando o nome ou a sigla e
 * gera um documento só, com o resumo e, para cada número dele, a lista do que ele conta (bases,
 * atualização, datasets, recursos, dados pessoais). PDF, Excel ou CSV.
 */
export function RelatorioOrgaoPainel() {
  const orgaos = useQuery({ queryKey: ["relatorios", "orgaos"], queryFn: relatoriosApi.orgaos });
  const [orgao, setOrgao] = useState<OrgaoOpcao | null>(null);
  const [aberto, setAberto] = useState(false);

  return (
    <div className="panel">
      <div className="panel-head">
        <div>
          <h3>Relatório de um órgão</h3>
          <div className="sub">
            Um documento só com a situação do órgão: o resumo e, para cada número, a lista do que ele
            conta — quais bases, quais datasets em atraso, quais recursos em formato fechado, onde há
            possíveis dados pessoais.
          </div>
        </div>
      </div>
      <div className="panel-body">
        <div className="form-grid">
          <div className="form-field full">
            <label htmlFor="relatorio-orgao">Órgão *</label>
            <OrgaoBusca id="relatorio-orgao" orgaos={orgaos.data ?? []} carregando={orgaos.isLoading}
              valor={orgao} onEscolher={setOrgao} />
            {orgaos.isError && <span className="help">Não foi possível carregar os órgãos: {orgaos.error.message}</span>}
          </div>
        </div>
        <div className="relatorio-orgao-acoes">
          <span className="help-texto">{orgao ? orgao.nome : "Digite o nome ou a sigla do órgão."}</span>
          <button type="button" className="btn btn-primary btn-sm" disabled={!orgao} onClick={() => setAberto(true)}>
            <i className="fa-solid fa-file-lines" />Gerar relatório
          </button>
        </div>
      </div>
      {aberto && orgao && <RelatorioOrgaoModal orgao={orgao.id} onFechar={() => setAberto(false)} />}
    </div>
  );
}

/**
 * Escolha do órgão por digitação (combobox WAI-ARIA): a lista filtra por nome ou sigla enquanto a
 * pessoa digita; setas, Enter e Esc funcionam. Escolhido, mostra o órgão com a opção de trocar.
 */
function OrgaoBusca({ id, orgaos, carregando, valor, onEscolher }: {
  id: string; orgaos: OrgaoOpcao[]; carregando: boolean; valor: OrgaoOpcao | null;
  onEscolher: (o: OrgaoOpcao | null) => void;
}) {
  const [texto, setTexto] = useState("");
  const [aberto, setAberto] = useState(false);
  const [ativo, setAtivo] = useState(-1);
  const listaId = `${id}-lista`;
  const opcoes = useMemo(() => {
    const termo = normalizar(texto);
    return termo ? orgaos.filter((o) => normalizar(o.nome).includes(termo)) : orgaos;
  }, [orgaos, texto]);

  function escolher(o: OrgaoOpcao) {
    onEscolher(o);
    setTexto("");
    setAberto(false);
    setAtivo(-1);
  }

  function teclado(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      setAberto(true);
      if (!opcoes.length) return;
      const passo = e.key === "ArrowDown" ? 1 : -1;
      setAtivo((i) => (i + passo + opcoes.length) % opcoes.length);
    } else if (e.key === "Enter") {
      e.preventDefault();
      const alvo = ativo >= 0 ? opcoes[ativo] : opcoes.length === 1 ? opcoes[0] : undefined;
      if (aberto && alvo) escolher(alvo);
    } else if (e.key === "Escape" && aberto) {
      e.stopPropagation();
      setAberto(false);
    }
  }

  if (valor) {
    return (
      <div className="dataset-escolhido">
        <strong>{valor.nome}</strong>
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => onEscolher(null)}
                aria-label={`Trocar o órgão ${valor.nome}`}>
          <i className="fa-solid fa-rotate" />Trocar
        </button>
      </div>
    );
  }

  const mostrarLista = aberto && opcoes.length > 0;
  return (
    <>
      <input id={id} className="text-input" type="search" autoComplete="off" value={texto} maxLength={200}
             placeholder={carregando ? "Carregando órgãos…" : "Digite o nome ou a sigla (ex.: SEAD, Saúde)"}
             disabled={carregando} role="combobox" aria-autocomplete="list" aria-controls={listaId}
             aria-expanded={mostrarLista}
             aria-activedescendant={mostrarLista && ativo >= 0 ? `${listaId}-${ativo}` : undefined}
             onChange={(e) => { setTexto(e.target.value); setAberto(true); setAtivo(-1); }}
             onFocus={() => setAberto(true)} onBlur={() => setAberto(false)} onKeyDown={teclado} />
      <ul id={listaId} role="listbox" className="busca-lista" aria-label="Órgãos encontrados" hidden={!mostrarLista}>
        {opcoes.map((o, i) => (
          <li key={o.id} id={`${listaId}-${i}`} role="option" aria-selected={i === ativo}
              onMouseDown={(e) => e.preventDefault()} onClick={() => escolher(o)}>
            {o.nome}
          </li>
        ))}
      </ul>
      {aberto && texto.trim() !== "" && opcoes.length === 0 && (
        <span className="help" role="status">Nenhum órgão com esse nome ou sigla.</span>
      )}
    </>
  );
}

/** Prévia do relatório detalhado do órgão (10 linhas por seção) e as exportações. Também usado
 *  no detalhe do órgão em Organizações. */
export function RelatorioOrgaoModal({ orgao, onFechar }: { orgao: number; onFechar: () => void }) {
  const toast = useToast();
  const previa = useQuery({
    queryKey: ["relatorios", "por-orgao", orgao],
    queryFn: () => relatoriosApi.previaOrgao(orgao),
  });
  const exportar = useMutation({
    mutationFn: (formato: Formato) => relatoriosApi.exportarOrgao(orgao, formato),
    onSuccess: () => toast("Relatório exportado."),
    onError: (e: Error) => toast(e.message, true),
  });
  const p = previa.data;

  return (
    <Modal aberto largo onFechar={onFechar}
      titulo={p ? `Relatório do órgão — ${p.orgao.nome}` : "Relatório do órgão"}
      subtitulo={p ? `${p.secoes.length} seção(ões) · prévia das ${LINHAS_NA_PREVIA} primeiras linhas de cada uma; o arquivo leva tudo` : "Gerando prévia..."}
      rodape={<>
        <button className="btn btn-outline btn-sm" onClick={onFechar}>Fechar</button>
        <Pode permissao="relatorios.exportar">
          <button className="btn btn-outline btn-sm" disabled={!p || exportar.isPending} onClick={() => exportar.mutate("csv")}>
            <i className="fa-solid fa-file-csv" />Exportar CSV
          </button>
          <button className="btn btn-outline btn-sm" disabled={!p || exportar.isPending} onClick={() => exportar.mutate("xlsx")}>
            <i className="fa-solid fa-file-excel" />Exportar Excel
          </button>
          <button className="btn btn-primary btn-sm" disabled={!p || exportar.isPending} onClick={() => exportar.mutate("pdf")}>
            <i className="fa-solid fa-file-pdf" />{exportar.isPending ? "Exportando..." : "Exportar PDF"}
          </button>
        </Pode>
      </>}>
      {previa.isLoading && <div className="table-empty">Gerando prévia...</div>}
      {previa.isError && <div className="table-empty">Não foi possível gerar a prévia: {previa.error.message}</div>}
      {p?.secoes.map((s) => <Secao key={s.id} s={s} />)}
    </Modal>
  );
}

function Secao({ s }: { s: Previa }) {
  const linhas = s.linhas.slice(0, LINHAS_NA_PREVIA);
  const info = [s.referencia, `${s.total} ${s.total === 1 ? "linha" : "linhas"}`,
    s.total > linhas.length ? `mostrando ${linhas.length}` : null].filter(Boolean).join(" · ");
  return (
    <section className="relatorio-secao">
      <h4>{s.titulo}</h4>
      <div className="sub">{info}</div>
      <div className="table-scroll relatorio-previa">
        <table>
          <thead><tr>{s.colunas.map((c) => <th key={c}>{c}</th>)}</tr></thead>
          <tbody>
            {linhas.length === 0
              ? <tr><td colSpan={s.colunas.length} className="table-empty">Nenhum registro deste órgão.</td></tr>
              : linhas.map((linha, i) => (
                <tr key={i}>{linha.map((v, j) => <td key={j} className={v ? undefined : "cell-muted"}>{v || "—"}</td>)}</tr>
              ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
