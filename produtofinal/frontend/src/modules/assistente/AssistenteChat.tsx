import { useMutation } from "@tanstack/react-query";
import type { FormEvent } from "react";
import { useEffect, useRef, useState } from "react";
import { api } from "@/shared/api/client";

interface Msg { autor: "user" | "bot"; texto: string }

const SUGESTOES = ["Quantos datasets estão no portal?", "Como está a Secretaria da Saúde?"];

export default function AssistenteChat() {
  const [aberto, setAberto] = useState(false);
  const [entrada, setEntrada] = useState("");
  const [msgs, setMsgs] = useState<Msg[]>([
    { autor: "bot", texto: "Olá! Pergunte sobre um órgão, uma base ou um prazo do PDA." },
  ]);
  const fim = useRef<HTMLDivElement>(null);
  useEffect(() => fim.current?.scrollIntoView({ behavior: "smooth" }), [msgs]);

  const perguntar = useMutation({
    mutationFn: (pergunta: string) => api.post<{ resposta: string }>("/assistente/perguntar", { pergunta }),
    onSuccess: (r) => setMsgs((m) => [...m, { autor: "bot", texto: r.resposta }]),
    onError: (e: Error) => setMsgs((m) => [...m, { autor: "bot", texto: e.message }]),
  });

  function enviar(texto: string) {
    const t = texto.trim();
    if (!t || perguntar.isPending) return;
    setMsgs((m) => [...m, { autor: "user", texto: t }]);
    setEntrada("");
    perguntar.mutate(t);
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
          <i className="fa-solid fa-circle-info" /> Responde com base na última coleta do portal.
          Não substitui consulta oficial ao CKAN.
        </div>
        <div className="chat-messages">
          {msgs.map((m, i) => (
            <div key={i} className={`msg ${m.autor === "user" ? "msg-user" : "msg-bot"}`}>{m.texto}</div>
          ))}
          {perguntar.isPending && <div className="msg msg-bot msg-typing">Consultando…</div>}
          <div ref={fim} />
        </div>
        <div className="chat-suggestions">
          {SUGESTOES.map((s) => <button key={s} className="chip" onClick={() => enviar(s)}>{s}</button>)}
        </div>
        <form className="chat-input-row" onSubmit={onSubmit}>
          <input value={entrada} onChange={(e) => setEntrada(e.target.value)}
                 placeholder="Pergunte sobre uma base, órgão ou prazo..." />
          <button className="chat-send-btn" type="submit" aria-label="Enviar">
            <i className="fa-solid fa-paper-plane" />
          </button>
        </form>
      </div>
    </>
  );
}
