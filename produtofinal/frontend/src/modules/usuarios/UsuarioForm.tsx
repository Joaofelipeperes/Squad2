import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import type { Papel, UsuarioIn } from "./api";
import { acessoApi } from "./api";
import type { Usuario } from "@/shared/types";
import { Modal } from "@/shared/ui/Modal";

interface Props {
  aberto: boolean; usuario: Usuario | null; papeis: Papel[];
  onFechar: () => void; onSalvo: () => void;
}

export function UsuarioForm({ aberto, usuario, papeis, onFechar, onSalvo }: Props) {
  const orgaos = useQuery({ queryKey: ["acesso", "orgaos"], queryFn: acessoApi.orgaos, enabled: aberto });
  const [f, setF] = useState<UsuarioIn>({ email: "", nome: "", ativo: true, orgao_id: null, papel_ids: [] });
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    if (!aberto) return;
    setF(usuario
      ? { email: usuario.email, nome: usuario.nome, ativo: usuario.ativo,
          orgao_id: usuario.orgao?.ckan_id ?? null, papel_ids: usuario.papeis.map((p) => p.id) }
      : { email: "", nome: "", ativo: true, orgao_id: null, papel_ids: [] });
    setSenha("");
    setErro(null);
  }, [aberto, usuario]);

  const exigeOrgao = papeis.some((p) => p.exige_orgao && f.papel_ids.includes(p.id));
  const alternar = (id: number) => setF((s) => ({
    ...s, papel_ids: s.papel_ids.includes(id) ? s.papel_ids.filter((x) => x !== id) : [...s.papel_ids, id],
  }));

  const salvar = useMutation({
    mutationFn: () => {
      const body = { ...f, senha: senha || null };
      return usuario ? acessoApi.atualizarUsuario(usuario.id, body) : acessoApi.criarUsuario(body);
    },
    onSuccess: () => { onSalvo(); onFechar(); },
    onError: (e: Error) => setErro(e.message),
  });

  return (
    <Modal aberto={aberto} onFechar={onFechar}
      titulo={usuario ? `Editar ${usuario.nome}` : "Novo usuário"}
      subtitulo="As telas e ações liberadas vêm dos papéis atribuídos."
      rodape={<button className="btn btn-primary btn-sm" onClick={() => salvar.mutate()} disabled={salvar.isPending}>
        <i className="fa-solid fa-floppy-disk" />Salvar usuário
      </button>}>
      <div className="form-grid">
        <div className="form-field">
          <label htmlFor="us-nome">Nome</label>
          <input id="us-nome" className="text-input" value={f.nome} onChange={(e) => setF({ ...f, nome: e.target.value })} />
        </div>
        <div className="form-field">
          <label htmlFor="us-email">E-mail</label>
          <input id="us-email" className="text-input" type="email" value={f.email}
                 onChange={(e) => setF({ ...f, email: e.target.value })} />
        </div>
        <div className="form-field">
          <label htmlFor="us-senha">{usuario ? "Nova senha" : "Senha inicial"}</label>
          <input id="us-senha" className="text-input" type="password" autoComplete="new-password" value={senha}
                 placeholder={usuario ? "Deixe vazio para manter" : "Mínimo 8 caracteres"}
                 onChange={(e) => setSenha(e.target.value)} />
        </div>
        <div className="form-field">
          <label htmlFor="us-orgao">Órgão {exigeOrgao ? "(obrigatório)" : "(opcional)"}</label>
          <select id="us-orgao" value={f.orgao_id ?? ""} onChange={(e) => setF({ ...f, orgao_id: e.target.value || null })}>
            <option value="">Todos os órgãos (equipe CGE-GO)</option>
            {orgaos.data?.map((o) => <option key={o.ckan_id} value={o.ckan_id}>{o.titulo}</option>)}
          </select>
          <span className="help">Com órgão definido, o usuário só enxerga dados daquele órgão.</span>
        </div>
        <div className="form-field full">
          <label>Papéis</label>
          {papeis.map((p) => (
            <label key={p.id} className="check-line">
              <input type="checkbox" checked={f.papel_ids.includes(p.id)} onChange={() => alternar(p.id)} />
              <span><strong>{p.nome}</strong>{p.exige_orgao && " · exige órgão"} — {p.descricao}</span>
            </label>
          ))}
        </div>
        <label className="check-line full">
          <input type="checkbox" checked={f.ativo} onChange={(e) => setF({ ...f, ativo: e.target.checked })} />
          <span>Usuário ativo (desmarcar encerra o acesso imediatamente)</span>
        </label>
        {erro && <div className="inline-msg err full">{erro}</div>}
      </div>
    </Modal>
  );
}
