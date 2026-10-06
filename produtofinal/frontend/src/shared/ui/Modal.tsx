import type { ReactNode } from "react";
import { useEffect } from "react";

interface Props {
  aberto: boolean;
  titulo: string;
  subtitulo?: string;
  onFechar: () => void;
  children: ReactNode;
  rodape?: ReactNode;
}

/** Modal com a mesma marcação/classes do protótipo (.modal-overlay/.modal). */
export function Modal({ aberto, titulo, subtitulo, onFechar, children, rodape }: Props) {
  useEffect(() => {
    if (!aberto) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onFechar();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [aberto, onFechar]);

  if (!aberto) return null;
  return (
    <div className="modal-overlay open" onMouseDown={(e) => e.target === e.currentTarget && onFechar()}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={titulo}>
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
