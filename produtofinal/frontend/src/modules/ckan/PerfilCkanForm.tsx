import { useMutation } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import type { PerfilCkan, PerfilCkanIn } from "./api";
import { ckanApi } from "./api";
import { Modal } from "@/shared/ui/Modal";

interface Props {
  aberto: boolean;
  perfil: PerfilCkan | null; // null = novo
  onFechar: () => void;
  onSalvo: () => void;
}

interface FormState {
  nome: string;
  base_url: string;
  auditoria_base_url: string;
  auditoria_api_token: string;
  remover_token: boolean; // só na edição: apagar o token salvo
}

const VAZIO: FormState = { nome: "", base_url: "", auditoria_base_url: "", auditoria_api_token: "", remover_token: false };

export function PerfilCkanForm({ aberto, perfil, onFechar, onSalvo }: Props) {
  const [f, setF] = useState<FormState>(VAZIO);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    if (!aberto) return;
    setF(perfil
      ? { nome: perfil.nome, base_url: perfil.base_url, auditoria_base_url: perfil.auditoria_base_url ?? "",
          auditoria_api_token: "", remover_token: false }
      : VAZIO);
    setErro(null);
  }, [aberto, perfil]);

  const set = (patch: Partial<FormState>) => setF((s) => ({ ...s, ...patch }));
  const temToken = !!perfil?.tem_token;

  const salvar = useMutation({
    mutationFn: () => {
      const corpo: PerfilCkanIn = {
        nome: f.nome.trim(),
        base_url: f.base_url.trim(),
        auditoria_base_url: f.auditoria_base_url.trim() || null,
        // ausente = mantém; "" = remove; texto = substitui
        auditoria_api_token: f.remover_token ? "" : (f.auditoria_api_token.trim() || undefined),
      };
      return perfil ? ckanApi.atualizar(perfil.id, corpo) : ckanApi.criar(corpo);
    },
    onSuccess: () => { onSalvo(); onFechar(); },
    onError: (e: Error) => setErro(e.message),
  });

  return (
    <Modal aberto={aberto} onFechar={onFechar}
      titulo={perfil ? `Editar perfil “${perfil.nome}”` : "Novo perfil de conexão"}
      subtitulo="Um perfil reúne a URL de leitura pública e, opcionalmente, a URL e o token da auditoria (dsaudit)."
      rodape={<>
        <button type="button" className="btn btn-ghost btn-sm" onClick={onFechar}>Cancelar</button>
        <button type="submit" form="pc-form" className="btn btn-primary btn-sm" disabled={salvar.isPending}>
          <i className="fa-solid fa-floppy-disk" />{salvar.isPending ? "Salvando…" : "Salvar perfil"}
        </button>
      </>}>
      <form id="pc-form" className="form-grid" onSubmit={(e) => { e.preventDefault(); salvar.mutate(); }}>
        <div className="form-field full">
          <label htmlFor="pc-nome">Nome</label>
          <input id="pc-nome" className="text-input" value={f.nome} required minLength={2} maxLength={120}
                 placeholder="Ex.: CKAN Docker, Homologação, Portal"
                 onChange={(e) => set({ nome: e.target.value })} />
        </div>

        <div className="form-field full">
          <label htmlFor="pc-url">URL de leitura pública</label>
          <input id="pc-url" className="text-input mono" value={f.base_url} required
                 placeholder="http://ckansquad2-ckan-1:5000"
                 onChange={(e) => set({ base_url: e.target.value })} />
          <span className="help">
            CKAN para a coleta do inventário e o download de recursos (LGPD). Ex.:
            <code> http://ckansquad2-ckan-1:5000</code> (Docker local) ou
            <code> https://dadosabertos.go.gov.br</code> (portal).
          </span>
        </div>

        <div className="form-field full">
          <label htmlFor="pc-aud-url">URL da auditoria (dsaudit) — opcional</label>
          <input id="pc-aud-url" className="text-input mono" value={f.auditoria_base_url}
                 placeholder="(vazio = usa a leitura pública)"
                 onChange={(e) => set({ auditoria_base_url: e.target.value })} />
          <span className="help">
            CKAN onde as edições ocorrem e a extensão <code>dsaudit</code> está instalada. Deixe vazio
            para usar a mesma URL de leitura pública.
          </span>
        </div>

        <div className="form-field full">
          <label htmlFor="pc-token">Token da auditoria — opcional</label>
          <input id="pc-token" className="text-input" type="password" autoComplete="new-password"
                 value={f.auditoria_api_token} disabled={f.remover_token}
                 placeholder={temToken ? `Atual: ${perfil?.auditoria_api_token_dica} (deixe vazio para manter)` : "cole o token aqui"}
                 onChange={(e) => set({ auditoria_api_token: e.target.value })} />
          <span className="help">
            Token de API de um usuário <b>editor</b> das organizações (exigido pela
            <code> dsaudit_activity_list</code>). Armazenado cifrado; nunca é exibido de volta.
          </span>
        </div>

        {temToken && (
          <label className="check-line full">
            <input type="checkbox" checked={f.remover_token}
                   onChange={(e) => set({ remover_token: e.target.checked })} />
            <span>Remover o token salvo</span>
          </label>
        )}

        {erro && <div className="inline-msg err full">{erro}</div>}
      </form>
    </Modal>
  );
}
