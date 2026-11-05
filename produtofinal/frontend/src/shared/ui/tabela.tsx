/**
 * Kit de tabelas (ADR-0028): ordenação por coluna e paginação com total de registros.
 *
 * - `useTabela` ordena e pagina no navegador as listas que a API já devolve inteiras
 *   (Datasets, PDA, Atualizações, Organizações, LGPD, Usuários).
 * - Listas que crescem sem limite (Rastreabilidade, Log de acesso) paginam no servidor e usam só
 *   `<Paginacao>` e `<ColunaOrdenavel>`.
 *
 * Padrão: 50 itens por página; o usuário muda no rodapé, até 999.
 */
import type { CSSProperties, KeyboardEvent, ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";

export type Direcao = "asc" | "desc";
export interface Ordem<C extends string = string> { coluna: C; direcao: Direcao }
export type ValorOrdenavel = string | number | boolean | Date | null | undefined;
/** Como obter, de cada linha, o valor usado para ordenar cada coluna. */
export type Ordenadores<T, C extends string> = Record<C, (linha: T) => ValorOrdenavel>;

export const POR_PAGINA_PADRAO = 50;
export const POR_PAGINA_MAXIMO = 999;

const colador = new Intl.Collator("pt-BR", { sensitivity: "base", numeric: true });

const vazio = (v: ValorOrdenavel) => v == null || v === "" || (typeof v === "number" && Number.isNaN(v));

/** Compara dois valores não vazios: números e datas pelo valor, texto sem diferenciar acento nem
 *  maiúscula ("10" depois de "9"). */
export function compararValores(a: ValorOrdenavel, b: ValorOrdenavel): number {
  const x = a instanceof Date ? a.getTime() : a;
  const y = b instanceof Date ? b.getTime() : b;
  if (typeof x === "number" && typeof y === "number") return x - y;
  if (typeof x === "boolean" && typeof y === "boolean") return Number(x) - Number(y);
  return colador.compare(String(x), String(y));
}

/** Data ISO → número para ordenar (vazia = sem valor, vai para o fim). */
export const dataOrdenavel = (iso: string | null | undefined): number | null => {
  if (!iso) return null;
  const t = Date.parse(iso);
  return Number.isNaN(t) ? null : t;
};

/** Ordena sem alterar a lista. Valores vazios ficam sempre no fim; empate mantém a ordem da API. */
export function ordenar<T, C extends string>(linhas: T[], ordem: Ordem<C> | null,
                                             ordenadores: Ordenadores<T, C>): T[] {
  if (!ordem) return linhas;
  const valor = ordenadores[ordem.coluna];
  const sinal = ordem.direcao === "asc" ? 1 : -1;
  return linhas
    .map((l, i) => ({ l, i, v: valor(l) }))
    .sort((p, q) => {
      const vp = vazio(p.v), vq = vazio(q.v);
      if (vp || vq) return vp === vq ? p.i - q.i : vp ? 1 : -1;
      return sinal * compararValores(p.v, q.v) || p.i - q.i;
    })
    .map((x) => x.l);
}

/** Clique no cabeçalho: coluna nova começa em `primeira`; a mesma coluna inverte a direção. */
export function alternarOrdem<C extends string>(atual: Ordem<C> | null, coluna: C,
                                                primeira: Direcao = "asc"): Ordem<C> {
  if (atual?.coluna === coluna) return { coluna, direcao: atual.direcao === "asc" ? "desc" : "asc" };
  return { coluna, direcao: primeira };
}

export interface PaginacaoEstado {
  total: number;
  pagina: number;
  porPagina: number;
  onPagina: (pagina: number) => void;
  onPorPagina: (porPagina: number) => void;
}

/** Ordenação + paginação no navegador. `ordenadores` deve ser estável (constante do módulo). A
 *  página volta para 1 quando a lista muda (filtro), a ordem muda ou o tamanho da página muda. */
export function useTabela<T, C extends string>(linhas: T[] | undefined, ordenadores: Ordenadores<T, C>,
                                               ordemInicial: Ordem<NoInfer<C>> | null = null) {
  const [ordem, setOrdem] = useState<Ordem<C> | null>(ordemInicial);
  const [pagina, setPagina] = useState(1);
  const [porPagina, setPorPagina] = useState(POR_PAGINA_PADRAO);

  useEffect(() => { setPagina(1); }, [linhas]);

  const ordenadas = useMemo(() => ordenar(linhas ?? [], ordem, ordenadores), [linhas, ordem, ordenadores]);
  const total = ordenadas.length;
  const paginas = Math.max(1, Math.ceil(total / porPagina));
  const atual = Math.min(pagina, paginas);
  const itens = useMemo(() => ordenadas.slice((atual - 1) * porPagina, atual * porPagina),
    [ordenadas, atual, porPagina]);

  const ordenarPor = (coluna: C, primeira: Direcao = "asc") => {
    setOrdem((o) => alternarOrdem(o, coluna, primeira));
    setPagina(1);
  };
  const paginacao: PaginacaoEstado = {
    total, pagina: atual, porPagina, onPagina: setPagina,
    onPorPagina: (n) => { setPorPagina(n); setPagina(1); },
  };
  return { itens, total, ordem, ordenarPor, paginacao };
}

/** Cabeçalho clicável. `primeira` = direção do primeiro clique (datas e números: "desc"). */
export function ColunaOrdenavel<C extends string>({ coluna, ordem, onOrdenar, primeira = "asc", title, style,
                                                    children }: {
  coluna: C; ordem: Ordem<C> | null; onOrdenar: (coluna: C, primeira: Direcao) => void;
  primeira?: Direcao; title?: string; style?: CSSProperties; children: ReactNode;
}) {
  const ativa = ordem?.coluna === coluna;
  const asc = ativa && ordem!.direcao === "asc";
  const icone = !ativa ? "fa-sort" : asc ? "fa-sort-up" : "fa-sort-down";
  return (
    <th aria-sort={ativa ? (asc ? "ascending" : "descending") : "none"} title={title} style={style}>
      <button type="button" className={`th-ordenar${ativa ? " ativa" : ""}`}
              onClick={() => onOrdenar(coluna, primeira)}>
        {children}
        <i className={`fa-solid ${icone}`} aria-hidden="true" />
      </button>
    </th>
  );
}

const fmtNumero = new Intl.NumberFormat("pt-BR");

/**
 * Rodapé da tabela: total de registros, faixa exibida, itens por página (1 a 999) e navegação.
 * `resumo` substitui o texto padrão "N registro(s)" (ex.: "12 dataset(s) de 446 no inventário").
 */
export function Paginacao({ total, pagina, porPagina, onPagina, onPorPagina, resumo, carregando, id }:
  PaginacaoEstado & { resumo?: ReactNode; carregando?: boolean; id?: string }) {
  const paginas = Math.max(1, Math.ceil(total / porPagina));
  const inicio = total === 0 ? 0 : (pagina - 1) * porPagina + 1;
  const fim = Math.min(total, pagina * porPagina);
  const [texto, setTexto] = useState(String(porPagina));
  useEffect(() => { setTexto(String(porPagina)); }, [porPagina]);
  const campo = `${id ?? "paginacao"}-por-pagina`;

  const aplicar = () => {
    const n = Math.trunc(Number(texto));
    if (!Number.isFinite(n) || n < 1) { setTexto(String(porPagina)); return; }
    const valido = Math.min(POR_PAGINA_MAXIMO, n);
    setTexto(String(valido));
    if (valido !== porPagina) onPorPagina(valido);
  };
  const teclado = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") { e.preventDefault(); aplicar(); }
  };

  return (
    <div className="paginacao">
      <div className="paginacao-total" aria-live="polite">
        {resumo ?? <><strong>{fmtNumero.format(total)}</strong> registro(s)</>}
        {total > 0 && <> · exibindo {fmtNumero.format(inicio)}–{fmtNumero.format(fim)}</>}
        {carregando && " · atualizando…"}
      </div>
      <div className="paginacao-controles">
        <label htmlFor={campo}>Itens por página</label>
        <input id={campo} type="number" className="text-input" min={1} max={POR_PAGINA_MAXIMO} step={1}
               value={texto} onChange={(e) => setTexto(e.target.value)} onBlur={aplicar} onKeyDown={teclado}
               title={`De 1 a ${POR_PAGINA_MAXIMO}`} />
        <div className="paginacao-nav" role="group" aria-label="Páginas">
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => onPagina(1)}
                  disabled={pagina <= 1} aria-label="Primeira página" title="Primeira página">
            <i className="fa-solid fa-angles-left" />
          </button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => onPagina(pagina - 1)}
                  disabled={pagina <= 1} aria-label="Página anterior" title="Página anterior">
            <i className="fa-solid fa-angle-left" />
          </button>
          <span className="paginacao-pagina">Página {fmtNumero.format(pagina)} de {fmtNumero.format(paginas)}</span>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => onPagina(pagina + 1)}
                  disabled={pagina >= paginas} aria-label="Próxima página" title="Próxima página">
            <i className="fa-solid fa-angle-right" />
          </button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => onPagina(paginas)}
                  disabled={pagina >= paginas} aria-label="Última página" title="Última página">
            <i className="fa-solid fa-angles-right" />
          </button>
        </div>
      </div>
    </div>
  );
}
