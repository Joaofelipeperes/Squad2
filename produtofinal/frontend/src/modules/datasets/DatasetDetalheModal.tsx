import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import type { BaseVinculada, DatasetDetalhe, Recurso } from "./api";
import { datasetsApi } from "./api";
import { SituacaoPortalBadge, fmtDataHora } from "./formato";
import { useAuth } from "@/app/auth/AuthContext";
import { fmtData } from "@/modules/pda/formato";
import { SituacaoBadge } from "@/modules/pda/SituacaoBadge";
import { Modal } from "@/shared/ui/Modal";

const PORTAL = "https://dadosabertos.go.gov.br/dataset/";

function Item({ rotulo, children, mono = false }: { rotulo: string; children: ReactNode; mono?: boolean }) {
  return (
    <div className="def-item">
      <label>{rotulo}</label>
      <div className={mono ? "val mono" : "val"}>{children}</div>
    </div>
  );
}

/** Nota secundária dentro de um .val (texto cinza, peso normal). */
const Nota = ({ children }: { children: ReactNode }) => (
  <div className="cell-muted" style={{ fontWeight: 400 }}>{children}</div>
);

/**
 * Detalhe do dataset (showDatasetDetails() do protótipo V1). Dados do inventário; prazo,
 * periodicidade e situação do PDA só aparecem quando alguma base prevista está vinculada a este
 * dataset pelo ID (nunca pelo nome).
 */
export function DatasetDetalheModal({ ckanId, onFechar }: { ckanId: string | null; onFechar: () => void }) {
  const { pode } = useAuth();
  const detalhe = useQuery({
    queryKey: ["inventario", "dataset", ckanId],
    queryFn: () => datasetsApi.detalhe(ckanId as string),
    enabled: ckanId != null,
  });
  const verPda = pode("pda.acessar");
  const bases = useQuery({
    queryKey: ["pda", "dataset", ckanId],
    queryFn: () => datasetsApi.basesPda(ckanId as string),
    enabled: ckanId != null && verPda,
  });

  if (ckanId == null) return null;
  const d = detalhe.data;
  const linkPortal = d && d.situacao !== "Fora do portal" ? `${PORTAL}${encodeURIComponent(d.ckan_id)}` : null;

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
      {d && <Conteudo d={d} verPda={verPda} bases={bases.data} carregandoBases={bases.isPending && verPda} />}
    </Modal>
  );
}

function Conteudo({ d, verPda, bases, carregandoBases }: {
  d: DatasetDetalhe; verPda: boolean; bases: BaseVinculada[] | undefined; carregandoBases: boolean;
}) {
  const base = bases?.[0] ?? null; // a do PDA vigente vem primeiro
  const semBase = !carregandoBases && !base;
  const notaSemBase = <Nota>Nenhuma base do PDA vinculada a este dataset</Nota>;

  return (
    <>
      {d.situacao === "Fora do portal" && (
        <div className="inline-msg err" role="alert" style={{ marginBottom: 14 }}>
          <i className="fa-solid fa-triangle-exclamation" style={{ marginRight: 6 }} />
          Dataset não está mais visível no portal (excluído ou privado).
        </div>
      )}
      <div className="def-grid">
        <Item rotulo="Nome da base">{d.titulo}</Item>
        <Item rotulo="Órgão responsável">{d.orgao_nome ?? "—"}</Item>
        <Item rotulo="ID do dataset (CKAN)" mono>
          <span style={{ wordBreak: "break-all" }}>{d.ckan_id}</span>
        </Item>
        <Item rotulo="Name no portal" mono>
          <span style={{ wordBreak: "break-all" }}>{d.name}</span>
        </Item>
        {verPda && (
          <Item rotulo="Prazo previsto (PDA)">
            {base ? <>{fmtData(base.prazo_abertura)}<Nota>{base.plano_nome}</Nota></> : carregandoBases ? "…" : <>—{notaSemBase}</>}
          </Item>
        )}
        <Item rotulo="Data de publicação">{fmtDataHora(d.metadata_created)}</Item>
        <Item rotulo="Periodicidade">
          {base ? base.periodicidade : d.periodicidade_declarada || "—"}
          {base
            ? d.periodicidade_declarada && <Nota>declarada no portal: {d.periodicidade_declarada}</Nota>
            : <Nota>{d.periodicidade_declarada ? "declarada no portal" : "não declarada no portal"}</Nota>}
        </Item>
        <Item rotulo="Última atualização real">
          {fmtDataHora(d.ultima_atualizacao)}
          {d.ultima_atualizacao && d.ultima_atualizacao_estimada && " (estimada pela criação)"}
          <Nota>Maior last_modified dos recursos</Nota>
        </Item>
        <Item rotulo="Última alteração de metadados">
          {fmtDataHora(d.metadata_modified)}
          <Nota>Data exibida pelo CKAN; não indica atualização dos dados</Nota>
        </Item>
        <Item rotulo="Formato">{d.formatos.length ? d.formatos.join(", ") : "—"}</Item>
        <Item rotulo="Recursos">
          {d.recursos_validos}
          <Nota>Dicionário de dados não entra na contagem</Nota>
        </Item>
        <Item rotulo="Status no portal"><SituacaoPortalBadge situacao={d.situacao} /></Item>
        {verPda && (
          <Item rotulo="Situação PDA">
            {base ? <SituacaoBadge situacao={base.situacao} /> : carregandoBases ? "…" : <>—{semBase && notaSemBase}</>}
          </Item>
        )}
        <Item rotulo="Situação de atualização">
          —<Nota>Regra por periodicidade ainda não definida (módulo Atualizações)</Nota>
        </Item>
        <Item rotulo="Licença">{d.licenca || "—"}</Item>
      </div>
      <div className="def-item full" style={{ marginTop: 14 }}>
        <label>Descrição</label>
        <div className="val" style={{ fontWeight: 400, whiteSpace: "pre-line" }}>
          {d.descricao || "—"}
        </div>
      </div>
      <TabelaRecursos recursos={d.recursos} removidos={d.recursos_removidos} />
      {bases && bases.length > 1 && (
        <p className="help-texto" style={{ marginTop: 10 }}>
          Também vinculado em: {bases.slice(1).map((b) => `${b.plano_nome} (${b.nome_previsto})`).join("; ")}.
        </p>
      )}
      <div className="mini-history">
        <h4>Histórico recente</h4>
        <div className="hist-row"><span>Disponível quando a rastreabilidade for implementada.</span></div>
      </div>
    </>
  );
}

function TabelaRecursos({ recursos, removidos }: { recursos: Recurso[]; removidos: number }) {
  return (
    <div style={{ marginTop: 16 }}>
      <h4 style={{ fontSize: 13, margin: "0 0 8px" }}>Recursos no portal ({recursos.length})</h4>
      {recursos.length === 0 ? (
        <p className="cell-muted">Nenhum recurso publicado.</p>
      ) : (
        <div className="table-scroll">
          <table>
            <thead><tr><th>Recurso</th><th>Formato</th><th>Última atualização</th><th /></tr></thead>
            <tbody>
              {recursos.map((r) => (
                <tr key={r.ckan_id}>
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
