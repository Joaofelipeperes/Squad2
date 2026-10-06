import type { ReactNode } from "react";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, tokenStore } from "@/shared/api/client";
import type { Permissao } from "@/shared/acesso/permissoes.gen";
import type { Sessao, Usuario } from "@/shared/types";

interface AuthState {
  usuario: Usuario | null;
  permissoes: ReadonlySet<Permissao>;
  /** Ponto único de checagem de permissão no frontend. */
  pode: (permissao: Permissao) => boolean;
  carregando: boolean;
  entrar: (email: string, senha: string) => Promise<void>;
  sair: () => void;
  recarregar: () => Promise<void>;
}

const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [sessao, setSessao] = useState<Sessao | null>(null);
  const [carregando, setCarregando] = useState(true);

  const recarregar = useCallback(async () => {
    if (!tokenStore.get()) return setSessao(null);
    try {
      setSessao(await api.get<Sessao>("/acesso/me"));
    } catch {
      tokenStore.clear();
      setSessao(null);
    }
  }, []);

  useEffect(() => { recarregar().finally(() => setCarregando(false)); }, [recarregar]);

  useEffect(() => {
    const expirou = () => setSessao(null);
    window.addEventListener("gda:sessao-expirada", expirou);
    return () => window.removeEventListener("gda:sessao-expirada", expirou);
  }, []);

  const entrar = useCallback(async (email: string, senha: string) => {
    const r = await api.post<{ access_token: string; sessao: Sessao }>("/acesso/login", { email, senha });
    tokenStore.set(r.access_token);
    setSessao(r.sessao);
  }, []);

  const sair = useCallback(() => { tokenStore.clear(); setSessao(null); }, []);

  const valor = useMemo<AuthState>(() => {
    const permissoes = new Set(sessao?.permissoes ?? []);
    return {
      usuario: sessao?.usuario ?? null, permissoes, pode: (p) => permissoes.has(p),
      carregando, entrar, sair, recarregar,
    };
  }, [sessao, carregando, entrar, sair, recarregar]);

  return <Ctx.Provider value={valor}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAuth fora do AuthProvider");
  return ctx;
}
