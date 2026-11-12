import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { Papel } from "./api";
import { acessoApi } from "./api";
import { PapelForm } from "./PapelForm";
import { UsuarioForm } from "./UsuarioForm";
import { useAuth } from "@/app/auth/AuthContext";
import { Pode } from "@/shared/acesso/Pode";
import type { Usuario } from "@/shared/types";
import { PageLede } from "@/shared/ui/PageLede";
import { useToast } from "@/shared/ui/Toast";
import type { Ordenadores } from "@/shared/ui/tabela";
import { ColunaOrdenavel, Paginacao, dataOrdenavel, useTabela } from "@/shared/ui/tabela";

const ORDENADORES_USUARIO: Ordenadores<Usuario, "nome" | "email" | "papeis" | "orgao" | "acesso" | "status"> = {
  nome: (u) => u.nome,
  email: (u) => u.email,
  papeis: (u) => u.papeis.map((p) => p.nome).join(", "),
  orgao: (u) => u.orgao?.titulo ?? "Todos",
  acesso: (u) => dataOrdenavel(u.ultimo_acesso),
  status: (u) => (u.ativo ? "Ativo" : "Inativo"),
};

const ORDENADORES_PAPEL: Ordenadores<Papel, "nome" | "permissoes" | "usuarios" | "escopo"> = {
  nome: (p) => p.nome,
  permissoes: (p) => (p.todas ? Number.MAX_SAFE_INTEGER : p.permissoes.length),
  usuarios: (p) => p.total_usuarios,
  escopo: (p) => (p.exige_orgao ? "Próprio órgão" : "Estadual"),
};

const fmt = (iso: string | null) =>
  iso ? new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }) : "Nunca";

export default function UsuariosPage() {
  const { pode, recarregar } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const usuarios = useQuery({ queryKey: ["acesso", "usuarios"], queryFn: acessoApi.usuarios });
  const papeis = useQuery({ queryKey: ["acesso", "papeis"], queryFn: acessoApi.papeis });
  const catalogo = useQuery({ queryKey: ["acesso", "catalogo"], queryFn: acessoApi.catalogo });
  const [formUsuario, setFormUsuario] = useState<{ aberto: boolean; u: Usuario | null }>({ aberto: false, u: null });
  const [formPapel, setFormPapel] = useState<{ aberto: boolean; p: Papel | null }>({ aberto: false, p: null });
  const tabUsuarios = useTabela(usuarios.data, ORDENADORES_USUARIO);
  const tabPapeis = useTabela(papeis.data, ORDENADORES_PAPEL);
  const colU = { ordem: tabUsuarios.ordem, onOrdenar: tabUsuarios.ordenarPor };
  const colP = { ordem: tabPapeis.ordem, onOrdenar: tabPapeis.ordenarPor };

  const atualizar = () => {
    qc.invalidateQueries({ queryKey: ["acesso"] });
    recarregar(); // se o usuário alterou o próprio papel, menu e botões mudam na hora
  };
  const excluirPapel = useMutation({
    mutationFn: (p: Papel) => acessoApi.excluirPapel(p.id),
    onSuccess: () => { toast("Papel excluído."); atualizar(); },
    onError: (e: Error) => toast(e.message, true),
  });

  return (
    <section className="screen">
      <PageLede titulo="Usuários e papéis">
        Cada usuário recebe um ou mais papéis; cada papel define quais telas o usuário vê e quais
        ações pode executar. Usuários vinculados a um órgão só enxergam dados daquele órgão.
      </PageLede>

      <div className="panel">
        <div className="panel-head">
          <div><h3>Usuários</h3></div>
          <button className="btn btn-primary btn-sm" onClick={() => setFormUsuario({ aberto: true, u: null })}>
            <i className="fa-solid fa-user-plus" />Novo usuário
          </button>
        </div>
        <div className="table-scroll">
          <table>
            <thead><tr>
              <ColunaOrdenavel coluna="nome" {...colU}>Nome</ColunaOrdenavel>
              <ColunaOrdenavel coluna="email" {...colU}>E-mail</ColunaOrdenavel>
              <ColunaOrdenavel coluna="papeis" {...colU}>Papéis</ColunaOrdenavel>
              <ColunaOrdenavel coluna="orgao" {...colU}>Órgão</ColunaOrdenavel>
              <ColunaOrdenavel coluna="acesso" primeira="desc" {...colU}>Último acesso</ColunaOrdenavel>
              <ColunaOrdenavel coluna="status" {...colU}>Status</ColunaOrdenavel>
              <th />
            </tr></thead>
            <tbody>
              {tabUsuarios.itens.map((u) => (
                <tr key={u.id}>
                  <td className="cell-strong">{u.nome}</td>
                  <td>{u.email}</td>
                  <td>{u.papeis.map((p) => <span key={p.id} className="badge badge-blue" style={{ marginRight: 4 }}>{p.nome}</span>)}</td>
                  <td>{u.orgao?.titulo ?? <span className="cell-muted">Todos</span>}</td>
                  <td>{fmt(u.ultimo_acesso)}</td>
                  <td>{u.ativo ? <span className="badge badge-green">Ativo</span> : <span className="badge badge-gray">Inativo</span>}</td>
                  <td><div className="row-actions">
                    <button className="btn btn-ghost btn-sm" onClick={() => setFormUsuario({ aberto: true, u })}>
                      <i className="fa-solid fa-pen" />Editar
                    </button>
                  </div></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {usuarios.data && (
          <Paginacao id="usuarios" {...tabUsuarios.paginacao}
            resumo={<><strong>{usuarios.data.length}</strong> usuário(s) cadastrado(s)</>} />
        )}
      </div>

      <div className="panel">
        <div className="panel-head">
          <div><h3>Papéis</h3><div className="sub">Papéis do sistema podem ter permissões ajustadas, mas não podem ser excluídos</div></div>
          <Pode permissao="acesso.gerenciar_papeis">
            <button className="btn btn-primary btn-sm" onClick={() => setFormPapel({ aberto: true, p: null })}>
              <i className="fa-solid fa-plus" />Novo papel
            </button>
          </Pode>
        </div>
        <div className="table-scroll">
          <table>
            <thead><tr>
              <ColunaOrdenavel coluna="nome" {...colP}>Papel</ColunaOrdenavel>
              <ColunaOrdenavel coluna="permissoes" primeira="desc" {...colP}>Permissões</ColunaOrdenavel>
              <ColunaOrdenavel coluna="usuarios" primeira="desc" {...colP}>Usuários</ColunaOrdenavel>
              <ColunaOrdenavel coluna="escopo" {...colP}>Escopo</ColunaOrdenavel>
              <th />
            </tr></thead>
            <tbody>
              {tabPapeis.itens.map((p) => (
                <tr key={p.id}>
                  <td style={{ maxWidth: 360 }}>
                    <div className="cell-strong">{p.nome} {p.sistema && <span className="badge badge-gray">sistema</span>}</div>
                    <div className="cell-muted" style={{ fontSize: 12 }}>{p.descricao}</div>
                  </td>
                  <td>{p.todas ? "Todas" : p.permissoes.length}</td>
                  <td>{p.total_usuarios}</td>
                  <td>{p.exige_orgao ? <span className="badge badge-amber">Próprio órgão</span> : "Estadual"}</td>
                  <td><div className="row-actions">
                    <button className="btn btn-ghost btn-sm" onClick={() => setFormPapel({ aberto: true, p })}>
                      <i className={`fa-solid ${pode("acesso.gerenciar_papeis") && !p.todas ? "fa-pen" : "fa-eye"}`} />
                      {pode("acesso.gerenciar_papeis") && !p.todas ? "Editar" : "Ver"}
                    </button>
                    <Pode permissao="acesso.gerenciar_papeis">
                      {!p.sistema && (
                        <button className="btn btn-danger-line btn-sm"
                          onClick={() => confirm(`Excluir o papel “${p.nome}”?`) && excluirPapel.mutate(p)}>
                          <i className="fa-solid fa-trash" />
                        </button>)}
                    </Pode>
                  </div></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {papeis.data && (
          <Paginacao id="papeis" {...tabPapeis.paginacao}
            resumo={<><strong>{papeis.data.length}</strong> papel(éis)</>} />
        )}
      </div>

      <UsuarioForm aberto={formUsuario.aberto} usuario={formUsuario.u} papeis={papeis.data ?? []}
        onFechar={() => setFormUsuario({ aberto: false, u: null })} onSalvo={atualizar} />
      {catalogo.data && (
        <PapelForm aberto={formPapel.aberto} catalogo={catalogo.data}
          papel={formPapel.p} somenteLeitura={!pode("acesso.gerenciar_papeis")}
          onFechar={() => setFormPapel({ aberto: false, p: null })} onSalvo={atualizar} />
      )}
    </section>
  );
}
