import { useState } from "react";
import { Pode } from "@/shared/acesso/Pode";
import { api } from "@/shared/api/client";
import { useToast } from "@/shared/ui/Toast";

export type Celula = string | number | null;

/** Coluna do arquivo: título e como obter o valor de cada linha (já como a tela mostra). */
export interface ColunaExportacao<T> {
  titulo: string;
  valor: (linha: T) => Celula;
}

type Formato = "xlsx" | "pdf";

/** "Órgão: SES · Situação: Atrasado" com os filtros preenchidos; nenhum = null. */
export function descreverFiltros(pares: [string, string | null | undefined][]): string | null {
  const ativos = pares.filter(([, v]) => v != null && v.trim() !== "").map(([r, v]) => `${r}: ${v!.trim()}`);
  return ativos.length ? ativos.join(" · ") : null;
}

/** Rótulo da opção escolhida num filtro (o valor pode ser um id). */
export const rotuloDe = (opcoes: { valor: string; rotulo: string }[] | undefined, valor: string) =>
  valor ? (opcoes?.find((o) => o.valor === valor)?.rotulo ?? valor) : null;

function salvar(blob: Blob, nome: string) {
  const url = URL.createObjectURL(blob);
  const a = Object.assign(document.createElement("a"), { href: url, download: nome });
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/**
 * Botões "Excel" e "PDF" de uma tabela (ADR-0031): exportam as linhas que o usuário vê — com os
 * filtros e a ordenação da tela, todas as páginas —, com os filtros ativos no cabeçalho do PDF.
 * O arquivo é gerado no backend, com o mesmo gerador dos relatórios. Exige `relatorios.exportar`.
 */
export function ExportarTabela<T>({ titulo, filtros, colunas, linhas }: {
  titulo: string; filtros?: string | null; colunas: ColunaExportacao<T>[]; linhas: T[];
}) {
  const toast = useToast();
  const [gerando, setGerando] = useState<Formato | null>(null);

  async function exportar(formato: Formato) {
    setGerando(formato);
    try {
      const { blob, filename } = await api.downloadPost("/relatorios/tabela/exportar", {
        titulo, filtros: filtros ?? null, formato,
        colunas: colunas.map((c) => c.titulo),
        linhas: linhas.map((l) => colunas.map((c) => c.valor(l))),
      });
      salvar(blob, filename);
    } catch (e) {
      toast((e as Error).message, true);
    } finally {
      setGerando(null);
    }
  }

  const desabilitado = linhas.length === 0 || gerando != null;
  const dica = linhas.length === 0 ? "Nenhum registro para exportar" : `${linhas.length} registro(s), com os filtros e a ordem da tela`;
  return (
    <Pode permissao="relatorios.exportar">
      <button type="button" className="btn btn-outline btn-sm" disabled={desabilitado} title={dica}
        onClick={() => exportar("xlsx")}>
        <i className="fa-solid fa-file-excel" />{gerando === "xlsx" ? "Gerando…" : "Excel"}
      </button>
      <button type="button" className="btn btn-outline btn-sm" disabled={desabilitado} title={dica}
        onClick={() => exportar("pdf")}>
        <i className="fa-solid fa-file-pdf" />{gerando === "pdf" ? "Gerando…" : "PDF"}
      </button>
    </Pode>
  );
}
