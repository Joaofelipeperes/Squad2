import type { ReactNode } from "react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import type { CriterioAtencao, Organizacao } from "./api";
import { IndiceAtencao, NAO_CONFIRMADO, explicarIndice } from "./OrganizacoesPage";
import { GerarRelatorioOrgaoModal } from "@/modules/relatorios/RelatorioOrgao";
import { HistoricoRecente } from "@/modules/rastreabilidade/HistoricoRecente";
import { Detalhe, Secao } from "@/shared/ui/Detalhe";
import { Modal } from "@/shared/ui/Modal";
import { useAuth } from "@/app/auth/AuthContext";

function Kpi({ n, rotulo, nota, alerta = false }: { n: ReactNode; rotulo: string; nota?: ReactNode; alerta?: boolean }) {
  return (
    <div className={alerta ? "det-kpi alerta" : "det-kpi"}>
      <div className="n">{n}</div>
      <div className="l">{rotulo}</div>
      {nota && <div className="l" style={{ fontStyle: "italic" }}>{nota}</div>}
    </div>
  );
}

const PENDENTE = <span style={{ color: "var(--gray-500)" }}>—</span>;

/**
 * Resumo de governança do órgão (showOrganizationDetails() do protótipo V1), agrupado em seções:
 * índice de atenção no topo e depois Publicação no PDA, Atualização, Formatos, Dados pessoais
 * (LGPD) e Últimas alterações.
 */
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
      <Detalhe>
        <div className="det-indice">
          <div>
            <div className="rotulo">Índice de atenção</div>
            <div style={{ marginTop: 4 }}><IndiceAtencao o={o} criterio={criterio} /></div>
          </div>
          <p className="explicacao">
            {o.indice_atencao
              ? explicarIndice(o, criterio)
              : "Sem risco LGPD (nenhum recurso varrido) e sem atualização avaliada (nenhuma base vinculada com prazo)."}
          </p>
        </div>

        <Secao titulo="Publicação no PDA">
          <div className="det-kpis">
            <Kpi n={o.bases_previstas} rotulo="Bases previstas" />
            <Kpi n={vinculado ? o.bases_publicadas : PENDENTE} rotulo="Bases publicadas"
              nota={vinculado ? `${o.bases_vinculadas} base(s) vinculada(s) ao portal` : "aguardando vínculo"} />
            <Kpi n={vinculado ? o.bases_previstas - o.bases_publicadas : PENDENTE} rotulo="Bases não publicadas"
              nota={vinculado ? undefined : "aguardando vínculo"} />
            <Kpi n={o.bases_em_atraso ?? PENDENTE} rotulo="Bases em atraso" alerta={!!o.bases_em_atraso}
              nota={o.bases_em_atraso == null ? "aguardando vínculo"
                : semConfirmacao ? `entre as ${o.bases_vinculadas} vinculada(s); ${NAO_CONFIRMADO.toLowerCase()} nas demais` : undefined} />
            <Kpi n={o.bases_proximas_do_prazo} rotulo="Bases próximas do prazo" />
          </div>
        </Secao>

        <Secao titulo="Atualização">
          <div className="det-kpis">
            <Kpi n={o.atualizacoes_atrasadas ?? PENDENTE} rotulo="Atualizações atrasadas" alerta={!!o.atualizacoes_atrasadas}
              nota={o.atualizacoes_atrasadas != null
                ? `de ${o.atualizacoes_avaliadas} base(s) com prazo (${o.atualizacao_pct}% em dia)`
                : vinculado ? "sem base com prazo definido" : "aguardando vínculo"} />
          </div>
        </Secao>

        <Secao titulo="Formatos">
          <div className="det-kpis">
            <Kpi n={o.recursos_formato_fechado} rotulo="Recursos sem formato aberto" alerta={o.recursos_formato_fechado > 0}
              nota={`de ${o.recursos_validos} recurso(s) em ${o.datasets_no_portal} dataset(s)`} />
          </div>
          {fechados.length > 0 && (
            <div style={{ marginBottom: 14 }}>
              <div className="det-campo"><label>Recursos fora dos formatos abertos</label></div>
              <div>
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
        </Secao>

        <Secao titulo="Dados pessoais (LGPD)">
          <div className="det-kpis">
            <Kpi n={o.riscos_lgpd ?? PENDENTE} rotulo="Recursos com possíveis dados pessoais" alerta={!!o.riscos_lgpd}
              nota={!lgpdVisivel ? "sem acesso ao módulo de dados pessoais"
                : o.riscos_lgpd == null ? "nenhum recurso varrido"
                : `de ${o.lgpd_recursos_analisados} varrido(s): ${o.lgpd_aguardando_revisao} achado(s) a revisar, ${o.lgpd_confirmados} confirmado(s)`} />
          </div>
        </Secao>

        <Secao titulo="Últimas alterações">
          <HistoricoRecente titulo="Últimas alterações" orgao={o.organizacao_id} onSair={onFechar} />
        </Secao>
      </Detalhe>
      {relatorio && o.organizacao_id != null && (
        <GerarRelatorioOrgaoModal orgao={o.organizacao_id} nome={o.nome}
          onFechar={() => setRelatorio(false)} />
      )}
    </Modal>
  );
}
