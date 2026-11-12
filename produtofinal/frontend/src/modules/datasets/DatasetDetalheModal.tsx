import { useQuery } from "@tanstack/react-query";
import type { BaseVinculada, DatasetDetalhe, Recurso } from "./api";
import { datasetsApi } from "./api";
import { SituacaoPortalBadge, fmtDataHora } from "./formato";
import { useAuth } from "@/app/auth/AuthContext";
import { fmtData } from "@/modules/pda/formato";
import { SituacaoBadge } from "@/modules/pda/SituacaoBadge";
import { HistoricoRecente } from "@/modules/rastreabilidade/HistoricoRecente";
import { Campo, Detalhe, Grade, Resumo, Secao, Vazio } from "@/shared/ui/Detalhe";
import { Modal } from "@/shared/ui/Modal";

const PORTAL = "https://dadosabertos.go.gov.br/dataset/";

/**
 * Detalhe do dataset (showDatasetDetails() do protótipo V1), agrupado em seções: faixa-resumo,
 * Identificação, Vínculo com o PDA, Atualização, Publicação e recursos, Descrição e Histórico.
 * Dados do inventário; prazo, periodicidade e situação do PDA só aparecem quando alguma base
 * prevista está vinculada a este dataset pelo ID (nunca pelo nome).
 */
export function DatasetDetalheModal({ datasetId, onFechar }: { datasetId: number | null; onFechar: () => void }) {
  const { pode } = useAuth();
  const detalhe = useQuery({
    queryKey: ["inventario", "dataset", datasetId],
    queryFn: () => datasetsApi.detalhe(datasetId as number),
    enabled: datasetId != null,
  });
  const verPda = pode("pda.acessar");
  const bases = useQuery({
    queryKey: ["pda", "dataset", datasetId],
    queryFn: () => datasetsApi.basesPda(datasetId as number),
    enabled: datasetId != null && verPda,
  });

  if (datasetId == null) return null;
  const d = detalhe.data;
  const linkPortal = d?.id_ckan && d.situacao !== "Fora do portal" ? `${PORTAL}${encodeURIComponent(d.id_ckan)}` : null;

  return (
    <Modal aberto titulo={d?.titulo ?? "Dataset"} onFechar={onFechar}
      subtitulo={`${d?.orgao_nome ?? "—"} · Camada de monitoramento (dados refletem o CKAN, sem alterá-lo)`}
      rodape={<>
        {linkPortal && (
          <a className="btn btn-ghost btn-sm" href={linkPortal} target="_blank" rel="noopener noreferrer">
            <i className="fa-solid fa-arrow-up-right-from-square" />Abrir no portal
          </a>
        )}
        <button type="button" className="btn btn-outline btn-sm" onClick={onFechar}>Fechar</button>
      </>}>
      {detalhe.isError && (
        <div className="inline-msg err" role="alert">Não foi possível carregar o dataset: {detalhe.error.message}</div>
      )}
      {!d && !detalhe.isError && <p className="cell-muted">Carregando…</p>}
      {d && <Conteudo d={d} verPda={verPda} bases={bases.data} carregandoBases={bases.isPending && verPda}
        onFechar={onFechar} />}
    </Modal>
  );
}

function Conteudo({ d, verPda, bases, carregandoBases, onFechar }: {
  d: DatasetDetalhe; verPda: boolean; bases: BaseVinculada[] | undefined; carregandoBases: boolean;
  onFechar: () => void;
}) {
  const base = bases?.[0] ?? null; // a do PDA vigente vem primeiro
  const semBase = !carregandoBases && !base;
  const notaSemBase = "Nenhuma base do PDA vinculada a este dataset";
  const atualizacao = fmtDataHora(d.ultima_atualizacao);

  return (
    <>
      {d.situacao === "Fora do portal" && (
        <div className="inline-msg err" role="alert" style={{ marginBottom: 14 }}>
          <i className="fa-solid fa-triangle-exclamation" style={{ marginRight: 6 }} />
          Dataset não está mais visível no portal (excluído ou privado).
        </div>
      )}
      <Detalhe>
        <Resumo
          selos={<>
            <SituacaoPortalBadge situacao={d.situacao} />
            {d.tipo_base && <span className={`badge ${d.tipo_base === "Espontânea" ? "badge-amber" : "badge-blue"}`}>{d.tipo_base}</span>}
            {verPda && base && <SituacaoBadge situacao={base.situacao} />}
            {verPda && semBase && <span className="badge badge-gray">Sem base do PDA vinculada</span>}
          </>}
          fatos={[
            { valor: atualizacao, rotulo: "Última atualização real" },
            { valor: d.recursos_validos, rotulo: d.recursos_validos === 1 ? "Recurso" : "Recursos" },
            { valor: d.formatos.length ? d.formatos.join(", ") : "—", rotulo: d.formatos.length > 1 ? "Formatos" : "Formato" },
          ]} />

        <Secao titulo="Identificação">
          <Grade>
            <Campo rotulo="Nome da base">{d.titulo}</Campo>
            <Campo rotulo="Órgão responsável">{d.orgao_nome ?? "—"}</Campo>
            <Campo rotulo="ID do dataset (CKAN)" mono>{d.id_ckan ?? "—"}</Campo>
            <Campo rotulo="Licença">{d.licenca || <Vazio />}</Campo>
          </Grade>
        </Secao>

        {verPda && (
          <Secao titulo="Vínculo com o PDA">
            <Grade>
              <Campo rotulo="Prazo previsto (PDA)" nota={base ? base.plano_nome : semBase ? notaSemBase : undefined}>
                {base ? fmtData(base.prazo_abertura) : carregandoBases ? "…" : <Vazio />}
              </Campo>
              <Campo rotulo="Situação PDA" nota={semBase ? notaSemBase : undefined}>
                {base ? <SituacaoBadge situacao={base.situacao} /> : carregandoBases ? "…" : <Vazio />}
              </Campo>
            </Grade>
            {bases && bases.length > 1 && (
              <p className="help-texto" style={{ margin: "-4px 0 14px" }}>
                Também vinculado em: {bases.slice(1).map((b) => `${b.plano_nome} (${b.nome_previsto})`).join("; ")}.
              </p>
            )}
          </Secao>
        )}

        <Secao titulo="Atualização">
          <Grade>
            <Campo rotulo="Periodicidade"
              nota={base
                ? d.periodicidade_declarada && `declarada no portal: ${d.periodicidade_declarada}`
                : d.periodicidade_declarada ? "declarada no portal" : "não declarada no portal"}>
              {base ? base.periodicidade : d.periodicidade_declarada || <Vazio />}
            </Campo>
            <Campo rotulo="Situação de atualização" nota="Regra por periodicidade ainda não definida (módulo Atualizações)">
              <Vazio />
            </Campo>
            <Campo rotulo="Última atualização real" nota="Maior last_modified dos recursos">
              {atualizacao}
              {d.ultima_atualizacao && d.ultima_atualizacao_estimada && " (estimada pela criação)"}
            </Campo>
            <Campo rotulo="Última alteração de metadados" nota="Data exibida pelo CKAN; não indica atualização dos dados">
              {fmtDataHora(d.metadata_modified)}
            </Campo>
          </Grade>
        </Secao>

        <Secao titulo="Publicação e recursos">
          <Grade>
            <Campo rotulo="Data de publicação">{fmtDataHora(d.metadata_created)}</Campo>
            <Campo rotulo="Formato">{d.formatos.length ? d.formatos.join(", ") : "—"}</Campo>
            <Campo rotulo="Recursos" nota="Dicionário de dados não entra na contagem">{d.recursos_validos}</Campo>
          </Grade>
          <TabelaRecursos recursos={d.recursos} removidos={d.recursos_removidos} />
        </Secao>

        <Secao titulo="Descrição">
          <p className="det-valor leve" style={{ lineHeight: 1.5, marginBottom: 14 }}>{d.descricao || "—"}</p>
        </Secao>

        <Secao titulo="Histórico recente">
          <HistoricoRecente titulo="Histórico recente" dataset={d.id_ckan} onSair={onFechar} />
        </Secao>
      </Detalhe>
    </>
  );
}

function TabelaRecursos({ recursos, removidos }: { recursos: Recurso[]; removidos: number }) {
  return (
    <div style={{ marginBottom: 14 }}>
      {recursos.length === 0 ? (
        <p className="cell-muted">Nenhum recurso publicado.</p>
      ) : (
        <div className="table-scroll">
          <table>
            <thead><tr><th>Recurso</th><th>Formato</th><th>Última atualização</th><th /></tr></thead>
            <tbody>
              {recursos.map((r) => (
                <tr key={r.id}>
                  <td>
                    {r.nome || <span className="cell-muted">(sem nome)</span>}
                    {r.eh_dicionario_dados && <>{" "}<span className="badge badge-gray">dicionário de dados</span></>}
                  </td>
                  <td>{r.formato || "—"}</td>
                  <td className="cell-muted">
                    {r.last_modified ? fmtDataHora(r.last_modified)
                      : r.created ? `${fmtDataHora(r.created)} (est.)` : "—"}
                  </td>
                  <td>
                    {r.url && (
                      <a href={r.url} target="_blank" rel="noopener noreferrer" title="Abrir o recurso">
                        <i className="fa-solid fa-arrow-up-right-from-square" />
                      </a>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {removidos > 0 && (
        <p className="help-texto" style={{ marginTop: 6 }}>
          {removidos} recurso(s) que já estiveram neste dataset saíram do portal e não contam.
        </p>
      )}
    </div>
  );
}
