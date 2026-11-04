import type { Achado, StatusAchado } from "./api";

/** Achados de um mesmo arquivo (recurso), para a tabela agrupada da tela LGPD. */
export interface GrupoRecurso {
  recurso_id: number;
  recurso_nome: string;
  dataset_titulo: string;
  orgao: string;
  orgao_nome: string | null;
  prioridade: Achado["prioridade"];          // a mais alta entre os achados
  celulas: number;                           // soma das ocorrências
  tipos: { rotulo: string; celulas: number }[];
  status: Partial<Record<StatusAchado, number>>;
  achados: Achado[];
}

const PESO: Record<string, number> = { Alta: 0, "Média": 1, Baixa: 2 };

/** Agrupa por recurso mantendo a ordem de prioridade: arquivo com achado Alta vem primeiro,
 *  depois o que tem mais células sinalizadas. Dentro do grupo, a ordem que veio da API. */
export function agruparPorRecurso(achados: Achado[]): GrupoRecurso[] {
  const grupos = new Map<number, GrupoRecurso>();
  for (const a of achados) {
    let g = grupos.get(a.recurso_id);
    if (!g) {
      g = {
        recurso_id: a.recurso_id, recurso_nome: a.recurso_nome ?? `Recurso ${a.recurso_id}`,
        dataset_titulo: a.dataset_titulo, orgao: a.orgao_sigla ?? a.orgao_nome ?? "—",
        orgao_nome: a.orgao_nome, prioridade: a.prioridade, celulas: 0, tipos: [], status: {},
        achados: [],
      };
      grupos.set(a.recurso_id, g);
    }
    g.achados.push(a);
    g.celulas += a.ocorrencias;
    if (PESO[a.prioridade] < PESO[g.prioridade]) g.prioridade = a.prioridade;
    g.status[a.status] = (g.status[a.status] ?? 0) + 1;
    const t = g.tipos.find((x) => x.rotulo === a.tipo_rotulo);
    if (t) t.celulas += a.ocorrencias;
    else g.tipos.push({ rotulo: a.tipo_rotulo, celulas: a.ocorrencias });
  }
  return [...grupos.values()].sort((x, y) =>
    PESO[x.prioridade] - PESO[y.prioridade] || y.celulas - x.celulas
    || x.recurso_nome.localeCompare(y.recurso_nome, "pt-BR"));
}
