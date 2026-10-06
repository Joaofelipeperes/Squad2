import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { PerfilIA, TarefaIA } from "./api";
import { iaApi } from "./api";
import { PerfilForm } from "./PerfilForm";
import { PageLede } from "@/shared/ui/PageLede";
import { useToast } from "@/shared/ui/Toast";

const fmt = (iso: string) => new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });

export default function ModelosIAPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const tipos = useQuery({ queryKey: ["ia", "tipos"], queryFn: iaApi.tipos });
  const perfis = useQuery({ queryKey: ["ia", "perfis"], queryFn: iaApi.perfis });
  const tarefas = useQuery({ queryKey: ["ia", "tarefas"], queryFn: iaApi.tarefas });
  const uso = useQuery({ queryKey: ["ia", "uso"], queryFn: iaApi.uso });
  const [form, setForm] = useState<{ aberto: boolean; perfil: PerfilIA | null }>({ aberto: false, perfil: null });

  const recarregar = () => qc.invalidateQueries({ queryKey: ["ia"] });
  const rotuloTipo = (t: string) => tipos.data?.find((x) => x.tipo === t)?.rotulo ?? t;

  const vincular = useMutation({
    mutationFn: (v: { t: TarefaIA; perfil_id: number | null; perfil_fallback_id: number | null }) =>
      iaApi.vincular(v.t.tarefa, { perfil_id: v.perfil_id, perfil_fallback_id: v.perfil_fallback_id }),
    onSuccess: () => { toast("Vínculo atualizado."); recarregar(); },
    onError: (e: Error) => toast(e.message, true),
  });
  const testar = useMutation({
    mutationFn: (p: PerfilIA) => iaApi.testarPerfil(p.id),
    onSuccess: (r) => { toast(r.mensagem, !r.ok); recarregar(); },
  });
  const excluir = useMutation({
    mutationFn: (p: PerfilIA) => iaApi.excluir(p.id),
    onSuccess: () => { toast("Perfil excluído."); recarregar(); },
    onError: (e: Error) => toast(e.message, true),
  });

  return (
    <section className="screen">
      <PageLede titulo="Modelos de IA">
        Escolha qual modelo atende cada tarefa de IA da solução. Troque entre modelos locais e
        comerciais sem alterar código: basta cadastrar um perfil e vinculá-lo à tarefa.
      </PageLede>

      <div className="alert-callout">
        <i className="fa-solid fa-shield-halved" />
        <div>
          Tarefas que processam dados pessoais só aceitam modelos de <strong>execução local</strong>,
          para que o conteúdo dos recursos não saia da infraestrutura do Estado. O Assistente GEDA
          recebe apenas indicadores agregados e pode usar um modelo comercial.
        </div>
      </div>

      {/* ------------------------------------------------ Tarefas */}
      <div className="panel">
        <div className="panel-head">
          <div><h3>Tarefas de IA</h3><div className="sub">Modelo principal e de contingência por tarefa</div></div>
        </div>
        <div className="table-scroll">
          <table>
            <thead><tr><th>Tarefa</th><th>Modelo principal</th><th>Contingência</th><th>Situação</th></tr></thead>
            <tbody>
              {tarefas.data?.map((t) => {
                const opcoes = (perfis.data ?? []).filter((p) => p.ativo);
                const select = (valor: number | null, campo: "perfil_id" | "perfil_fallback_id") => (
                  <select value={valor ?? ""} disabled={vincular.isPending}
                    onChange={(e) => {
                      const id = e.target.value ? Number(e.target.value) : null;
                      vincular.mutate({ t, perfil_id: campo === "perfil_id" ? id : t.perfil_id,
                        perfil_fallback_id: campo === "perfil_fallback_id" ? id : t.perfil_fallback_id });
                    }}>
                    <option value="">{campo === "perfil_id" ? "— não configurado —" : "— nenhuma —"}</option>
                    {opcoes.map((p) => (
                      <option key={p.id} value={p.id} disabled={t.somente_local && !p.execucao_local}>
                        {p.nome} · {p.modelo}{t.somente_local && !p.execucao_local ? " (externo — bloqueado)" : ""}
                      </option>
                    ))}
                  </select>
                );
                return (
                  <tr key={t.tarefa}>
                    <td style={{ minWidth: 300, maxWidth: 420 }}>
                      <div className="cell-strong">{t.rotulo}{" "}
                        <span className="badge badge-gray">{t.user_story}</span>{" "}
                        {t.sensivel && <span className="badge badge-red">Dado pessoal</span>}
                      </div>
                      <div className="cell-muted" style={{ fontSize: 12, marginTop: 4 }}>{t.descricao}</div>
                    </td>
                    <td>{select(t.perfil_id, "perfil_id")}</td>
                    <td>{select(t.perfil_fallback_id, "perfil_fallback_id")}</td>
                    <td>{t.perfil_id
                      ? <span className="badge badge-green">Configurada</span>
                      : <span className="badge badge-amber">Sem modelo</span>}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* ------------------------------------------------ Perfis */}
      <div className="panel">
        <div className="panel-head">
          <div><h3>Perfis de modelo</h3><div className="sub">Provedores cadastrados e suas credenciais</div></div>
          <button className="btn btn-primary btn-sm" onClick={() => setForm({ aberto: true, perfil: null })}
                  disabled={!tipos.data}>
            <i className="fa-solid fa-plus" />Novo perfil
          </button>
        </div>
        <div className="table-scroll">
          <table>
            <thead><tr><th>Nome</th><th>Provedor</th><th>Modelo</th><th>Execução</th><th>Chave</th><th>Status</th><th /></tr></thead>
            <tbody>
              {perfis.data?.length === 0 && (
                <tr><td colSpan={7}><div className="empty-state">
                  <i className="fa-solid fa-microchip" />
                  <p>Nenhum perfil cadastrado. Crie um perfil local (Ollama) ou comercial (Gemini) para começar.</p>
                </div></td></tr>
              )}
              {perfis.data?.map((p) => (
                <tr key={p.id}>
                  <td className="cell-strong">{p.nome}</td>
                  <td>{rotuloTipo(p.tipo)}</td>
                  <td className="mono">{p.modelo}</td>
                  <td>{p.execucao_local
                    ? <span className="badge badge-green">Local</span>
                    : <span className="badge badge-amber">Externo</span>}</td>
                  <td className="mono cell-muted">{p.tem_chave ? p.api_key_dica : "—"}</td>
                  <td>{p.ativo ? <span className="badge badge-blue">Ativo</span> : <span className="badge badge-gray">Inativo</span>}</td>
                  <td>
                    <div className="row-actions">
                      <button className="btn btn-ghost btn-sm" onClick={() => testar.mutate(p)} disabled={testar.isPending}>
                        <i className="fa-solid fa-plug" />Testar
                      </button>
                      <button className="btn btn-ghost btn-sm" onClick={() => setForm({ aberto: true, perfil: p })}>
                        <i className="fa-solid fa-pen" />Editar
                      </button>
                      <button className="btn btn-danger-line btn-sm"
                        onClick={() => confirm(`Excluir o perfil “${p.nome}”?`) && excluir.mutate(p)}>
                        <i className="fa-solid fa-trash" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <Playground tarefas={tarefas.data ?? []} onUsado={() => qc.invalidateQueries({ queryKey: ["ia", "uso"] })} />

      {/* ------------------------------------------------ Uso */}
      <div className="panel">
        <div className="panel-head">
          <div><h3>Uso recente</h3><div className="sub">Somente metadados da chamada — prompts e respostas não são armazenados</div></div>
        </div>
        <div className="table-scroll">
          <table>
            <thead><tr><th>Quando</th><th>Tarefa</th><th>Perfil</th><th>Modelo</th><th>Tempo</th><th>Tokens</th><th>Resultado</th></tr></thead>
            <tbody>
              {uso.data?.map((u, i) => (
                <tr key={i}>
                  <td>{fmt(u.momento)}</td>
                  <td>{tarefas.data?.find((t) => t.tarefa === u.tarefa)?.rotulo ?? u.tarefa}</td>
                  <td>{u.perfil_nome}{u.usou_fallback && <span className="badge badge-amber" style={{ marginLeft: 6 }}>contingência</span>}</td>
                  <td className="mono">{u.modelo}</td>
                  <td>{u.latencia_ms != null ? `${u.latencia_ms} ms` : "—"}</td>
                  <td>{u.tokens_entrada ?? "—"} / {u.tokens_saida ?? "—"}</td>
                  <td>{u.sucesso ? <span className="badge badge-green">OK</span>
                    : <span className="badge badge-red" title={u.erro ?? ""}>Falhou</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {tipos.data && (
        <PerfilForm aberto={form.aberto} perfil={form.perfil} tipos={tipos.data}
          onFechar={() => setForm({ aberto: false, perfil: null })} onSalvo={recarregar} />
      )}
    </section>
  );
}

function Playground({ tarefas, onUsado }: { tarefas: TarefaIA[]; onUsado: () => void }) {
  const [tarefa, setTarefa] = useState("assistente");
  const [msg, setMsg] = useState("Quantos datasets foram coletados na última coleta?");
  const enviar = useMutation({
    mutationFn: () => iaApi.playground({ tarefa, mensagem: msg }),
    onSettled: onUsado,
  });
  return (
    <div className="panel">
      <div className="panel-head">
        <div><h3>Testar tarefa</h3><div className="sub">Envia uma mensagem pelo mesmo caminho que os módulos usam</div></div>
      </div>
      <div className="panel-body">
        <div className="form-grid">
          <div className="form-field">
            <label htmlFor="pg-tarefa">Tarefa</label>
            <select id="pg-tarefa" value={tarefa} onChange={(e) => setTarefa(e.target.value)}>
              {tarefas.map((t) => <option key={t.tarefa} value={t.tarefa}>{t.rotulo}</option>)}
            </select>
          </div>
          <div className="form-field full">
            <label htmlFor="pg-msg">Mensagem</label>
            <textarea id="pg-msg" className="text-input" value={msg} onChange={(e) => setMsg(e.target.value)} />
            <span className="help">Use apenas dados fictícios neste teste.</span>
          </div>
          <div className="full">
            <button className="btn btn-primary btn-sm" onClick={() => enviar.mutate()}
                    disabled={enviar.isPending || !msg.trim()}>
              <i className="fa-solid fa-paper-plane" />{enviar.isPending ? "Enviando…" : "Enviar"}
            </button>
          </div>
          {enviar.data && (
            <div className="inline-msg ok full">
              <div style={{ whiteSpace: "pre-wrap", color: "var(--ink)" }}>{enviar.data.texto}</div>
              <div style={{ marginTop: 6, fontSize: 12 }}>
                {enviar.data.perfil} · {enviar.data.modelo}
                {enviar.data.latencia_ms != null && ` · ${enviar.data.latencia_ms} ms`}
                {enviar.data.usou_fallback && " · respondeu a contingência"}
              </div>
            </div>
          )}
          {enviar.error && <div className="inline-msg err full">{(enviar.error as Error).message}</div>}
        </div>
      </div>
    </div>
  );
}
