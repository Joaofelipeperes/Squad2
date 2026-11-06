import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { rastreabilidadeApi } from "./api";
import { useAuth } from "@/app/auth/AuthContext";

const QUANTIDADE = 5;

const fmtData = (iso: string) =>
  new Date(iso).toLocaleDateString("pt-BR", { timeZone: "America/Sao_Paulo" });

/**
 * Histórico recente de um dataset ou de um órgão (.mini-history do Protótipo V1), lido da linha do
 * tempo da rastreabilidade: os últimos eventos, com atalho para a tela Rastreabilidade já filtrada.
 * Usado nos detalhes de dataset (Datasets, Atualizações) e de órgão (Organizações).
 */
export function HistoricoRecente({ titulo, dataset, orgao, onSair }: {
  titulo: string;
  dataset?: string | null; // ID do CKAN do dataset
  orgao?: number | null;   // `id` do órgão no inventário
  onSair: () => void;      // fecha o modal antes de ir para a tela Rastreabilidade
}) {
  const { pode } = useAuth();
  const navigate = useNavigate();
  const alvo = dataset ? { dataset } : orgao != null ? { orgao } : null;
  const permitido = pode("rastreabilidade.acessar");
  const lista = useQuery({
    queryKey: ["rastreabilidade", "recentes", alvo],
    queryFn: () => rastreabilidadeApi.recentes(alvo!, QUANTIDADE),
    enabled: permitido && alvo != null,
  });

  function verTodos() {
    onSair();
    navigate(`/rastreabilidade?${dataset ? `busca=${encodeURIComponent(dataset)}` : `orgao=${orgao}`}`);
  }

  const aviso = (texto: string) => <div className="hist-row"><span>{texto}</span></div>;
  const d = lista.data;
  return (
    <div className="mini-history">
      <h4>{titulo}</h4>
      {!permitido ? aviso("Histórico disponível para quem tem acesso à Rastreabilidade.")
        : !alvo ? aviso(dataset === null ? "Dataset sem ID do CKAN: sem histórico." : "Órgão sem organização no portal: sem histórico.")
        : lista.isError ? aviso(`Não foi possível carregar o histórico: ${lista.error.message}`)
        : !d ? aviso("Carregando…")
        : d.eventos.length === 0 ? aviso(dataset
          ? "Sem eventos de rastreabilidade recentes para este dataset."
          : "Nenhum evento recente registrado.")
        : d.eventos.map((e) => (
          <div key={e.id} className="hist-row">
            <span className="date">{fmtData(e.ocorrido_em)}</span>
            <span>
              <b>{e.tipo_rotulo}</b>
              {" · "}
              {dataset ? e.resumo
                : e.origem === "comparacao_coletas" ? `Cadastro do órgão · ${e.resumo}`
                : `${e.dataset_titulo ?? e.dataset_id_ckan ?? "—"} · ${e.resumo}`}
            </span>
          </div>
        ))}
      {d && d.eventos.length > 0 && (
        <button type="button" className="btn-link" style={{ marginTop: 8 }} onClick={verTodos}>
          {d.total > d.eventos.length ? `Ver todos os ${d.total} eventos na Rastreabilidade` : "Abrir na Rastreabilidade"}
        </button>
      )}
    </div>
  );
}
