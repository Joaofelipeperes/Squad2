import { useState } from "react";
import { NavLink } from "react-router-dom";
import { useAuth } from "@/app/auth/AuthContext";
import { TrocarSenhaModal } from "@/app/layout/TrocarSenhaModal";
import type { AppModule } from "@/modules/types";
import { SECOES } from "@/modules/types";

function iniciais(nome: string) {
  return nome.split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0]!.toUpperCase()).join("");
}

export function Sidebar({ modulos, aberta = false }: { modulos: AppModule[]; aberta?: boolean }) {
  const { usuario, sair } = useAuth();
  const [trocandoSenha, setTrocandoSenha] = useState(false);
  return (
    <aside className={`sidebar${aberta ? " aberta" : ""}`} id="menu-lateral" aria-label="Menu principal">
      <div className="brand">
        <div className="brand-mark"><i className="fa-solid fa-layer-group" aria-hidden="true" /></div>
        <div className="brand-text">
          {/* O h1 da página é o título na barra superior; a marca não é título. */}
          <p className="brand-nome">Dados Abertos Goiás</p>
          <span>Monitoramento e Governança</span>
        </div>
      </div>

      <nav className="nav">
        {SECOES.map((secao) => {
          const itens = modulos.filter((m) => m.secao === secao);
          if (!itens.length) return null;
          return (
            <div key={secao}>
              <div className="nav-group-label">{secao}</div>
              {itens.map((m) => (
                <NavLink key={m.id} to={m.caminho} end={m.caminho === "/"}
                  className={({ isActive }) =>
                    `nav-item${m.destaqueAlerta ? " alert" : ""}${isActive ? " active" : ""}`}>
                  <i className={`fa-solid ${m.icone}`} />
                  {m.rotulo}
                </NavLink>
              ))}
            </div>
          );
        })}
      </nav>

      <div className="sidebar-footer">
        <div className="org-line"><i className="fa-solid fa-landmark" /> {usuario?.orgao ? usuario.orgao.titulo : "CGE-GO"}</div>
        {!usuario?.orgao && (
          <div className="org-line" style={{ fontWeight: 500, color: "#8fa5b8" }}>
            <i className="fa-solid fa-diagram-project" /> GEDA
          </div>
        )}
        {usuario && (
          <div className="user-line">
            <div className="user-avatar">{iniciais(usuario.nome)}</div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontWeight: 600, color: "#e6eef5" }}>{usuario.nome}</div>
              <div>{usuario.papeis.map((p) => p.nome).join(", ") || "Sem papel"}</div>
            </div>
            <button className="btn btn-ghost btn-sm" onClick={() => setTrocandoSenha(true)}
                    aria-label="Trocar senha" title="Trocar senha" style={{ color: "#c4d5e3" }}>
              <i className="fa-solid fa-key" />
            </button>
            <button className="btn btn-ghost btn-sm" onClick={sair} aria-label="Sair" title="Sair"
                    style={{ color: "#c4d5e3" }}>
              <i className="fa-solid fa-right-from-bracket" />
            </button>
          </div>
        )}
      </div>
      <TrocarSenhaModal aberto={trocandoSenha} onFechar={() => setTrocandoSenha(false)} />
    </aside>
  );
}
