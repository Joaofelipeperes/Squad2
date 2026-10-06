import { Suspense } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { Sidebar } from "@/app/layout/Sidebar";
import { Topbar } from "@/app/layout/Topbar";
import type { AppModule, AppWidget } from "@/modules/types";

export function Shell({ modulos, widgets }: { modulos: AppModule[]; widgets: AppWidget[] }) {
  const { pathname } = useLocation();
  const atual = modulos.find((m) => m.caminho === pathname)
    ?? modulos.find((m) => m.caminho !== "/" && pathname.startsWith(m.caminho));
  return (
    <div className="app">
      <Sidebar modulos={modulos} />
      <div className="main">
        <Topbar crumb={atual?.crumb ?? "GEDA · CGE-GO"} titulo={atual?.titulo ?? ""} />
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
