import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/shared/api/client";
import { Pode } from "@/shared/acesso/Pode";
import { useToast } from "@/shared/ui/Toast";

interface Coleta { id: number; status: string; iniciada_em: string; finalizada_em: string | null }

const fmt = (iso: string) =>
  new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });

export function Topbar({ crumb, titulo }: { crumb: string; titulo: string }) {
  const toast = useToast();
  const qc = useQueryClient();
  const ultima = useQuery({
    queryKey: ["coleta", "ultima"],
    queryFn: () => api.get<Coleta | null>("/inventario/coletas/ultima"),
    refetchInterval: (q) => (q.state.data?.status === "executando" ? 5000 : 60000),
  });
  const coletar = useMutation({
    mutationFn: () => api.post<Coleta>("/inventario/coletas"),
    onSuccess: () => {
      toast("Coleta iniciada. Os indicadores serão atualizados ao final.");
      qc.invalidateQueries({ queryKey: ["coleta"] });
    },
    onError: (e: Error) => toast(e.message, true),
  });

  const c = ultima.data;
  const meta = !c ? "Nenhuma coleta realizada"
    : c.status === "executando" ? "Coleta em andamento…"
    : `Última coleta: ${fmt(c.finalizada_em ?? c.iniciada_em)}${c.status === "erro" ? " (falhou)" : ""}`;

  return (
    <header className="topbar">
      <div className="topbar-title">
        <span className="crumb">{crumb}</span>
        <h2>{titulo}</h2>
      </div>
      <div className="topbar-actions">
        <span className="topbar-meta">{meta}</span>
        <Pode permissao="inventario.coletar">
          <button className="btn btn-primary btn-sm" onClick={() => coletar.mutate()}
                  disabled={coletar.isPending || c?.status === "executando"}>
            <i className="fa-solid fa-arrows-rotate" />Atualizar dados
          </button>
        </Pode>
      </div>
    </header>
  );
}
