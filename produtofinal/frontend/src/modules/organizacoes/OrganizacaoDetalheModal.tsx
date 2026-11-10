import type { ReactNode } from "react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import type { CriterioAtencao, Organizacao } from "./api";
import { CLASSE_ATENCAO, IndiceAtencao, NAO_CONFIRMADO, explicarIndice } from "./OrganizacoesPage";
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
 * Resumo de governança do órgão (showOrganizationDetails() do protótipo V1), agrupado em seções
 * como no protótipo `prototipos/detalhes-agrupados.html`: índice de atenção em destaque no topo e
 * depois Publicação no PDA, Atualização, Formatos, Dados pessoais (LGPD) e Últimas alterações.
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
  const faixa = o.indice_atencao;
  const valor = o.indice_atencao_valor;
  const classeValor = faixa === "Alto" ? "alto" : faixa === "Médio" ? "medio" : "baixo";

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
          {faixa && valor != null ? (
            <>
              <div className={`valor ${classeValor}`} aria-label={`Índice ${valor}`}>{valor}</div>
              <div className="centro">
                <div className="rotulo">Índice de atenção</div>
                <div style={{ marginTop: 4 }}>
                  <span className={`badge ${CLASSE_ATENCAO[faixa]}`}>Atenção {faixa.toLowerCase()}</span>
                </div>
                <div className="det-barra" aria-hidden="true"><i style={{ width: `${Math.min(100, valor)}%` }} /></div>
              </div>
              <p className="explicacao">{explicarIndice(o, criterio)}</p>
            </>
          ) : (
            <>
              <div className="centro">
                <div className="rotulo">Índice de atenção</div>
                <div style={{ marginTop: 4 }}><IndiceAtencao o={o} criterio={criterio} /></div>
              </div>
              <p className="explicacao">
                Sem risco LGPD (nenhum recurso varrido) e sem atualização avaliada (nenhuma base vinculada com prazo).
              </p>
            </>
          )}
        </div>

        <Secao titulo="Publicação no PDA">
          <div className="det-kpis">
            <Kpi n={o.bases_previstas} rotulo="Bases previstas" />
            <Kpi n={vinculado ? o.bases_publicadas : PENDENTE} rotulo="Bases publicadas"
              nota={vinculado ? undefined : "aguardando vínculo"} />
            <Kpi n={vinculado ? o.bases_previstas - o.bases_publicadas : PENDENTE} rotulo="Bases não publicadas"
              nota={vinculado ? undefined : "aguardando vínculo"} />
            <Kpi n={o.bases_em_atraso ?? PENDENTE} rotulo="Bases em atraso" alerta={!!o.bases_em_atraso}
              nota={o.bases_em_atraso == null ? "aguardando vínculo"
                : semConfirmacao ? `entre as ${o.bases_vinculadas} vinculada(s); ${NAO_CONFIRMADO.toLowerCase()} nas demais` : undefined} />
            <Kpi n={o.bases_proximas_do_prazo} rotulo="Próximas do prazo" />
            <Kpi n={o.bases_vinculadas} rotulo="Bases vinculadas ao portal" />
          </div>
        </Secao>

        <Secao titulo="Atualização"
          nota={vinculado ? `de ${o.atualizacoes_avaliadas} base(s) com prazo` : "aguardando vínculo"}>
          <div className="det-kpis">
            <Kpi n={o.atualizacoes_atrasadas ?? PENDENTE} rotulo="Atualizações atrasadas" alerta={!!o.atualizacoes_atrasadas}
              nota={o.atualizacoes_atrasadas == null && vinculado ? "sem base com prazo definido" : undefined} />
            <Kpi n={o.atualizacao_pct != null ? `${o.atualizacao_pct}%` : PENDENTE} rotulo="em dia" />
            <Kpi n={o.atualizacoes_avaliadas} rotulo="Bases com prazo definido" />
          </div>
        </Secao>

        <Secao titulo="Formatos">
          <div className="det-kpis">
            <Kpi n={o.recursos_formato_fechado} rotulo="Recursos sem formato aberto" alerta={o.recursos_formato_fechado > 0} />
            <Kpi n={o.recursos_validos} rotulo="Recursos válidos" />
            <Kpi n={o.datasets_no_portal} rotulo="Datasets no portal" />
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

        <Secao titulo="Dados pessoais (LGPD)"
          nota={!lgpdVisivel ? "sem acesso ao módulo de dados pessoais"
            : o.riscos_lgpd == null ? "nenhum recurso varrido"
            : `de ${o.lgpd_recursos_analisados} recurso(s) varrido(s)`}>
          <div className="det-kpis">
            <Kpi n={o.riscos_lgpd ?? PENDENTE} rotulo="Recursos com possíveis dados pessoais" alerta={!!o.riscos_lgpd} />
            <Kpi n={lgpdVisivel && o.riscos_lgpd != null ? o.lgpd_aguardando_revisao : PENDENTE} rotulo="Achados a revisar" />
            <Kpi n={lgpdVisivel && o.riscos_lgpd != null ? o.lgpd_confirmados : PENDENTE} rotulo="Confirmados" />
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
