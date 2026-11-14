import type { FormEvent } from "react";
import { useEffect, useState } from "react";
import { useAuth } from "@/app/auth/AuthContext";
import { Modal } from "@/shared/ui/Modal";
import { useToast } from "@/shared/ui/Toast";

/** Troca da própria senha (qualquer usuário logado). A regra da senha é conferida pela API. */
export function TrocarSenhaModal({ aberto, onFechar }: { aberto: boolean; onFechar: () => void }) {
  const { trocarSenha } = useAuth();
  const toast = useToast();
  const [atual, setAtual] = useState("");
  const [nova, setNova] = useState("");
  const [repetida, setRepetida] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);

  useEffect(() => {
    if (!aberto) return;
    setAtual(""); setNova(""); setRepetida(""); setErro(null);
  }, [aberto]);

  async function salvar(e: FormEvent) {
    e.preventDefault();
    if (nova !== repetida) return setErro("A confirmação não é igual à nova senha.");
    setSalvando(true);
    setErro(null);
    try {
      await trocarSenha(atual, nova);
      toast("Senha alterada. As outras sessões abertas foram encerradas.");
      onFechar();
    } catch (ex) {
      setErro(ex instanceof Error ? ex.message : "Não foi possível trocar a senha.");
    } finally {
      setSalvando(false);
    }
  }

  return (
    <Modal aberto={aberto} onFechar={onFechar} titulo="Trocar senha"
      subtitulo="Mínimo de 8 caracteres, com letras e números."
      rodape={<button className="btn btn-primary btn-sm" type="submit" form="form-trocar-senha" disabled={salvando}>
        <i className="fa-solid fa-key" />Trocar senha
      </button>}>
      <form id="form-trocar-senha" className="form-grid" onSubmit={salvar}>
        <div className="form-field full">
          <label htmlFor="ts-atual">Senha atual</label>
          <input id="ts-atual" className="text-input" type="password" autoComplete="current-password"
                 required value={atual} onChange={(e) => setAtual(e.target.value)} />
        </div>
        <div className="form-field">
          <label htmlFor="ts-nova">Nova senha</label>
          <input id="ts-nova" className="text-input" type="password" autoComplete="new-password"
                 required minLength={8} value={nova} onChange={(e) => setNova(e.target.value)} />
        </div>
        <div className="form-field">
          <label htmlFor="ts-repetida">Repita a nova senha</label>
          <input id="ts-repetida" className="text-input" type="password" autoComplete="new-password"
                 required minLength={8} value={repetida} onChange={(e) => setRepetida(e.target.value)} />
        </div>
        {erro && <div className="inline-msg err full" role="alert">{erro}</div>}
      </form>
    </Modal>
  );
}
