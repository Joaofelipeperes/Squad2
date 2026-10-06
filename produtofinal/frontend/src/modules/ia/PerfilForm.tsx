import { useMutation } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import type { PerfilIA, PerfilIn, TesteConexao, TipoProvedor } from "./api";
import { iaApi } from "./api";
import { Modal } from "@/shared/ui/Modal";

interface Props {
  aberto: boolean;
  tipos: TipoProvedor[];
  perfil: PerfilIA | null; // null = novo
  onFechar: () => void;
  onSalvo: () => void;
}

const VAZIO: PerfilIn = {
  nome: "", tipo: "ollama", modelo: "", base_url: "", execucao_local: true,
  temperatura: 0.2, max_tokens: 1024, timeout_s: 60, ativo: true,
};

export function PerfilForm({ aberto, tipos, perfil, onFechar, onSalvo }: Props) {
  const [f, setF] = useState<PerfilIn>(VAZIO);
  const [apiKey, setApiKey] = useState("");
  const [teste, setTeste] = useState<TesteConexao | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    if (!aberto) return;
    setF(perfil ? { ...perfil, base_url: perfil.base_url ?? "" } : VAZIO);
    setApiKey("");
    setTeste(null);
    setErro(null);
  }, [aberto, perfil]);

  const tipo = useMemo(() => tipos.find((t) => t.tipo === f.tipo), [tipos, f.tipo]);
  const campo = (n: string) => tipo?.campos.find((c) => c.name === n);
  const modelosLista = teste?.modelos.length ? teste.modelos : (tipo?.modelos_sugeridos ?? []);
  const set = <K extends keyof PerfilIn>(k: K, v: PerfilIn[K]) => setF((s) => ({ ...s, [k]: v }));

  function trocarTipo(novo: string) {
    const t = tipos.find((x) => x.tipo === novo);
    setF((s) => ({ ...s, tipo: novo, base_url: "", modelo: t?.modelos_sugeridos[0] ?? "",
                   execucao_local: t?.local_por_padrao ?? false }));
    setTeste(null);
  }

  const testar = useMutation({
    mutationFn: () => iaApi.testarConexao({ tipo: f.tipo, modelo: f.modelo || "teste",
      base_url: f.base_url || null, api_key: apiKey || null, perfil_id: perfil?.id }),
    onSuccess: setTeste,
    onError: (e: Error) => setTeste({ ok: false, mensagem: e.message, latencia_ms: null, modelos: [] }),
  });

  const salvar = useMutation({
    mutationFn: () => {
      const body: PerfilIn = { ...f, base_url: f.base_url || null,
        // chave: vazio na edição = manter a atual; preenchido = substituir
        api_key: apiKey ? apiKey : perfil ? null : undefined };
      return perfil ? iaApi.atualizar(perfil.id, body) : iaApi.criar(body);
    },
    onSuccess: () => { onSalvo(); onFechar(); },
    onError: (e: Error) => setErro(e.message),
  });

  return (
    <Modal aberto={aberto} onFechar={onFechar}
      titulo={perfil ? `Editar perfil “${perfil.nome}”` : "Novo perfil de modelo"}
      subtitulo="Um perfil combina provedor, modelo e credencial. Ele pode ser vinculado a uma ou mais tarefas."
      rodape={<>
        <button className="btn btn-outline btn-sm" onClick={() => testar.mutate()} disabled={testar.isPending}>
          <i className="fa-solid fa-plug" />{testar.isPending ? "Testando…" : "Testar conexão"}
        </button>
        <button className="btn btn-primary btn-sm" onClick={() => salvar.mutate()} disabled={salvar.isPending}>
          <i className="fa-solid fa-floppy-disk" />Salvar perfil
        </button>
      </>}>
      <div className="form-grid">
        <div className="form-field">
          <label htmlFor="pf-tipo">Provedor</label>
          <select id="pf-tipo" value={f.tipo} onChange={(e) => trocarTipo(e.target.value)} disabled={!!perfil}>
            {tipos.map((t) => <option key={t.tipo} value={t.tipo}>{t.rotulo}</option>)}
          </select>
        </div>
        <div className="form-field">
          <label htmlFor="pf-nome">Nome do perfil</label>
          <input id="pf-nome" className="text-input" value={f.nome} placeholder="Ex.: Gemini SECTI"
                 onChange={(e) => set("nome", e.target.value)} />
        </div>
        {tipo && <p className="help full" style={{ fontSize: 12.5, color: "var(--gray-700)" }}>{tipo.descricao}</p>}

        {campo("base_url") && (
          <div className="form-field full">
            <label htmlFor="pf-url">{campo("base_url")!.label}</label>
            <input id="pf-url" className="text-input mono" value={f.base_url ?? ""}
                   placeholder={campo("base_url")!.placeholder ?? ""}
                   onChange={(e) => set("base_url", e.target.value)} />
            {campo("base_url")!.help && <span className="help">{campo("base_url")!.help}</span>}
          </div>
        )}
        <div className="form-field">
          <label htmlFor="pf-modelo">Modelo</label>
          <input id="pf-modelo" className="text-input mono" list="pf-modelos" value={f.modelo}
                 placeholder={campo("model")?.placeholder ?? ""} onChange={(e) => set("modelo", e.target.value)} />
          <datalist id="pf-modelos">{modelosLista.map((m) => <option key={m} value={m} />)}</datalist>
          <span className="help">“Testar conexão” carrega os modelos disponíveis no provedor.</span>
        </div>
        {campo("api_key") && (
          <div className="form-field">
            <label htmlFor="pf-key">{campo("api_key")!.label}</label>
            <input id="pf-key" className="text-input" type="password" autoComplete="off" value={apiKey}
                   placeholder={perfil?.tem_chave ? `Atual: ${perfil.api_key_dica} (deixe vazio para manter)` : ""}
                   onChange={(e) => setApiKey(e.target.value)} />
            <span className="help">Armazenada cifrada. Nunca é exibida de volta.</span>
          </div>
        )}

        <label className="check-line full">
          <input type="checkbox" checked={f.execucao_local}
                 onChange={(e) => set("execucao_local", e.target.checked)} />
          <span><strong>Execução local</strong> — o modelo roda na infraestrutura do Estado e nenhum
            dado sai do servidor. Somente perfis locais podem atender tarefas que processam dados pessoais.</span>
        </label>

        <div className="form-field">
          <label htmlFor="pf-temp">Temperatura</label>
          <input id="pf-temp" className="text-input" type="number" step="0.1" min={0} max={2}
                 value={f.temperatura} onChange={(e) => set("temperatura", Number(e.target.value))} />
        </div>
        <div className="form-field">
          <label htmlFor="pf-max">Máx. tokens de resposta</label>
          <input id="pf-max" className="text-input" type="number" min={16} value={f.max_tokens}
                 onChange={(e) => set("max_tokens", Number(e.target.value))} />
        </div>
        <div className="form-field">
          <label htmlFor="pf-timeout">Tempo limite (s)</label>
          <input id="pf-timeout" className="text-input" type="number" min={5} value={f.timeout_s}
                 onChange={(e) => set("timeout_s", Number(e.target.value))} />
        </div>
        <label className="check-line" style={{ alignSelf: "end" }}>
          <input type="checkbox" checked={f.ativo} onChange={(e) => set("ativo", e.target.checked)} />
          <span>Perfil ativo</span>
        </label>

        {teste && (
          <div className={`inline-msg full ${teste.ok ? "ok" : "err"}`}>
            {teste.mensagem}{teste.latencia_ms != null && ` (${teste.latencia_ms} ms)`}
          </div>
        )}
        {erro && <div className="inline-msg err full">{erro}</div>}
      </div>
    </Modal>
  );
}
