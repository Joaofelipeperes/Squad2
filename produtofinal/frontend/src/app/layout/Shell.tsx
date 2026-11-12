import { Suspense, useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { Sidebar } from "@/app/layout/Sidebar";
import { Topbar } from "@/app/layout/Topbar";
import type { AppModule, AppWidget } from "@/modules/types";

export function Shell({ modulos, widgets }: { modulos: AppModule[]; widgets: AppWidget[] }) {
  const { pathname } = useLocation();
  const atual = modulos.find((m) => m.caminho === pathname)
    ?? modulos.find((m) => m.caminho !== "/" && pathname.startsWith(m.caminho));
  // Em telas estreitas (≤ 768px) o menu lateral vira gaveta; fecha ao trocar de tela e com Esc.
  const [menuAberto, setMenuAberto] = useState(false);
  useEffect(() => { setMenuAberto(false); }, [pathname]);
  useEffect(() => {
    if (!menuAberto) return;
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setMenuAberto(false); };
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [menuAberto]);

  return (
    <div className="app">
      <Sidebar modulos={modulos} aberta={menuAberto} />
      {menuAberto && <div className="sidebar-fundo" aria-hidden="true" onClick={() => setMenuAberto(false)} />}
      <div className="main">
        <Topbar crumb={atual?.crumb ?? "GEDA · CGE-GO"} titulo={atual?.titulo ?? ""}
          menuAberto={menuAberto} onMenu={() => setMenuAberto((v) => !v)} />
        <main className="content">
          <Suspense fallback={<div className="empty-state"><p>Carregando…</p></div>}>
            <Outlet />
          </Suspense>
        </main>
      </div>
      <Suspense fallback={null}>
        {widgets.map((w) => <w.componente key={w.id} />)}
      </Suspense>
    </div>
  );
}
