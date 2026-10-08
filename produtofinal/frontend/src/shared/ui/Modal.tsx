import type { ReactNode } from "react";
import { useEffect, useRef } from "react";

interface Props {
  aberto: boolean;
  titulo: string;
  subtitulo?: string;
  onFechar: () => void;
  children: ReactNode;
  rodape?: ReactNode;
}

const FOCAVEIS =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * Modal com a mesma marcação/classes do protótipo (.modal-overlay/.modal).
 * Acessibilidade de teclado: ao abrir, o foco vai para o primeiro campo do modal; Tab e Shift+Tab
 * ficam presos dentro dele; ao fechar, o foco volta ao elemento que o abriu.
 */
export function Modal({ aberto, titulo, subtitulo, onFechar, children, rodape }: Props) {
  const dialogo = useRef<HTMLDivElement>(null);
  const fechar = useRef(onFechar);
  fechar.current = onFechar;

  useEffect(() => {
    if (!aberto) return;
    const anterior = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const focaveis = () =>
      Array.from(dialogo.current?.querySelectorAll<HTMLElement>(FOCAVEIS) ?? [])
        .filter((el) => el.offsetParent !== null || el === document.activeElement);
    // Primeiro campo do corpo (o botão de fechar fica por último na preferência)
    const inicial = focaveis().find((el) => !el.classList.contains("modal-close")) ?? dialogo.current;
    inicial?.focus();

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        fechar.current();
        return;
      }
      if (e.key !== "Tab") return;
      const lista = focaveis();
      if (lista.length === 0) {
        e.preventDefault();
        dialogo.current?.focus();
        return;
      }
      const primeiro = lista[0];
      const ultimo = lista[lista.length - 1];
      const ativo = document.activeElement;
      const dentro = dialogo.current?.contains(ativo) ?? false;
      if (e.shiftKey && (ativo === primeiro || !dentro)) {
        e.preventDefault();
        ultimo.focus();
      } else if (!e.shiftKey && (ativo === ultimo || !dentro)) {
        e.preventDefault();
        primeiro.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      if (anterior && document.contains(anterior)) anterior.focus();
    };
  }, [aberto]);

  if (!aberto) return null;
  return (
    <div className="modal-overlay open" onMouseDown={(e) => e.target === e.currentTarget && onFechar()}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={titulo} ref={dialogo} tabIndex={-1}>
        <div className="modal-head">
          <div>
            <h3>{titulo}</h3>
            {subtitulo && <div className="sub">{subtitulo}</div>}
          </div>
          <button className="modal-close" onClick={onFechar} aria-label="Fechar">
            <i className="fa-solid fa-xmark" />
          </button>
        </div>
        <div className="modal-body">{children}</div>
        {rodape && <div className="modal-foot">{rodape}</div>}
      </div>
    </div>
  );
}
