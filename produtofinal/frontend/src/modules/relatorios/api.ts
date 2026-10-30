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

export type Formato = "xlsx" | "csv";

/** Baixa o arquivo do relatório (a exportação leva todas as linhas, não só as da prévia). */
async function exportar(id: string, formato: Formato) {
  const token = tokenStore.get();
  const resp = await fetch(`/api/v1/relatorios/${id}/exportar?formato=${formato}`,
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
    ?? `relatorio-${id}.${formato}`;
  const url = URL.createObjectURL(await resp.blob());
  const a = Object.assign(document.createElement("a"), { href: url, download: nome });
  a.click();
  URL.revokeObjectURL(url);
}

export const relatoriosApi = {
  lista: () => api.get<Relatorio[]>("/relatorios"),
  previa: (id: string) => api.get<Previa>(`/relatorios/${id}/previa`),
  exportar,
};
