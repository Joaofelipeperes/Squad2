import type { ReactNode } from "react";
import { Modal } from "@/shared/ui/Modal";

interface Props {
  aberto: boolean;
  titulo: string;
  children: ReactNode;
  rotuloConfirmar: string;
  icone?: string;          // classe Font Awesome do botão de confirmação
  perigo?: boolean;        // ação destrutiva: botão vermelho (btn-danger-line)
  processando?: boolean;
  onConfirmar: () => void;
  onFechar: () => void;
}

/** Confirmação dentro da interface (o visualizador não usa window.confirm). */
export function ConfirmarModal({
  aberto, titulo, children, rotuloConfirmar, icone = "fa-check", perigo = false, processando = false,
  onConfirmar, onFechar,
}: Props) {
  const fechar = () => { if (!processando) onFechar(); };
  return (
    <Modal aberto={aberto} titulo={titulo} onFechar={fechar}
      rodape={<>
        <button type="button" className="btn btn-outline btn-sm" onClick={fechar} disabled={processando}>
          Cancelar
        </button>
        <button type="button" className={`btn btn-sm ${perigo ? "btn-danger-line" : "btn-primary"}`}
                onClick={onConfirmar} disabled={processando}>
          <i className={`fa-solid ${icone}`} />{processando ? "Processando…" : rotuloConfirmar}
        </button>
      </>}>
      <div className="confirmar-texto">{children}</div>
    </Modal>
  );
}
