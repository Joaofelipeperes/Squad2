import type { ReactNode } from "react";
import { createContext, useCallback, useContext, useState } from "react";

interface ToastItem { id: number; texto: string; erro?: boolean }
const Ctx = createContext<(texto: string, erro?: boolean) => void>(() => undefined);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [itens, setItens] = useState<ToastItem[]>([]);
  const toast = useCallback((texto: string, erro = false) => {
    const id = Date.now() + Math.random();
    setItens((l) => [...l, { id, texto, erro }]);
    setTimeout(() => setItens((l) => l.filter((t) => t.id !== id)), 3600);
  }, []);
  return (
    <Ctx.Provider value={toast}>
      {children}
      <div className="toast-wrap">
        {itens.map((t) => (
          <div key={t.id} className="toast">
            <i className={`fa-solid ${t.erro ? "fa-circle-exclamation" : "fa-circle-check"}`}
               style={t.erro ? { color: "var(--red-600)" } : undefined} />
            {t.texto}
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}

export const useToast = () => useContext(Ctx);
