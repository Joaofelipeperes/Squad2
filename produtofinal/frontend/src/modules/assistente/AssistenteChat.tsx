import { useMutation } from "@tanstack/react-query";
import type { FormEvent, ReactNode } from "react";
import { useEffect, useRef, useState } from "react";
import { api } from "@/shared/api/client";

interface Fonte { tipo: "dataset" | "orgao" | "pda"; id: string; titulo: string }
interface Resposta { resposta: string; modelo: string; fontes: Fonte[] }
interface Msg {
  autor: "user" | "bot";
  texto: string;
  fontes?: Fonte[];
  /** Saudação e mensagens de erro não vão no histórico enviado ao modelo. */
  local?: boolean;
}

// Mesmas sugestões do Protótipo V1, ajustadas aos dados reais
const SUGESTOES = [
  "Quais bases estão atrasadas?",
  "Quantos alertas de LGPD existem?",
  "Próximos prazos do PDA",
  "Situação da Secretaria da Saúde",
  "Datasets sem recurso publicado",
];
const SAUDACAO =
  "Olá! Sou o assistente de consulta da GEDA. Posso responder perguntas sobre bases do PDA, " +
  "datasets, arquivos, prazos e alertas de LGPD com base na última coleta do portal.";
const HISTORICO_MAX = 6;

/** Negrito (**texto**) dentro de uma linha, sem interpretar HTML vindo da resposta. */
function negrito(linha: string): ReactNode[] {
  return linha.split(/(\*\*[^*]+\*\*)/g).map((parte, i) =>
    parte.startsWith("**") && parte.endsWith("**") && parte.length > 4
      ? <b key={i}>{parte.slice(2, -2)}</b>
      : parte);
}

/** Markdown mínimo da resposta: negrito e listas ("- " ou "* " viram "•"). */
function Formatado({ texto }: { texto: string }) {
  const linhas = texto.replace(/\n{3,}/g, "\n\n").trim().split("\n");
  return (
    <>
      {linhas.map((l, i) => {
        const item = l.match(/^(\s*)[-*•]\s+(.*)$/);
        const titulo = l.match(/^#{1,4}\s+(.*)$/);
        const conteudo = item ? ["• ", ...negrito(item[2])]
          : titulo ? [<b key="t">{titulo[1]}</b>] : negrito(l);
        return <span key={i}>{item?.[1]}{conteudo}{i < linhas.length - 1 ? "\n" : null}</span>;
      })}
    </>
  );
}

export default function AssistenteChat() {
  const [aberto, setAberto] = useState(false);
  const [entrada, setEntrada] = useState("");
  const [msgs, setMsgs] = useState<Msg[]>([{ autor: "bot", texto: SAUDACAO, local: true }]);
  const fim = useRef<HTMLDivElement>(null);
  const campo = useRef<HTMLInputElement>(null);
  // Corpo com chaves: no Chrome atual scrollIntoView devolve uma Promise, e o React a trataria
  // como função de limpeza ao desmontar (logout/401 deixava a tela em branco).
  useEffect(() => { fim.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs]);
  useEffect(() => {
    if (!aberto) return;
    const t = setTimeout(() => campo.current?.focus(), 180);
    return () => clearTimeout(t);
  }, [aberto]);

  const perguntar = useMutation({
    mutationFn: (corpo: { pergunta: string; historico: { papel: string; texto: string }[] }) =>
      api.post<Resposta>("/assistente/perguntar", corpo),
    onSuccess: (r) => setMsgs((m) => [...m, { autor: "bot", texto: r.resposta, fontes: r.fontes }]),
    onError: (e: Error) => setMsgs((m) => [...m, { autor: "bot", texto: e.message, local: true }]),
  });

  function enviar(texto: string) {
    const t = texto.trim();
    if (!t || perguntar.isPending) return;
    // A conversa fica só no navegador; vão ao backend as últimas trocas, para continuações
    // como "e o prazo dele?"
    const historico = msgs.filter((m) => !m.local).slice(-HISTORICO_MAX)
      .map((m) => ({ papel: m.autor === "user" ? "user" : "assistant", texto: m.texto }));
    setMsgs((m) => [...m, { autor: "user", texto: t }]);
    setEntrada("");
    perguntar.mutate({ pergunta: t, historico });
  }
  const onSubmit = (e: FormEvent) => { e.preventDefault(); enviar(entrada); };

  return (
    <>
      <button className={`chat-fab${aberto ? " open" : ""}`} onClick={() => setAberto((a) => !a)}
              aria-label="Abrir assistente de dados">
        <i className="fa-solid fa-comment-dots" />
        <i className="fa-solid fa-xmark" />
      </button>
      <div className={`chat-panel${aberto ? " open" : ""}`} aria-hidden={!aberto}>
        <div className="chat-head">
          <div className="chat-head-icon"><i className="fa-solid fa-robot" /></div>
          <div className="chat-head-text">
            <h4>Assistente GEDA</h4>
            <span>Consulta ao inventário monitorado</span>
          </div>
          <button className="chat-head-close" onClick={() => setAberto(false)} aria-label="Fechar">
            <i className="fa-solid fa-xmark" />
          </button>
        </div>
        <div className="chat-scope-banner">
          <i className="fa-solid fa-circle-info" /> Responde com base na última coleta do portal
          (bases, datasets, arquivos, prazos e alertas). Não lê o conteúdo dos arquivos e não
          substitui consulta oficial ao CKAN.
        </div>
        <div className="chat-messages" aria-live="polite">
          {msgs.map((m, i) => (
            <div key={i} className={`msg ${m.autor === "user" ? "msg-user" : "msg-bot"}`}>
              {m.autor === "bot" && !m.local ? <Formatado texto={m.texto} /> : m.texto}
              {m.fontes && m.fontes.length > 0 && (
                <div className="msg-fontes">
                  Consultado: {m.fontes.map((f) => f.titulo).join(" · ")}
                </div>
              )}
            </div>
          ))}
          {perguntar.isPending && (
            <div className="msg-typing" aria-label="Consultando"><span /><span /><span /></div>
          )}
          <div ref={fim} />
        </div>
        <div className="chat-suggestions">
          {SUGESTOES.map((s) => (
            <button key={s} type="button" className="chip" onClick={() => enviar(s)}
                    disabled={perguntar.isPending}>{s}</button>
          ))}
        </div>
        <form className="chat-input-row" onSubmit={onSubmit}>
          <input ref={campo} value={entrada} onChange={(e) => setEntrada(e.target.value)}
                 maxLength={1000} placeholder="Pergunte sobre uma base, órgão, arquivo ou prazo..." />
          <button className="chat-send-btn" type="submit" aria-label="Enviar"
                  disabled={perguntar.isPending || entrada.trim().length < 2}>
            <i className="fa-solid fa-paper-plane" />
          </button>
        </form>
      </div>
    </>
  );
}
