import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import type { Alcance, Correcao, Operador } from "./api";
import { FILTROS_VAZIOS, correcoesApi, lgpdApi, operadorPadrao } from "./api";
import { Modal } from "@/shared/ui/Modal";

interface Escolha { incluir: boolean; operador: Operador; alcance: Alcance }

/**
 * Passo 1 da anonimização (US26, PBI-91): para cada achado CONFIRMADO do recurso, escolher operador
 * e alcance. O backend baixa o original, guarda a cópia de segurança e gera a prévia.
 */
export function NovaCorrecaoModal({ recursoId, onFechar, onCriada }: {
  recursoId: number | null; onFechar: () => void; onCriada: (c: Correcao) => void;
}) {
  const [escolhas, setEscolhas] = useState<Record<number, Escolha>>({});
  const confirmados = useQuery({
    queryKey: ["lgpd", "achados", { ...FILTROS_VAZIOS, status: "confirmado" }],
    queryFn: () => lgpdApi.achados({ ...FILTROS_VAZIOS, status: "confirmado" }),
    enabled: recursoId !== null,
  });
  const opcoes = useQuery({ queryKey: ["lgpd", "correcoes"], queryFn: correcoesApi.lista,
                            enabled: recursoId !== null });
  const achados = (confirmados.data?.achados ?? []).filter((a) => a.recurso_id === recursoId);

  useEffect(() => {
    setEscolhas(Object.fromEntries(achados.map((a) => [a.id, {
      incluir: true, operador: operadorPadrao(a.tipo), alcance: "detectados" as Alcance }])));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [recursoId, confirmados.data]);

  const set = (id: number, campo: keyof Escolha, valor: Escolha[keyof Escolha]) =>
    setEscolhas((e) => ({ ...e, [id]: { ...e[id], [campo]: valor } }));
  const itens = achados.filter((a) => escolhas[a.id]?.incluir)
    .map((a) => ({ achado_id: a.id, operador: escolhas[a.id].operador, alcance: escolhas[a.id].alcance }));

  const gerar = useMutation({
    mutationFn: () => correcoesApi.gerarPrevia(recursoId!, itens),
    onSuccess: onCriada,
  });
  const primeiro = achados[0];

  return (
    <Modal largo aberto={recursoId !== null} onFechar={onFechar} titulo="Anonimizar recurso"
      subtitulo={primeiro ? `${primeiro.recurso_nome ?? primeiro.recurso_id} · ${primeiro.dataset_titulo}` : undefined}
      rodape={<>
        <button className="btn btn-outline btn-sm" onClick={onFechar}>Cancelar</button>
        <button className="btn btn-primary btn-sm" disabled={!itens.length || gerar.isPending}
                onClick={() => gerar.mutate()}>
          <i className="fa-solid fa-eye" />{gerar.isPending ? "Enviando…" : "Gerar prévia"}
        </button>
      </>}>
      <p style={{ fontSize: 13, marginTop: 0 }}>
        Entram só os achados <b>confirmados</b> deste recurso. Nada é publicado agora: o sistema
        gera uma prévia do arquivo anonimizado para você conferir e aprovar no passo seguinte.
      </p>
      {confirmados.isError ? (
        <div className="inline-msg err">{confirmados.error.message}</div>
      ) : !confirmados.data ? (
        <p className="cell-muted">Carregando…</p>
      ) : achados.length === 0 ? (
        <div className="inline-msg">Nenhum achado confirmado neste recurso. Confirme os achados antes.</div>
      ) : (
        <div className="table-scroll">
          <table>
            <thead><tr><th /><th>Tipo</th><th>Coluna</th><th>Células</th><th>Como anonimizar</th><th>Alcance</th></tr></thead>
            <tbody>
              {achados.map((a) => {
                const e = escolhas[a.id];
                if (!e) return null;
                return (
                  <tr key={a.id}>
                    <td><input type="checkbox" aria-label={`Incluir ${a.tipo_rotulo} em ${a.coluna}`}
                               checked={e.incluir} onChange={(ev) => set(a.id, "incluir", ev.target.checked)} /></td>
                    <td>{a.tipo_rotulo}</td>
                    <td className="mono">{a.coluna}</td>
                    <td className="cell-muted">{a.ocorrencias}</td>
                    <td>
                      <select value={e.operador} disabled={!e.incluir}
                              onChange={(ev) => set(a.id, "operador", ev.target.value as Operador)}>
                        {(opcoes.data?.operadores ?? []).map((o) => <option key={o.valor} value={o.valor}>{o.rotulo}</option>)}
                      </select>
                    </td>
                    <td>
                      <select value={e.alcance} disabled={!e.incluir}
                              onChange={(ev) => set(a.id, "alcance", ev.target.value as Alcance)}>
                        {(opcoes.data?.alcances ?? []).map((o) => <option key={o.valor} value={o.valor}>{o.rotulo}</option>)}
                      </select>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <p className="cell-muted" style={{ fontSize: 12, marginBottom: 0 }}>
        “Só os trechos detectados” reencontra o dado com o mesmo motor da varredura e troca só o
        trecho (ex.: “cel (62) 99876-5432” → “cel &lt;TELEFONE&gt;”). “A célula inteira” troca todo
        valor não vazio da coluna — use quando a coluna inteira é dado pessoal.
      </p>
      {gerar.error && <div className="inline-msg err" role="alert">{(gerar.error as Error).message}</div>}
    </Modal>
  );
}
