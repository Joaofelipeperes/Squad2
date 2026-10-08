import type { ReactNode } from "react";
import type { BasePda } from "./api";
import { fmtData, fmtDataHora } from "./formato";
import { SituacaoBadge } from "./SituacaoBadge";
import { Modal } from "@/shared/ui/Modal";

const PORTAL = "https://dadosabertos.go.gov.br/dataset/";

const sigiloso = (v: boolean | null) => (v == null ? "—" : v ? "Sim" : "Não");

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
 * Detalhe de uma base prevista (equivalente ao showDatasetDetails() do protótipo V1).
 * Só leitura: os dados refletem o CKAN sem alterá-lo.
 */
export function BaseDetalheModal({ base, onFechar }: { base: BasePda | null; onFechar: () => void }) {
  if (!base) return null;
  const b = base;
  const orgao = b.orgao_nome ?? b.orgao_sigla;
  const periodicidadeDiferente =
    !!b.periodicidade_original && b.periodicidade_original.trim() !== b.periodicidade;
  const linkPortal = b.dataset_id && b.dataset_ativo !== false ? `${PORTAL}${encodeURIComponent(b.dataset_id)}` : null;

  return (
    <Modal aberto titulo={b.nome_previsto} onFechar={onFechar}
      subtitulo={`${orgao} · Camada de monitoramento (dados refletem o CKAN, sem alterá-lo)`}
      rodape={<>
        {linkPortal && (
          <a className="btn btn-ghost btn-sm" href={linkPortal} target="_blank" rel="noopener noreferrer">
            <i className="fa-solid fa-arrow-up-right-from-square" />Abrir no portal
          </a>
        )}
        <button type="button" className="btn btn-outline btn-sm" onClick={onFechar}>Fechar</button>
      </>}>
      {b.dataset_ativo === false && (
        <div className="inline-msg err" role="alert" style={{ marginBottom: 14 }}>
          <i className="fa-solid fa-triangle-exclamation" style={{ marginRight: 6 }} />
          Dataset vinculado não está mais visível no portal (excluído ou privado).
        </div>
      )}
      <div className="def-grid">
        <Item rotulo="Nome da base">{b.nome_previsto}</Item>
        <Item rotulo="Órgão responsável">
          {b.orgao_sigla}{b.orgao_nome && ` — ${b.orgao_nome}`}
          {!b.orgao_nome && <Nota>Sem correspondência com organização do portal</Nota>}
        </Item>
        <Item rotulo="Unidade responsável">{b.unidade_responsavel || "—"}</Item>
        <Item rotulo="ID do dataset (CKAN)" mono>
          <span style={{ wordBreak: "break-all" }}>{b.dataset_id ?? "—"}</span>
        </Item>
        <Item rotulo="Dataset no portal">
          {b.vinculo === "resolvido" && (
            <>
              <span className="mono" style={{ fontWeight: 500, wordBreak: "break-all" }}>{b.dataset_name ?? "—"}</span>
              {b.dataset_titulo && <Nota>{b.dataset_titulo}</Nota>}
            </>
          )}
          {b.vinculo === "pendente" && (
            <>
              <span className="mono" style={{ fontWeight: 500, wordBreak: "break-all" }}>{b.dataset_name_planilha}</span>{" "}
              <span className="badge badge-amber">vínculo pendente</span>
              <Nota>Endereço informado na planilha; nenhum dataset do inventário atual corresponde a ele.</Nota>
            </>
          )}
          {b.vinculo === "sem_vinculo" && (
            <>—<Nota>A planilha não informa endereço desta base no portal.</Nota></>
          )}
        </Item>
        <Item rotulo="Prazo previsto (PDA)">{fmtData(b.prazo_abertura)}</Item>
        <Item rotulo="Data de publicação">
          {b.data_publicacao ? fmtDataHora(b.data_publicacao) : "Não publicado"}
        </Item>
        <Item rotulo="Periodicidade">
          {b.periodicidade}
          {periodicidadeDiferente && <Nota>planilha: {b.periodicidade_original}</Nota>}
        </Item>
        <Item rotulo="Última atualização real">
          {fmtDataHora(b.ultima_atualizacao)}
          {b.ultima_atualizacao && b.ultima_atualizacao_estimada && " (estimada pela criação)"}
        </Item>
        <Item rotulo="Recursos válidos">
          {b.dataset_id ? b.recursos_validos : "—"}
          {b.dataset_id && <Nota>Dicionário de dados não entra na contagem</Nota>}
        </Item>
        <Item rotulo="Formatos dos recursos">
          {b.formatos.length ? b.formatos.join(", ") : "—"}
        </Item>
        <Item rotulo="Situação PDA"><SituacaoBadge situacao={b.situacao} /></Item>
        <Item rotulo="Conteúdo sigiloso">{sigiloso(b.possui_conteudo_sigiloso)}</Item>
        <Item rotulo="Políticas públicas">{b.politicas_publicas || "—"}</Item>
        <Item rotulo="PDA de origem">{b.plano_nome}</Item>
      </div>
      <div className="def-item full" style={{ marginTop: 14 }}>
        <label>Descrição</label>
        <div className="val" style={{ fontWeight: 400 }}>{b.descricao || "—"}</div>
      </div>
    </Modal>
  );
}
