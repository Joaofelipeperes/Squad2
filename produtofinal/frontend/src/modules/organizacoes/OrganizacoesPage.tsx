import { useQuery } from "@tanstack/react-query";
import type { KeyboardEvent, ReactNode } from "react";
import { useState } from "react";
import type { Organizacao } from "./api";
import { organizacoesApi } from "./api";
import { OrganizacaoDetalheModal } from "./OrganizacaoDetalheModal";
import { PageLede } from "@/shared/ui/PageLede";

/**
 * Tela "Organizações" (US19) — referência visual: #screen-organizations do Protótipo V1.
 * Bases vêm do PDA vigente; datasets e formatos, do inventário do portal. Indicadores que ainda
 * dependem do vínculo PDA × portal ou de regra não definida aparecem como pendentes, não como 0.
 */
export default function OrganizacoesPage() {
  const dados = useQuery({ queryKey: ["painel", "organizacoes"], queryFn: organizacoesApi.lista });
  const [detalhe, setDetalhe] = useState<Organizacao | null>(null);
  const d = dados.data;

  return (
    <section className="screen">
      <PageLede titulo="Organizações">
        Situação consolidada de cumprimento do PDA por órgão publicador.
      </PageLede>

      <div className="panel">
        <div className="panel-head" style={{ borderBottom: "none", paddingBottom: 0 }}>
          <div className="sub" style={{ fontSize: 12.5 }}>
            {d && (d.plano
              ? <>Bases do PDA vigente: <strong>{d.plano.nome}</strong> · {d.organizacoes.length} órgão(s)</>
              : "Nenhum PDA vigente: as colunas de bases ficam zeradas até um PDA ser cadastrado.")}
          </div>
        </div>
        <div className="table-scroll">
          <table>
            <thead><tr>
              <th>Órgão</th><th>Bases previstas</th><th>Bases publicadas</th>
              <th title="Bases vinculadas com prazo vencido e sem publicação no portal">Em atraso</th>
              <th>Atualização</th><th>Riscos LGPD</th><th>Índice de atenção</th>
            </tr></thead>
            <tbody>
              {dados.isError ? (
                <tr><td colSpan={7} style={{ padding: 18 }}>
                  <div className="inline-msg err" role="alert">
                    Não foi possível carregar as organizações: {dados.error.message}
                  </div>
                </td></tr>
              ) : !d ? (
                <tr><td colSpan={7} className="table-empty">Carregando…</td></tr>
              ) : d.organizacoes.length === 0 ? (
                <tr><td colSpan={7} className="table-empty">
                  Nenhum órgão no inventário: rode a coleta pelo botão "Atualizar dados".
                </td></tr>
              ) : (
                d.organizacoes.map((o) => <Linha key={o.chave} o={o} onAbrir={setDetalhe} />)
              )}
            </tbody>
          </table>
        </div>
        <div className="panel-body" style={{ paddingTop: 10 }}>
          <p className="help-texto">
            <Pendente>aguardando vínculo</Pendente> depende de ligar as bases do PDA aos datasets do portal
            (pelo ID). <Pendente>a definir</Pendente> depende de regra ainda não definida (atualização por
            periodicidade, índice de atenção) ou do módulo de dados pessoais.
          </p>
          <p className="help-texto">
            Em atraso conta só bases vinculadas cujo prazo venceu sem publicação: sem o vínculo não há como
            saber se a base já está no portal.
          </p>
        </div>
      </div>

      <OrganizacaoDetalheModal org={detalhe} formatosAbertos={d?.formatos_abertos ?? []}
        onFechar={() => setDetalhe(null)} />
    </section>
  );
}

/** Ressalva para as bases sem vínculo: não há como conferir se já foram publicadas. */
export const NAO_CONFIRMADO = "Publicação ainda não confirmada: aguardando vínculo";

/** Indicador ainda não calculável: badge cinza com o motivo. */
export function Pendente({ children }: { children: ReactNode }) {
  return <span className="badge badge-gray" style={{ fontWeight: 500 }}>{children}</span>;
}

function Linha({ o, onAbrir }: { o: Organizacao; onAbrir: (o: Organizacao) => void }) {
  const teclado = (e: KeyboardEvent<HTMLTableRowElement>) => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onAbrir(o); }
  };
  const semOrgao = o.organizacao_id == null;
  const semConfirmacao = o.bases_vinculadas < o.bases_previstas;
  return (
    <tr tabIndex={0} onClick={() => onAbrir(o)} onKeyDown={teclado}>
      <td className="cell-strong">
        {o.nome}
        {!semOrgao && o.siglas.length > 0 && (
          <span className="cell-muted mono" style={{ marginLeft: 4 }}>({o.siglas.join(", ")})</span>
        )}
        {semOrgao && (
          <>{" "}<span className="badge badge-amber" title="Sigla do PDA sem correspondência com organização do portal">
            sem organização no portal</span></>
        )}
      </td>
      <td>{o.bases_previstas}</td>
      <td>{o.bases_vinculadas > 0 ? `${o.bases_publicadas} de ${o.bases_vinculadas} vinculada(s)` : <Pendente>aguardando vínculo</Pendente>}</td>
      <td>
        {o.bases_em_atraso == null
          ? <Pendente>aguardando vínculo</Pendente>
          : <span className={`badge ${o.bases_em_atraso > 0 ? "badge-red" : "badge-green"}`}
              title={semConfirmacao ? `Entre as ${o.bases_vinculadas} base(s) vinculada(s). ${NAO_CONFIRMADO} nas demais.` : undefined}>
              {o.bases_em_atraso}{semConfirmacao ? ` de ${o.bases_vinculadas} vinculada(s)` : ""}
            </span>}
      </td>
      <td>{o.atualizacao_pct != null ? `${o.atualizacao_pct}%` : <Pendente>a definir</Pendente>}</td>
      <td>{o.riscos_lgpd != null ? o.riscos_lgpd : <Pendente>a definir</Pendente>}</td>
      <td>{o.indice_atencao ?? <Pendente>a definir</Pendente>}</td>
    </tr>
  );
}
