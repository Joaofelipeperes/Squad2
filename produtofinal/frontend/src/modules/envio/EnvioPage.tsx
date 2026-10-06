import { useAuth } from "@/app/auth/AuthContext";
import { PageLede } from "@/shared/ui/PageLede";

/** Área do órgão publicador — NÃO comprometida no Backlog v2 (ver docs/modulos/envio.md). */
export default function EnvioPage() {
  const { usuario } = useAuth();
  return (
    <section className="screen">
      <PageLede titulo="Envio de dados do órgão">
        Datasets e recursos de {usuario?.orgao?.titulo ?? "seu órgão"}.
      </PageLede>
      <div className="alert-callout">
        <i className="fa-solid fa-triangle-exclamation" />
        <div>
          Funcionalidade em definição. O envio de recursos pelos órgãos não faz parte do escopo
          atual do projeto e depende de decisão da CGE-GO e da SECTI.
        </div>
      </div>
    </section>
  );
}
