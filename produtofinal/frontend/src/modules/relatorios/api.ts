/** Contrato JSON da tela Relatórios (/api/v1/relatorios). */
import { api, ApiError, tokenStore } from "@/shared/api/client";

export interface Relatorio {
  id: string;
  titulo: string;
  descricao: string;
  icone: string; // classe Font Awesome
}

export interface Previa {
  id: string;
  titulo: string;
  referencia: string | null; // ex.: nome do PDA vigente
  hoje: string;
  colunas: string[];
  linhas: string[][]; // primeiras linhas, já formatadas
  total: number; // linhas do relatório completo
}

export type Formato = "xlsx" | "csv" | "pdf";

/** Órgão que pode ser escolhido no relatório de um órgão. */
export interface OrgaoOpcao { id: number; nome: string }

/** Prévia do relatório detalhado de um órgão: o resumo e a lista do que cada número conta. */
export interface RelatorioOrgao {
  orgao: OrgaoOpcao;
  hoje: string;
  secoes: Previa[];
}

/** Baixa um arquivo de relatório (a exportação leva todas as linhas, não só as da prévia). */
async function baixar(caminho: string, nomePadrao: string) {
  const token = tokenStore.get();
  const resp = await fetch(`/api/v1/relatorios/${caminho}`,
    { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!resp.ok) {
    let msg = `Erro ${resp.status} ao exportar o relatório`;
    try {
      const data = await resp.json();
      if (typeof data.detail === "string") msg = data.detail;
    } catch {
      /* resposta sem JSON */
    }
    throw new ApiError(resp.status, msg);
  }
  const nome = /filename="([^"]+)"/.exec(resp.headers.get("Content-Disposition") ?? "")?.[1]
    ?? nomePadrao;
  const url = URL.createObjectURL(await resp.blob());
  const a = Object.assign(document.createElement("a"), { href: url, download: nome });
  a.click();
  URL.revokeObjectURL(url);
}

export const relatoriosApi = {
  lista: () => api.get<Relatorio[]>("/relatorios"),
  previa: (id: string) => api.get<Previa>(`/relatorios/${id}/previa`),
  exportar: (id: string, formato: Formato) =>
    baixar(`${id}/exportar?formato=${formato}`, `relatorio-${id}.${formato}`),
  // Relatório detalhado de um órgão
  orgaos: () => api.get<OrgaoOpcao[]>("/relatorios/por-orgao/orgaos"),
  previaOrgao: (orgao: number) => api.get<RelatorioOrgao>(`/relatorios/por-orgao/${orgao}/previa`),
  exportarOrgao: (orgao: number, formato: Formato) =>
    baixar(`por-orgao/${orgao}/exportar?formato=${formato}`, `relatorio-orgao-${orgao}.${formato}`),
};
