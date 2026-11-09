import type { ReactNode } from "react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import type { CriterioAtencao, Organizacao } from "./api";
import { IndiceAtencao, NAO_CONFIRMADO, explicarIndice } from "./OrganizacoesPage";
import { RelatorioOrgaoModal } from "@/modules/relatorios/RelatorioOrgao";
import { HistoricoRecente } from "@/modules/rastreabilidade/HistoricoRecente";
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
export function OrganizacaoDetalheModal({ org, formatosAbertos, lgpdVisivel, criterio, onFechar }: {
  org: Organizacao | null; formatosAbertos: string[]; lgpdVisivel: boolean; criterio: CriterioAtencao;
  onFechar: () => void;
}) {
  const navigate = useNavigate();
  const { pode } = useAuth();
  const [relatorio, setRelatorio] = useState(false);
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
        {/* Relatório só com os dados deste órgão (mesmo gerador da tela Relatórios) */}
        {pode("relatorios.acessar") && o.organizacao_id != null && (
          <button type="button" className="btn btn-outline btn-sm" onClick={() => setRelatorio(true)}>
            <i className="fa-solid fa-file-lines" />Gerar relatório
          </button>
        )}
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
        <Stat n={o.atualizacoes_atrasadas ?? PENDENTE} rotulo="Atualizações atrasadas"
          nota={o.atualizacoes_atrasadas != null
            ? `de ${o.atualizacoes_avaliadas} base(s) com prazo (${o.atualizacao_pct}% em dia)`
            : vinculado ? "sem base com prazo definido" : "aguardando vínculo"} />
        <Stat n={o.recursos_formato_fechado} rotulo="Recursos sem formato aberto"
          nota={`de ${o.recursos_validos} recurso(s) em ${o.datasets_no_portal} dataset(s)`} />
        <Stat n={o.riscos_lgpd ?? PENDENTE} rotulo="Recursos com possíveis dados pessoais"
          nota={!lgpdVisivel ? "sem acesso ao módulo de dados pessoais"
            : o.riscos_lgpd == null ? "nenhum recurso varrido"
            : `de ${o.lgpd_recursos_analisados} varrido(s): ${o.lgpd_aguardando_revisao} achado(s) a revisar, ${o.lgpd_confirmados} confirmado(s)`} />
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
        <div className="def-item full">
          <label>Índice de atenção</label>
          <div className="val"><IndiceAtencao o={o} criterio={criterio} /></div>
          <p className="help-texto" style={{ marginTop: 4 }}>
            {o.indice_atencao
              ? explicarIndice(o, criterio)
              : "Sem risco LGPD (nenhum recurso varrido) e sem atualização avaliada (nenhuma base vinculada com prazo)."}
          </p>
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
      <HistoricoRecente titulo="Últimas alterações" orgao={o.organizacao_id} onSair={onFechar} />
      {relatorio && o.organizacao_id != null && (
        <RelatorioOrgaoModal orgao={o.organizacao_id} onFechar={() => setRelatorio(false)} />
      )}
    </Modal>
  );
}
