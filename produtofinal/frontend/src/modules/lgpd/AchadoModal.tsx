import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import type { StatusAchado } from "./api";
import { ROTULO_STATUS, lgpdApi } from "./api";
import { PrioridadeTag, fmtMomento } from "./formato";
import { useAuth } from "@/app/auth/AuthContext";
import { Campo, Detalhe, Grade, Resumo, Secao } from "@/shared/ui/Detalhe";
import { Modal } from "@/shared/ui/Modal";
import { useToast } from "@/shared/ui/Toast";

/**
 * Detalhe do achado — referência: #modal-lgpd do Protótipo V1, com a decisão gravada no backend.
 * Agrupado em três perguntas: onde está, por que foi sinalizado e o que decidir.
 */
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
        <Detalhe>
          <Resumo
            selos={<>
              <PrioridadeTag prioridade={a.prioridade} />
              <span className="badge badge-gray">{a.status === "revisar" ? "Aguardando revisão humana" : ROTULO_STATUS[a.status]}</span>
              <span className="badge badge-gray">{a.metodo === "ia" ? "Modelo local (IA)" : "Regra (padrão e validação)"}</span>
            </>}
            fatos={[
              { valor: a.tipo_rotulo, rotulo: "Tipo identificado" },
              { valor: `${a.confianca}%`, rotulo: "Confiança" },
              { valor: a.ocorrencias, rotulo: "Células com esse tipo na coluna" },
            ]} />

          <Secao titulo="Onde está">
            <Grade>
              <Campo rotulo="Dataset">{a.dataset_titulo}</Campo>
              <Campo rotulo="Órgão">{a.orgao_nome ?? "—"}</Campo>
              <Campo rotulo="Recurso" mono>
                {a.recurso_url
                  ? <a href={a.recurso_url} target="_blank" rel="noreferrer">{a.recurso_nome ?? a.recurso_id}</a>
                  : (a.recurso_nome ?? a.recurso_id)}
              </Campo>
              <Campo rotulo="Coluna" mono>{a.coluna}</Campo>
              <Campo rotulo="Linha (primeira ocorrência)">{a.linha ?? "—"}</Campo>
              <Campo rotulo="Valor" leve>
                Não armazenado (política de não retenção). Confira no arquivo do recurso, coluna
                “{a.coluna}”, linha {a.linha ?? "—"}.
              </Campo>
            </Grade>
          </Secao>

          <Secao titulo="Por que foi sinalizado">
            <div className="det-campo" style={{ marginBottom: 12 }}>
              <label>Confiança da detecção</label>
              <div className="det-valor">{a.confianca}%</div>
              <div className="confidence-bar"><div className="confidence-fill" style={{ width: `${a.confianca}%` }} /></div>
            </div>
            {a.explicacao && (
              <ul className="lgpd-explicacao" style={{ marginBottom: 14 }}>
                {a.explicacao.split("; ").map((p, i) => <li key={i}>{p}</li>)}
              </ul>
            )}
          </Secao>

          <Secao titulo="Decisão">
            <div className="det-campo" style={{ marginBottom: 14 }}>
              <label>Status</label>
              <div className="det-valor">{a.status === "revisar" ? "Aguardando revisão humana" : ROTULO_STATUS[a.status]}</div>
            </div>
            {triar && (
              <div className="form-field" style={{ marginBottom: 14 }}>
                <label htmlFor="lgpd-justificativa">Justificativa da decisão (opcional)</label>
                <textarea id="lgpd-justificativa" className="text-input" maxLength={1000} value={justificativa}
                          placeholder="Ex.: coluna guarda código da escola, não telefone"
                          onChange={(e) => setJustificativa(e.target.value)} />
              </div>
            )}
            {a.decisoes.length > 0 && (
              <div className="det-campo" style={{ marginBottom: 14 }}>
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
            <div className="alert-callout" style={{ marginBottom: 14 }}>
              <i className="fa-solid fa-circle-info" />
              <div>Esta é uma sinalização automática indicativa. Nenhuma ação de bloqueio, ocultação ou
                anonimização é realizada pelo sistema — a decisão cabe à equipe responsável, mediante
                análise humana.</div>
            </div>
          </Secao>
        </Detalhe>
      )}
    </Modal>
  );
}
