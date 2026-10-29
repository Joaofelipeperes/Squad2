import { keepPreviousData, useQuery } from "@tanstack/react-query";
import type { KeyboardEvent } from "react";
import { useEffect, useState } from "react";
import type { DatasetOpcao } from "./api";
import { pdaApi } from "./api";

interface Props {
  /** id do campo de busca (para o <label htmlFor>). */
  id: string;
  /** Dataset vinculado; null = sem vínculo (mostra a busca). */
  valor: DatasetOpcao | null;
  onEscolher: (d: DatasetOpcao | null) => void;
}

const MINIMO = 2;

/**
 * Busca de datasets do inventário para vincular a uma base do PDA (combobox WAI-ARIA com lista de
 * sugestões). Aceita título, name, ID ou o link do portal; o vínculo gravado é sempre o ID.
 */
export function DatasetBusca({ id, valor, onEscolher }: Props) {
  const [texto, setTexto] = useState("");
  const [termo, setTermo] = useState("");
  const [aberto, setAberto] = useState(false);
  const [ativo, setAtivo] = useState(-1);
  const listaId = `${id}-lista`;

  useEffect(() => {
    const t = setTimeout(() => setTermo(texto.trim()), 300);
    return () => clearTimeout(t);
  }, [texto]);

  const busca = useQuery({
    queryKey: ["pda", "formulario", "datasets", termo],
    queryFn: () => pdaApi.buscarDatasets(termo),
    enabled: valor == null && termo.length >= MINIMO,
    placeholderData: keepPreviousData,
    staleTime: 60_000,
  });
  const opcoes = termo.length >= MINIMO ? busca.data ?? [] : [];

  useEffect(() => setAtivo(-1), [termo]);

  function escolher(d: DatasetOpcao) {
    onEscolher(d);
    setTexto("");
    setTermo("");
    setAberto(false);
  }

  function teclado(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      setAberto(true);
      if (!opcoes.length) return;
      const passo = e.key === "ArrowDown" ? 1 : -1;
      setAtivo((i) => (i + passo + opcoes.length) % opcoes.length);
    } else if (e.key === "Enter") {
      e.preventDefault(); // Enter na busca nunca envia o formulário
      if (aberto && ativo >= 0 && opcoes[ativo]) escolher(opcoes[ativo]);
    } else if (e.key === "Escape" && aberto) {
      e.stopPropagation(); // fecha só a lista, não o modal
      setAberto(false);
    }
  }

  if (valor) {
    return (
      <div className="dataset-escolhido">
        <div>
          <strong>{valor.titulo}</strong>
          {!valor.ativo_no_portal && <>{" "}<span className="badge badge-red">Fora do portal</span></>}
          <div className="cell-muted mono">{valor.name}</div>
          <div className="cell-muted">{valor.orgao_nome ?? "Sem organização no portal"}</div>
        </div>
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => onEscolher(null)}
                aria-label={`Remover vínculo com ${valor.titulo}`}>
          <i className="fa-solid fa-link-slash" />Remover
        </button>
      </div>
    );
  }

  const mostrarLista = aberto && termo.length >= MINIMO;
  const status = texto.trim().length < MINIMO ? ""
    : busca.isError ? `Não foi possível buscar: ${busca.error.message}`
    : busca.isFetching && !busca.data ? "Buscando…"
    : busca.data && !opcoes.length ? "Nenhum dataset encontrado no inventário."
    : "";

  return (
    <>
      <input id={id} className="text-input" type="search" autoComplete="off" value={texto} maxLength={500}
             placeholder="Busque pelo título, name ou link do dataset"
             role="combobox" aria-autocomplete="list" aria-controls={listaId}
             aria-expanded={mostrarLista && opcoes.length > 0}
             aria-activedescendant={mostrarLista && ativo >= 0 ? `${listaId}-${ativo}` : undefined}
             onChange={(e) => { setTexto(e.target.value); setAberto(true); }}
             onFocus={() => setAberto(true)} onBlur={() => setAberto(false)} onKeyDown={teclado} />
      <ul id={listaId} role="listbox" className="busca-lista" aria-label="Datasets encontrados"
          hidden={!mostrarLista || !opcoes.length}>
        {opcoes.map((d, i) => (
          <li key={d.id} id={`${listaId}-${i}`} role="option" aria-selected={i === ativo}
              onMouseDown={(e) => e.preventDefault()} onClick={() => escolher(d)}>
            <span>
              {d.titulo}
              {!d.ativo_no_portal && <>{" "}<span className="badge badge-red">Fora do portal</span></>}
            </span>
            <span className="meta"><span className="mono">{d.name}</span> · {d.orgao_nome ?? "sem organização"}</span>
          </li>
        ))}
      </ul>
      <span className="help" role="status">{status}</span>
    </>
  );
}
