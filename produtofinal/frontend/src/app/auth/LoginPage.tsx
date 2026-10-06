import type { FormEvent } from "react";
import { useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "@/app/auth/AuthContext";

export function LoginPage() {
  const { usuario, entrar } = useAuth();
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  if (usuario) return <Navigate to="/" replace />;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setErro(null);
    setEnviando(true);
    try {
      await entrar(email, senha);
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível entrar.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="login-wrap">
      <div className="login-card">
        <div className="brand">
          <div className="brand-mark"><i className="fa-solid fa-layer-group" /></div>
          <div className="brand-text">
            <h1>Dados Abertos Goiás</h1>
            <span>Monitoramento e Governança · GEDA/CGE-GO</span>
          </div>
        </div>
        <form onSubmit={onSubmit}>
          <div className="form-field">
            <label htmlFor="email">E-mail institucional</label>
            <input id="email" className="text-input" type="email" autoComplete="username"
                   value={email} onChange={(e) => setEmail(e.target.value)} required />
          </div>
          <div className="form-field">
            <label htmlFor="senha">Senha</label>
            <input id="senha" className="text-input" type="password" autoComplete="current-password"
                   value={senha} onChange={(e) => setSenha(e.target.value)} required />
          </div>
          {erro && <div className="inline-msg err">{erro}</div>}
          <button className="btn btn-primary" type="submit" disabled={enviando}
                  style={{ justifyContent: "center" }}>
            {enviando ? "Entrando…" : "Entrar"}
          </button>
        </form>
      </div>
    </div>
  );
}
