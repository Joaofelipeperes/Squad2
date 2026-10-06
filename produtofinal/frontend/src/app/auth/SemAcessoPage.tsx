import { useAuth } from "@/app/auth/AuthContext";

export function SemAcessoPage() {
  const { usuario, sair } = useAuth();
  return (
    <div className="login-wrap">
      <div className="login-card">
        <h3 style={{ marginBottom: 8 }}>Nenhuma tela liberada</h3>
        <p style={{ fontSize: 13.5, color: "var(--gray-700)", lineHeight: 1.5, marginBottom: 18 }}>
          {usuario?.nome}, seu usuário está ativo, mas nenhum papel com acesso a telas foi
          atribuído. Peça à Gerência de Dados Abertos para revisar seus papéis.
        </p>
        <button className="btn btn-outline btn-sm" onClick={sair}>Sair</button>
      </div>
    </div>
  );
}
