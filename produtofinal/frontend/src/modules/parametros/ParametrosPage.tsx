import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useAuth } from "@/app/auth/AuthContext";
import { api } from "@/shared/api/client";
import { PageLede } from "@/shared/ui/PageLede";
import { useToast } from "@/shared/ui/Toast";

interface Parametro { chave: string; rotulo: string; descricao: string; valor: unknown; padrao: unknown; pbi: string }

const paraTexto = (v: unknown) => (Array.isArray(v) ? v.join(", ") : String(v));
function deTexto(texto: string, padrao: unknown): unknown {
  if (Array.isArray(padrao)) return texto.split(",").map((s) => s.trim()).filter(Boolean);
  if (typeof padrao === "number") return Number(texto);
  return texto;
}

export default function ParametrosPage() {
  const { pode } = useAuth();
  const podeEditar = pode("parametros.editar");
  const qc = useQueryClient();
  const toast = useToast();
  const q = useQuery({ queryKey: ["parametros"], queryFn: () => api.get<Parametro[]>("/parametros") });
  const [edicao, setEdicao] = useState<Record<string, string>>({});
  const salvar = useMutation({
    mutationFn: (p: Parametro) => api.put(`/parametros/${p.chave}`, { valor: deTexto(edicao[p.chave] ?? "", p.padrao) }),
    onSuccess: () => { toast("Parâmetro salvo."); qc.invalidateQueries({ queryKey: ["parametros"] }); },
    onError: (e: Error) => toast(e.message, true),
  });

  return (
    <section className="screen">
      <PageLede titulo="Parâmetros de monitoramento">
        Valores de negócio usados pelos indicadores. Listas são separadas por vírgula.
      </PageLede>
      <div className="panel">
        <div className="table-scroll">
          <table>
            <thead><tr><th>Parâmetro</th><th>Valor</th><th>Origem</th><th /></tr></thead>
            <tbody>
              {q.data?.map((p) => (
                <tr key={p.chave}>
                  <td style={{ maxWidth: 340 }}>
                    <div className="cell-strong">{p.rotulo}</div>
                    <div className="cell-muted" style={{ fontSize: 12 }}>{p.descricao}</div>
                  </td>
                  <td style={{ minWidth: 280 }}>
                    <input className="text-input" style={{ width: "100%" }} disabled={!podeEditar}
                      value={edicao[p.chave] ?? paraTexto(p.valor)}
                      onChange={(e) => setEdicao((s) => ({ ...s, [p.chave]: e.target.value }))} />
                  </td>
                  <td><span className="badge badge-gray">{p.pbi}</span></td>
                  <td>{podeEditar && edicao[p.chave] !== undefined && (
                    <button className="btn btn-primary btn-sm" onClick={() => salvar.mutate(p)}>Salvar</button>
                  )}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
