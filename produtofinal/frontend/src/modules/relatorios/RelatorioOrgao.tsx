import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import type { Formato, Previa, Relatorio } from "./api";
import { relatoriosApi } from "./api";
import { Pode } from "@/shared/acesso/Pode";
import { Modal } from "@/shared/ui/Modal";
import { useToast } from "@/shared/ui/Toast";

const LINHAS_NA_PREVIA = 10; // por seção, na tela (a exportação leva todas)
// Para um órgão, o relatório comparativo de todos os órgãos vira o "Resumo do órgão": primeira
// opção da marcação (já marcada) e, quando escolhido, primeira seção do documento
const RESUMO = "orgaos";

/** Estado da marcação dos relatórios de um órgão (usado aqui e no detalhe do órgão). */
function useEscolha(catalogo: Relatorio[]) {
  const resumo = catalogo.find((r) => r.id === RESUMO);
  const relatorios = [
    ...(resumo ? [{ ...resumo, titulo: "Resumo do órgão" }] : []),
    ...catalogo.filter((r) => r.id !== RESUMO),
  ];
  // Resumo marcado por padrão (quando o catálogo chega depois, entra na primeira carga)
  const [marcados, setMarcados] = useState<string[] | null>(null);
  const atuais = marcados ?? (resumo ? [RESUMO] : []);
  // Ordem da lista (resumo primeiro, depois o catálogo), qualquer que seja a ordem das marcações
  const escolhidos = relatorios.map((r) => r.id).filter((id) => atuais.includes(id));
  const outros = escolhidos.filter((id) => id !== RESUMO).length;
  const conteudo = [escolhidos.includes(RESUMO) ? "Resumo do órgão" : null,
    outros ? `${outros} relatório(s)` : null].filter(Boolean).join(" + ");
  return {
    relatorios, temResumo: !!resumo, marcados: atuais, setMarcados, escolhidos, conteudo,
    vazio: escolhidos.length === 0,
  };
}

function EscolhaRelatorios({ escolha }: { escolha: ReturnType<typeof useEscolha> }) {
  const { relatorios, marcados, setMarcados } = escolha;
  const todos = relatorios.length > 0 && marcados.length === relatorios.length;
  const alternar = (id: string) =>
    setMarcados(marcados.includes(id) ? marcados.filter((x) => x !== id) : [...marcados, id]);
  return (
    <fieldset className="form-field full relatorio-orgao-lista">
      <legend>
        Relatórios *
        <button type="button" className="btn-link" onClick={() => setMarcados(todos ? [] : relatorios.map((r) => r.id))}>
          {todos ? "Desmarcar todos" : "Marcar todos"}
        </button>
      </legend>
      {relatorios.map((r) => (
        <label key={r.id} className="check-line">
          <input type="checkbox" checked={marcados.includes(r.id)} onChange={() => alternar(r.id)} />
          <span><i className={`fa-solid ${r.icone}`} style={{ marginRight: 6, color: "var(--gray-500)" }} />{r.titulo}</span>
        </label>
      ))}
    </fieldset>
  );
}

/**
 * Relatório de um órgão: escolhe o órgão e quantos relatórios quiser; o resumo do órgão, se
 * marcado, abre o documento, que segue com uma seção por relatório, só com as linhas daquele órgão
 * (PDF, Excel ou CSV).
 */
export function RelatorioOrgaoPainel({ relatorios: catalogo }: { relatorios: Relatorio[] }) {
  const escolha = useEscolha(catalogo);
  const orgaos = useQuery({ queryKey: ["relatorios", "orgaos"], queryFn: relatoriosApi.orgaos });
  const [orgao, setOrgao] = useState("");
  const [aberto, setAberto] = useState(false);
  const nomeOrgao = orgaos.data?.find((o) => String(o.id) === orgao)?.nome ?? "";
  const falta = !orgao ? "Escolha o órgão." : escolha.vazio ? "Marque ao menos um relatório." : null;

  return (
    <div className="panel">
      <div className="panel-head">
        <div>
          <h3>Relatório de um órgão</h3>
          <div className="sub">
            Escolha o órgão e os relatórios: tudo sai num documento só, apenas com os dados dele.
            {escolha.temResumo && " O resumo do órgão (indicadores gerais), se marcado, abre o documento."}
          </div>
        </div>
      </div>
      <div className="panel-body">
        <div className="form-grid">
          <div className="form-field full">
            <label htmlFor="relatorio-orgao">Órgão *</label>
            <select id="relatorio-orgao" value={orgao} onChange={(e) => setOrgao(e.target.value)}
              disabled={!orgaos.data}>
              <option value="">{orgaos.isLoading ? "Carregando órgãos…" : "Selecione o órgão"}</option>
              {orgaos.data?.map((o) => <option key={o.id} value={o.id}>{o.nome}</option>)}
            </select>
            {orgaos.isError && <span className="help">Não foi possível carregar os órgãos: {orgaos.error.message}</span>}
          </div>
          <EscolhaRelatorios escolha={escolha} />
        </div>
        <div className="relatorio-orgao-acoes">
          <span className="help-texto">{falta ?? `${escolha.conteudo} · ${nomeOrgao}`}</span>
          <button type="button" className="btn btn-primary btn-sm" disabled={!!falta} onClick={() => setAberto(true)}>
            <i className="fa-solid fa-file-lines" />Gerar relatório
          </button>
        </div>
      </div>
      {aberto && orgao && (
        <RelatorioOrgaoModal orgao={Number(orgao)} relatorios={escolha.escolhidos} onFechar={() => setAberto(false)} />
      )}
    </div>
  );
}

/**
 * Relatório de um órgão já escolhido (ex.: detalhe do órgão em Organizações): marca os relatórios
 * e gera o documento do órgão, com a mesma prévia e as mesmas exportações da tela Relatórios.
 */
export function GerarRelatorioOrgaoModal({ orgao, nome, onFechar }: {
  orgao: number; nome: string; onFechar: () => void;
}) {
  const lista = useQuery({ queryKey: ["relatorios"], queryFn: relatoriosApi.lista });
  const escolha = useEscolha(lista.data ?? []);
  const [gerado, setGerado] = useState(false);

  if (gerado) {
    return <RelatorioOrgaoModal orgao={orgao} relatorios={escolha.escolhidos} onFechar={onFechar} />;
  }
  return (
    <Modal aberto titulo={`Gerar relatório — ${nome}`}
      subtitulo={escolha.temResumo
        ? "Marque o que deve entrar no documento; o resumo do órgão, se marcado, vem primeiro."
        : "Marque os relatórios que devem entrar no documento."}
      onFechar={onFechar}
      rodape={<>
        <button type="button" className="btn btn-outline btn-sm" onClick={onFechar}>Cancelar</button>
        <button type="button" className="btn btn-primary btn-sm" disabled={!lista.data || escolha.vazio}
          onClick={() => setGerado(true)}>
          <i className="fa-solid fa-file-lines" />Gerar relatório
        </button>
      </>}>
      {lista.isLoading && <div className="table-empty">Carregando relatórios...</div>}
      {lista.isError && <div className="table-empty">Não foi possível carregar os relatórios: {lista.error.message}</div>}
      {lista.data && (
        <>
          <div className="form-grid"><EscolhaRelatorios escolha={escolha} /></div>
          <p className="help-texto" style={{ marginTop: 8 }}>
            {escolha.vazio ? "Marque ao menos um relatório." : `${escolha.conteudo} · ${nome}`}
          </p>
        </>
      )}
    </Modal>
  );
}

function RelatorioOrgaoModal({ orgao, relatorios, onFechar }: {
  orgao: number; relatorios: string[]; onFechar: () => void;
}) {
  const toast = useToast();
  const previa = useQuery({
    queryKey: ["relatorios", "por-orgao", orgao, relatorios],
    queryFn: () => relatoriosApi.previaOrgao(orgao, relatorios),
  });
  const exportar = useMutation({
    mutationFn: (formato: Formato) => relatoriosApi.exportarOrgao(orgao, relatorios, formato),
    onSuccess: () => toast("Relatório exportado."),
    onError: (e: Error) => toast(e.message, true),
  });
  const p = previa.data;

  return (
    <Modal aberto largo onFechar={onFechar}
      titulo={p ? `Relatório do órgão — ${p.orgao.nome}` : "Relatório do órgão"}
      subtitulo={p ? `${p.secoes.length} seção(ões) · prévia das ${LINHAS_NA_PREVIA} primeiras linhas de cada uma` : "Gerando prévia..."}
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
