import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { PerfilCkan, PerfilCkanIn } from "./api";
import { ckanApi } from "./api";
import { PageLede } from "@/shared/ui/PageLede";
import { useToast } from "@/shared/ui/Toast";

const fmt = (iso: string) => new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });

interface FormState {
  id: number | null;      // null = novo perfil
  nome: string;
  base_url: string;
  auditoria_base_url: string;
  auditoria_api_token: string;
  remover_token: boolean;  // só na edição: apagar o token salvo
  tem_token: boolean;
}

const VAZIO: FormState = {
  id: null, nome: "", base_url: "", auditoria_base_url: "", auditoria_api_token: "",
  remover_token: false, tem_token: false,
};

function doPerfil(p: PerfilCkan): FormState {
  return {
    id: p.id, nome: p.nome, base_url: p.base_url, auditoria_base_url: p.auditoria_base_url ?? "",
    auditoria_api_token: "", remover_token: false, tem_token: p.tem_token,
  };
}

export default function ConfiguracoesCkanPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const perfis = useQuery({ queryKey: ["ckan", "perfis"], queryFn: ckanApi.perfis });
  const [form, setForm] = useState<FormState | null>(null);

  const recarregar = () => qc.invalidateQueries({ queryKey: ["ckan"] });
  const set = (patch: Partial<FormState>) => setForm((f) => (f ? { ...f, ...patch } : f));

  const salvar = useMutation({
    mutationFn: (f: FormState) => {
      const corpo: PerfilCkanIn = {
        nome: f.nome.trim(),
        base_url: f.base_url.trim(),
        auditoria_base_url: f.auditoria_base_url.trim() || null,
        // ausente = mantém; "" = remove; texto = substitui
        auditoria_api_token: f.remover_token ? "" : (f.auditoria_api_token.trim() || undefined),
      };
      return f.id == null ? ckanApi.criar(corpo) : ckanApi.atualizar(f.id, corpo);
    },
    onSuccess: () => { toast("Perfil salvo."); setForm(null); recarregar(); },
    onError: (e: Error) => toast(e.message, true),
  });

  const selecionar = useMutation({
    mutationFn: (p: PerfilCkan) => ckanApi.selecionar(p.id),
    onSuccess: (p) => { toast(`Agora o sistema usa o CKAN “${p.nome}”.`); recarregar(); },
    onError: (e: Error) => toast(e.message, true),
  });

  const excluir = useMutation({
    mutationFn: (p: PerfilCkan) => ckanApi.excluir(p.id),
    onSuccess: () => { toast("Perfil excluído."); recarregar(); },
    onError: (e: Error) => toast(e.message, true),
  });

  const lista = perfis.data ?? [];

  return (
    <section className="screen">
      <PageLede titulo="Configurações CKAN">
        Cadastre perfis de conexão com o CKAN e escolha qual deles o sistema usa. A troca vale na
        hora, para toda a solução (coleta do inventário, varredura LGPD e auditoria/diff da
        rastreabilidade).
      </PageLede>

      <div className="alert-callout">
        <i className="fa-solid fa-triangle-exclamation" />
        <div>
          Trocar o CKAN em uso passa a valer <strong>na hora e para todo o sistema</strong>,
          sobrepondo o que está no <code>.env</code>/<code>GDA_ENVIRONMENT</code>. <strong>Não apaga</strong> os
          dados já coletados (inventário, eventos, achados) — apenas muda de qual CKAN as próximas
          leituras virão.
        </div>
      </div>

      <div className="panel">
        <div className="panel-head">
          <div>
            <h3>Perfis de conexão</h3>
            <div className="sub">O perfil em uso rege toda a solução</div>
          </div>
          <button type="button" className="btn btn-primary btn-sm" onClick={() => setForm(VAZIO)}>
            <i className="fa-solid fa-plus" style={{ marginRight: 4 }} /> Novo perfil
          </button>
        </div>

        {perfis.isError && (
          <div className="inline-msg err" role="alert">{(perfis.error as Error).message}</div>
        )}
        {!perfis.isError && lista.length === 0 && (
          <div className="tl-meta" style={{ padding: 12 }}>Nenhum perfil cadastrado ainda.</div>
        )}

        {lista.length > 0 && (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Nome</th><th>Leitura pública</th><th>Auditoria (dsaudit)</th>
                  <th>Token</th><th>Em uso</th><th />
                </tr>
              </thead>
              <tbody>
                {lista.map((p) => (
                  <tr key={p.id}>
                    <td><b>{p.nome}</b><div className="tl-meta" style={{ color: "var(--gray-500)" }}>Atualizado em {fmt(p.atualizado_em)}</div></td>
                    <td className="mono" style={{ wordBreak: "break-all" }}>{p.base_url}</td>
                    <td className="mono" style={{ wordBreak: "break-all" }}>{p.auditoria_base_url ?? <span className="cell-muted">(usa a leitura pública)</span>}</td>
                    <td>{p.tem_token ? <span className="mono">{p.auditoria_api_token_dica}</span> : <span className="cell-muted">—</span>}</td>
                    <td>{p.selecionado ? <span className="badge badge-green">Em uso</span> : <span className="cell-muted">—</span>}</td>
                    <td style={{ whiteSpace: "nowrap", textAlign: "right" }}>
                      {!p.selecionado && (
                        <button type="button" className="btn btn-primary btn-sm" disabled={selecionar.isPending}
                                onClick={() => selecionar.mutate(p)}>
                          Usar este CKAN
                        </button>
                      )}
                      <button type="button" className="btn btn-ghost btn-sm" style={{ marginLeft: 6 }}
                              onClick={() => setForm(doPerfil(p))}>Editar</button>
                      {!p.selecionado && (
                        <button type="button" className="btn btn-ghost btn-sm" style={{ marginLeft: 6 }}
                                disabled={excluir.isPending}
                                onClick={() => { if (confirm(`Excluir o perfil “${p.nome}”?`)) excluir.mutate(p); }}>
                          Excluir
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {form && (
        <div className="panel">
          <div className="panel-head">
            <div><h3>{form.id == null ? "Novo perfil" : `Editar “${form.nome}”`}</h3></div>
          </div>
          <form className="form-grid" style={{ padding: 12, display: "grid", gap: 14, maxWidth: 680 }}
                onSubmit={(e) => { e.preventDefault(); salvar.mutate(form); }}>
            <label>
              <div><b>Nome</b></div>
              <div className="tl-meta" style={{ color: "var(--gray-500)" }}>Identifica a conexão (ex.: CKAN Docker, Homologação, Portal).</div>
              <input value={form.nome} onChange={(e) => set({ nome: e.target.value })} required minLength={2} maxLength={120} />
            </label>

            <label>
              <div><b>URL de leitura pública</b></div>
              <div className="tl-meta" style={{ color: "var(--gray-500)" }}>
                CKAN para a coleta do inventário e o download de recursos (LGPD). Ex.:
                <code> http://ckansquad2-ckan-1:5000</code> (Docker local) ou
                <code> https://dadosabertos.go.gov.br</code> (portal).
              </div>
              <input value={form.base_url} onChange={(e) => set({ base_url: e.target.value })}
                     required placeholder="http://ckansquad2-ckan-1:5000" />
            </label>

            <label>
              <div><b>URL da auditoria (dsaudit) <span className="cell-muted">— opcional</span></b></div>
              <div className="tl-meta" style={{ color: "var(--gray-500)" }}>
                CKAN de onde a auditoria/diff (extensão <code>dsaudit</code>) é lida. Deixe vazio para
                usar a mesma URL de leitura pública. É o CKAN onde as edições ocorrem e o dsaudit está
                instalado.
              </div>
              <input value={form.auditoria_base_url} onChange={(e) => set({ auditoria_base_url: e.target.value })}
                     placeholder="(vazio = usa a leitura pública)" />
            </label>

            <label>
              <div><b>Token da auditoria <span className="cell-muted">— opcional</span></b></div>
              <div className="tl-meta" style={{ color: "var(--gray-500)" }}>
                Token de API de um usuário <b>editor</b> das organizações (exigido pela
                <code> dsaudit_activity_list</code>). É guardado cifrado.
                {form.id != null && form.tem_token && " Deixe em branco para manter o token atual."}
              </div>
              <input type="password" autoComplete="new-password" value={form.auditoria_api_token}
                     disabled={form.remover_token}
                     onChange={(e) => set({ auditoria_api_token: e.target.value })}
                     placeholder={form.id != null && form.tem_token ? "•••• (mantém o atual)" : "cole o token aqui"} />
              {form.id != null && form.tem_token && (
                <label style={{ display: "flex", gap: 6, alignItems: "center", marginTop: 6, fontWeight: "normal" }}>
                  <input type="checkbox" checked={form.remover_token}
                         onChange={(e) => set({ remover_token: e.target.checked })} />
                  Remover o token salvo
                </label>
              )}
            </label>

            <div style={{ display: "flex", gap: 8 }}>
              <button type="submit" className="btn btn-primary" disabled={salvar.isPending}>
                {salvar.isPending ? "Salvando…" : "Salvar perfil"}
              </button>
              <button type="button" className="btn btn-ghost" onClick={() => setForm(null)}>Cancelar</button>
            </div>
          </form>
        </div>
      )}
    </section>
  );
}
