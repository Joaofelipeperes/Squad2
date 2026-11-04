import type { ReactNode } from "react";
import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";

interface Props {
  aberto: boolean;
  titulo: string;
  subtitulo?: string;
  onFechar: () => void;
  children: ReactNode;
  rodape?: ReactNode;
  largo?: boolean; // janelas com tabelas ou muitas colunas (ex.: prévia da anonimização, importação do PDA)
}

const FOCAVEIS =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/** Modais abertos, do mais antigo ao mais recente: só o do topo responde ao teclado. */
const pilha: object[] = [];

/**
 * Modal com a mesma marcação/classes do protótipo (.modal-overlay/.modal).
 * Renderizado no fim do <body> (portal): o modal aberto por último fica sempre por cima, mesmo
 * quando é aberto de dentro de outro (ex.: Editar no detalhe da base).
 * Acessibilidade de teclado: ao abrir, o foco vai para o primeiro campo do modal; Tab e Shift+Tab
 * ficam presos dentro dele; Esc fecha só o do topo; ao fechar, o foco volta ao elemento que o abriu.
 */
export function Modal({ aberto, titulo, subtitulo, onFechar, children, rodape, largo }: Props) {
  const dialogo = useRef<HTMLDivElement>(null);
  const fechar = useRef(onFechar);
  fechar.current = onFechar;

  useEffect(() => {
    if (!aberto) return;
    const eu = {};
    pilha.push(eu);
    const anterior = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const focaveis = () =>
      Array.from(dialogo.current?.querySelectorAll<HTMLElement>(FOCAVEIS) ?? [])
        .filter((el) => el.offsetParent !== null || el === document.activeElement);
    // Primeiro campo do corpo (o botão de fechar fica por último na preferência)
    const inicial = focaveis().find((el) => !el.classList.contains("modal-close")) ?? dialogo.current;
    inicial?.focus();

    const onKey = (e: KeyboardEvent) => {
      if (pilha[pilha.length - 1] !== eu) return;
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
      pilha.splice(pilha.indexOf(eu), 1);
      if (anterior && document.contains(anterior)) anterior.focus();
    };
  }, [aberto]);

  if (!aberto) return null;
  return createPortal(
    <div className="modal-overlay open" onMouseDown={(e) => e.target === e.currentTarget && onFechar()}>
      <div className={largo ? "modal modal-largo" : "modal"} role="dialog" aria-modal="true" aria-label={titulo} ref={dialogo} tabIndex={-1}>
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
    </div>,
    document.body,
  );
}
