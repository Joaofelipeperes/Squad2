import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import type { StatusAchado } from "./api";
import { ROTULO_STATUS, lgpdApi } from "./api";
import { PrioridadeTag, fmtMomento } from "./formato";
import { useAuth } from "@/app/auth/AuthContext";
import { Modal } from "@/shared/ui/Modal";
import { useToast } from "@/shared/ui/Toast";

/** Detalhe do achado — referência: #modal-lgpd do Protótipo V1, com a decisão gravada no backend. */
export function AchadoModal({ id, onFechar, onDecidido, onAnonimizar }: {
  id: number | null; onFechar: () => void; onDecidido: () => void;
  onAnonimizar: (recursoId: number) => void;
}) {
  const { pode } = useAuth();
  const toast = useToast();
  const qc = useQueryClient();
  const [justificativa, setJustificativa] = useState("");
  useEffect(() => setJustificativa(""), [id]);

  const detalhe = useQuery({
    queryKey: ["lgpd", "achado", id],
    queryFn: () => lgpdApi.achado(id!),
    enabled: id !== null,
  });
  const decidir = useMutation({
    mutationFn: (d: StatusAchado) => lgpdApi.decidir(id!, d, justificativa.trim() || null),
    onSuccess: (a) => {
      qc.setQueryData(["lgpd", "achado", a.id], a);  // reabrir mostra o status novo
      onDecidido();
      onFechar();
      toast(a.status === "confirmado" ? "Alerta marcado como confirmado. Encaminhado para tratativa."
        : a.status === "falso_positivo" ? "Alerta marcado como falso positivo."
        : `Alerta marcado como “${ROTULO_STATUS[a.status]}”.`);
    },
    onError: (e: Error) => toast(e.message, true),
  });

  const a = detalhe.data;
  const triar = pode("lgpd.triar");
  const botao = (d: StatusAchado, classe: string, icone: string, rotulo: string) => (
    a && a.status !== d && (
      <button className={`btn ${classe} btn-sm`} disabled={decidir.isPending} onClick={() => decidir.mutate(d)}>
        <i className={`fa-solid ${icone}`} />{rotulo}
      </button>
    )
  );

  return (
    <Modal aberto={id !== null} onFechar={onFechar} titulo="Possível dado pessoal identificado"
      subtitulo="Sinalização automática — requer revisão humana"
      rodape={<>
        {triar && botao("falso_positivo", "btn-danger-line", "fa-ban", "Marcar como falso positivo")}
        {triar && botao("confirmado", "btn-success-line", "fa-check", "Marcar como confirmado")}
        {triar && a?.status === "confirmado" && botao("tratado", "btn-outline", "fa-circle-check", "Marcar como tratado")}
        {triar && a && a.status !== "revisar" && botao("revisar", "btn-ghost", "fa-rotate-left", "Voltar para revisão")}
        {pode("lgpd.aprovar_correcao") && a?.status === "confirmado" && (
          <button className="btn btn-primary btn-sm" onClick={() => onAnonimizar(a.recurso_id)}>
            <i className="fa-solid fa-user-secret" />Anonimizar recurso…
          </button>
        )}
        <button className="btn btn-outline btn-sm" onClick={onFechar}>Fechar</button>
      </>}>
      {detalhe.isError ? (
        <div className="inline-msg err" role="alert">{detalhe.error.message}</div>
      ) : !a ? (
        <p className="cell-muted">Carregando…</p>
      ) : (
        <>
          <div className="def-grid">
            <Item rotulo="Dataset" valor={a.dataset_titulo} />
            <Item rotulo="Órgão" valor={a.orgao_nome ?? "—"} />
            <div className="def-item"><label>Recurso</label><div className="val mono">
              {a.recurso_url
                ? <a href={a.recurso_url} target="_blank" rel="noreferrer">{a.recurso_nome ?? a.recurso_id}</a>
                : (a.recurso_nome ?? a.recurso_id)}
            </div></div>
            <Item rotulo="Coluna" valor={a.coluna} mono />
            <Item rotulo="Linha (primeira ocorrência)" valor={a.linha ?? "—"} />
            <Item rotulo="Células com esse tipo na coluna" valor={a.ocorrencias} />
            <Item rotulo="Tipo identificado" valor={a.tipo_rotulo} />
            <Item rotulo="Detectado por" valor={a.metodo === "ia" ? "Modelo local (IA)" : "Regra (padrão e validação)"} />
            <div className="def-item"><label>Prioridade</label><div className="val"><PrioridadeTag prioridade={a.prioridade} /></div></div>
            <Item rotulo="Status" valor={a.status === "revisar" ? "Aguardando revisão humana" : ROTULO_STATUS[a.status]} />
            <div className="def-item" style={{ gridColumn: "1 / -1" }}>
              <label>Valor</label>
              <div className="val cell-muted">
                Não armazenado (política de não retenção). Confira no arquivo do recurso, coluna
                “{a.coluna}”, linha {a.linha ?? "—"}.
              </div>
            </div>
          </div>
          <div className="def-item" style={{ marginTop: 16 }}>
            <label>Confiança da detecção</label>
            <div className="val">{a.confianca}%</div>
            <div className="confidence-bar"><div className="confidence-fill" style={{ width: `${a.confianca}%` }} /></div>
          </div>
          {a.explicacao && (
            <div className="def-item" style={{ marginTop: 16 }}>
              <label>Por que foi sinalizado</label>
              <ul className="lgpd-explicacao">
                {a.explicacao.split("; ").map((p, i) => <li key={i}>{p}</li>)}
              </ul>
            </div>
          )}
          {triar && (
            <div className="form-field" style={{ marginTop: 16 }}>
              <label htmlFor="lgpd-justificativa">Justificativa da decisão (opcional)</label>
              <textarea id="lgpd-justificativa" className="text-input" maxLength={1000} value={justificativa}
                        placeholder="Ex.: coluna guarda código da escola, não telefone"
                        onChange={(e) => setJustificativa(e.target.value)} />
            </div>
          )}
          {a.decisoes.length > 0 && (
            <div className="def-item" style={{ marginTop: 16 }}>
              <label>Histórico de decisões</label>
              <ul className="lgpd-explicacao">
                {a.decisoes.map((d, i) => (
                  <li key={i}>
                    <b>{ROTULO_STATUS[d.decisao]}</b> · {d.usuario} · {fmtMomento(d.momento)}
                    {d.justificativa && <> — {d.justificativa}</>}
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div className="alert-callout" style={{ marginTop: 16, marginBottom: 0 }}>
            <i className="fa-solid fa-circle-info" />
            <div>Esta é uma sinalização automática indicativa. Nenhuma ação de bloqueio, ocultação ou
              anonimização é realizada pelo sistema — a decisão cabe à equipe responsável, mediante
              análise humana.</div>
          </div>
        </>
      )}
    </Modal>
  );
}

function Item({ rotulo, valor, mono }: { rotulo: string; valor: string | number; mono?: boolean }) {
  return <div className="def-item"><label>{rotulo}</label><div className={mono ? "val mono" : "val"}>{valor}</div></div>;
}
