import type { BasePda } from "./api";
import { fmtData, fmtDataHora } from "./formato";
import { DICA_SITUACAO, SituacaoBadge } from "./SituacaoBadge";
import { Pode } from "@/shared/acesso/Pode";
import { Campo, Detalhe, Grade, Resumo, Secao, Vazio } from "@/shared/ui/Detalhe";
import { Modal } from "@/shared/ui/Modal";

const PORTAL = "https://dadosabertos.go.gov.br/dataset/";

const sigiloso = (v: boolean | null) => (v == null ? <Vazio /> : v ? "Sim" : "Não");

interface Props {
  base: BasePda | null;
  onFechar: () => void;
  onEditar: (b: BasePda) => void;
  onExcluir: (b: BasePda) => void;
}

/**
 * Detalhe de uma base prevista (equivalente ao showDatasetDetails() do protótipo V1), agrupado em
 * seções: Identificação, Vínculo com o portal, Prazo e atualização, Recursos, Classificação e
 * Descrição. Os dados refletem o CKAN sem alterá-lo; editar e excluir mexem só no cadastro do PDA.
 */
export function BaseDetalheModal({ base, onFechar, onEditar, onExcluir }: Props) {
  if (!base) return null;
  const b = base;
  const orgao = b.orgao_nome ?? b.orgao_sigla;
  const periodicidadeDiferente =
    !!b.periodicidade_original && b.periodicidade_original.trim() !== b.periodicidade;
  const linkPortal = b.dataset_id_ckan && b.dataset_ativo !== false ? `${PORTAL}${encodeURIComponent(b.dataset_id_ckan)}` : null;
  const seloVinculo = b.vinculo === "resolvido" ? <span className="badge badge-blue">Vínculo resolvido</span>
    : b.vinculo === "pendente" ? <span className="badge badge-amber">Vínculo pendente</span>
    : <span className="badge badge-gray">Sem vínculo</span>;

  return (
    <Modal aberto titulo={b.nome_previsto} onFechar={onFechar}
      subtitulo={`${orgao} · Camada de monitoramento (dados refletem o CKAN, sem alterá-lo)`}
      rodape={<>
        <Pode permissao="pda.gerenciar_planos">
          <button type="button" className="btn btn-danger-line btn-sm" onClick={() => onExcluir(b)}>
            <i className="fa-solid fa-trash" />Excluir base
          </button>
          <button type="button" className="btn btn-outline btn-sm" onClick={() => onEditar(b)}>
            <i className="fa-solid fa-pen" />Editar
          </button>
        </Pode>
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
      <Detalhe>
        <Resumo
          selos={<>
            <SituacaoBadge situacao={b.situacao} />
            {seloVinculo}
            <span className="badge badge-gray">{b.plano_nome}</span>
          </>}
          fatos={[
            { valor: fmtData(b.prazo_abertura), rotulo: "Prazo previsto" },
            { valor: b.data_publicacao ? fmtDataHora(b.data_publicacao) : "Não publicado", rotulo: "Publicação" },
            { valor: b.periodicidade, rotulo: "Periodicidade" },
          ]} />

        <Secao titulo="Identificação">
          <Grade>
            <Campo rotulo="Nome da base">{b.nome_previsto}</Campo>
            <Campo rotulo="Órgão responsável"
              nota={!b.orgao_nome ? "Sem correspondência com organização do portal" : undefined}>
              {b.orgao_sigla}{b.orgao_nome && ` — ${b.orgao_nome}`}
            </Campo>
            <Campo rotulo="Unidade responsável">{b.unidade_responsavel || <Vazio />}</Campo>
            <Campo rotulo="PDA de origem">{b.plano_nome}</Campo>
          </Grade>
        </Secao>

        <Secao titulo="Vínculo com o portal">
          <Grade>
            <Campo rotulo="Dataset no portal"
              nota={b.vinculo === "pendente"
                ? `${b.dataset_id_ckan_planilha ? "ID do CKAN" : "Endereço"} informado no PDA; nenhum dataset do inventário atual corresponde a ele.`
                : b.vinculo === "sem_vinculo" ? "Nenhum endereço desta base no portal foi informado." : undefined}>
              {b.vinculo === "resolvido" && (b.dataset_titulo ?? b.dataset_name ?? "—")}
              {b.vinculo === "pendente" && (
                <>
                  <span className="mono" style={{ fontWeight: 500, wordBreak: "break-all" }}>
                    {b.dataset_id_ckan_planilha ?? b.dataset_name_planilha}
                  </span>{" "}
                  <span className="badge badge-amber">vínculo pendente</span>
                </>
              )}
              {b.vinculo === "sem_vinculo" && <Vazio />}
            </Campo>
            <Campo rotulo="ID do dataset (CKAN)" mono>{b.dataset_id_ckan ?? "—"}</Campo>
          </Grade>
        </Secao>

        <Secao titulo="Prazo e atualização">
          <Grade>
            <Campo rotulo="Prazo previsto (PDA)">{fmtData(b.prazo_abertura)}</Campo>
            <Campo rotulo="Data de publicação">
              {b.data_publicacao ? fmtDataHora(b.data_publicacao) : "Não publicado"}
            </Campo>
            <Campo rotulo="Periodicidade" nota={periodicidadeDiferente ? `planilha: ${b.periodicidade_original}` : undefined}>
              {b.periodicidade}
            </Campo>
            <Campo rotulo="Última atualização real">
              {fmtDataHora(b.ultima_atualizacao)}
              {b.ultima_atualizacao && b.ultima_atualizacao_estimada && " (estimada pela criação)"}
            </Campo>
            <Campo rotulo="Situação PDA" nota={DICA_SITUACAO[b.situacao]}>
              <SituacaoBadge situacao={b.situacao} />
            </Campo>
          </Grade>
        </Secao>

        <Secao titulo="Recursos">
          <Grade>
            <Campo rotulo="Recursos válidos"
              nota={b.dataset_id != null ? "Dicionário de dados não entra na contagem" : undefined}>
              {b.dataset_id != null ? b.recursos_validos : "—"}
            </Campo>
            <Campo rotulo="Formatos dos recursos">{b.formatos.length ? b.formatos.join(", ") : "—"}</Campo>
          </Grade>
        </Secao>

        <Secao titulo="Classificação">
          <Grade>
            <Campo rotulo="Conteúdo sigiloso">{sigiloso(b.possui_conteudo_sigiloso)}</Campo>
            <Campo rotulo="Políticas públicas">{b.politicas_publicas || <Vazio />}</Campo>
          </Grade>
        </Secao>

        <Secao titulo="Descrição">
          <p className="det-valor leve" style={{ lineHeight: 1.5, marginBottom: 14 }}>{b.descricao || "—"}</p>
        </Secao>
      </Detalhe>
    </Modal>
  );
}
