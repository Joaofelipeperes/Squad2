import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import type { Organizacao } from "./api";
import { NAO_CONFIRMADO } from "./OrganizacoesPage";
import { Modal } from "@/shared/ui/Modal";
import { useAuth } from "@/app/auth/AuthContext";

function Stat({ n, rotulo, nota }: { n: ReactNode; rotulo: string; nota?: string }) {
  return (
    <div className="stat-mini" title={nota}>
      <div className="n">{n}</div>
      <div className="l">{rotulo}</div>
      {nota && <div className="l" style={{ fontStyle: "italic" }}>{nota}</div>}
    </div>
  );
}

const PENDENTE = <span style={{ color: "var(--gray-500)" }}>—</span>;

/** Resumo de governança do órgão (showOrganizationDetails() do protótipo V1). */
export function OrganizacaoDetalheModal({ org, formatosAbertos, onFechar }: {
  org: Organizacao | null; formatosAbertos: string[]; onFechar: () => void;
}) {
  const navigate = useNavigate();
  const { pode } = useAuth();
  if (!org) return null;
  const o = org;
  const vinculado = o.bases_vinculadas > 0;
  const semConfirmacao = o.bases_vinculadas < o.bases_previstas;
  const fechados = Object.entries(o.formatos_fechados);

  function verNoPda() {
    onFechar();
    navigate(`/pda?orgao=${encodeURIComponent(o.chave)}`);
  }

  return (
    <Modal aberto titulo={o.nome}
      subtitulo={`${o.siglas.length ? `${o.siglas.join(", ")} · ` : ""}Resumo de governança de dados abertos`}
      onFechar={onFechar}
      rodape={<>
        <button type="button" className="btn btn-outline btn-sm" onClick={onFechar}>Fechar</button>
        {pode("pda.acessar") && o.bases_previstas > 0 && (
          <button type="button" className="btn btn-primary btn-sm" onClick={verNoPda}>Ver bases no PDA</button>
        )}
      </>}>
      <div className="stat-mini-grid">
        <Stat n={o.bases_previstas} rotulo="Bases previstas" />
        <Stat n={vinculado ? o.bases_publicadas : PENDENTE} rotulo="Bases publicadas"
          nota={vinculado ? `${o.bases_vinculadas} base(s) vinculada(s) ao portal` : "aguardando vínculo"} />
        <Stat n={vinculado ? o.bases_previstas - o.bases_publicadas : PENDENTE} rotulo="Bases não publicadas"
          nota={vinculado ? undefined : "aguardando vínculo"} />
        <Stat n={PENDENTE} rotulo="Atualizações atrasadas" nota="regra de atualização a definir" />
        <Stat n={o.recursos_formato_fechado} rotulo="Recursos sem formato aberto"
          nota={`de ${o.recursos_validos} recurso(s) em ${o.datasets_no_portal} dataset(s)`} />
        <Stat n={PENDENTE} rotulo="Possíveis dados pessoais" nota="módulo de dados pessoais a definir" />
      </div>
      <div className="def-grid" style={{ marginTop: 14 }}>
        <div className="def-item">
          <label>Bases em atraso</label>
          <div className="val">{o.bases_em_atraso ?? PENDENTE}</div>
          {semConfirmacao && (
            <p className="help-texto" style={{ marginTop: 4 }}>
              {o.bases_em_atraso == null ? "aguardando vínculo" : `entre as ${o.bases_vinculadas} vinculada(s); ${NAO_CONFIRMADO.toLowerCase()} nas demais`}
            </p>
          )}
        </div>
        <div className="def-item">
          <label>Bases próximas do prazo</label>
          <div className="val">{o.bases_proximas_do_prazo}</div>
        </div>
      </div>
      {fechados.length > 0 && (
        <div className="def-item full" style={{ marginTop: 14 }}>
          <label>Recursos fora dos formatos abertos</label>
          <div className="val" style={{ fontWeight: 400 }}>
            {fechados.map(([f, n]) => (
              <span key={f || "-"} className="badge badge-gray" style={{ marginRight: 6 }}>
                {f || "sem formato"}: {n}
              </span>
            ))}
          </div>
          <p className="help-texto" style={{ marginTop: 6 }}>
            Formatos abertos (parâmetro da GEDA): {formatosAbertos.join(", ") || "—"}. Dicionário de dados não entra.
          </p>
        </div>
      )}
      <div className="mini-history">
        <h4>Últimas alterações</h4>
        <div className="hist-row"><span>Disponível quando a rastreabilidade for implementada.</span></div>
      </div>
    </Modal>
  );
}
