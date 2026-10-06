import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useMemo } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "@/app/auth/AuthContext";
import { LoginPage } from "@/app/auth/LoginPage";
import { SemAcessoPage } from "@/app/auth/SemAcessoPage";
import { Shell } from "@/app/layout/Shell";
import { MODULOS, WIDGETS } from "@/modules/registry";
import { ToastProvider } from "@/shared/ui/Toast";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 30_000, refetchOnWindowFocus: false } },
});

function RotasProtegidas() {
  const { usuario, carregando, pode } = useAuth();
  // Filtro ÚNICO de telas: o que o usuário não pode acessar não entra no menu nem vira rota.
  const modulos = useMemo(() => MODULOS.filter((m) => pode(m.permissao)), [pode]);
  const widgets = useMemo(() => WIDGETS.filter((w) => pode(w.permissao)), [pode]);

  if (carregando) return null;
  if (!usuario) return <Navigate to="/login" replace />;
  if (!modulos.length) return <SemAcessoPage />;
  const inicial = modulos[0]!.caminho; // ex.: órgão publicador cai direto em /envio
  return (
    <Routes>
      <Route element={<Shell modulos={modulos} widgets={widgets} />}>
        {modulos.map((m) => <Route key={m.id} path={m.caminho} element={<m.pagina />} />)}
        <Route path="*" element={<Navigate to={inicial} replace />} />
      </Route>
    </Routes>
  );
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ToastProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/*" element={<RotasProtegidas />} />
            </Routes>
          </BrowserRouter>
        </ToastProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}
