import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { PerfilCkan } from "./api";
import { ckanApi } from "./api";
import { PerfilCkanForm } from "./PerfilCkanForm";
import { PageLede } from "@/shared/ui/PageLede";
import { useToast } from "@/shared/ui/Toast";

const fmt = (iso: string) => new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });

export default function ConfiguracoesCkanPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const perfis = useQuery({ queryKey: ["ckan", "perfis"], queryFn: ckanApi.perfis });
  const [form, setForm] = useState<{ aberto: boolean; perfil: PerfilCkan | null }>({ aberto: false, perfil: null });

  const recarregar = () => qc.invalidateQueries({ queryKey: ["ckan"] });

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
          <button type="button" className="btn btn-primary btn-sm" onClick={() => setForm({ aberto: true, perfil: null })}>
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
                              onClick={() => setForm({ aberto: true, perfil: p })}>Editar</button>
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

      <PerfilCkanForm aberto={form.aberto} perfil={form.perfil}
        onFechar={() => setForm({ aberto: false, perfil: null })}
        onSalvo={() => { toast("Perfil salvo."); recarregar(); }} />
    </section>
  );
}
