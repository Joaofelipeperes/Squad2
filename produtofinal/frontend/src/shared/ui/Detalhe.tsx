import type { ReactNode } from "react";

/**
 * Peças das janelas de detalhe agrupadas em seções (Dataset, Base do PDA, Organização, Achado LGPD).
 * Estrutura: <Detalhe> → <Resumo> (faixa com o essencial) → várias <Secao> com <Grade> de <Campo>.
 * Seção omitida por permissão simplesmente não aparece. Estilos em `design-system/overrides.css`
 * (prefixo `det-`).
 */
export function Detalhe({ children }: { children: ReactNode }) {
  return <div className="det">{children}</div>;
}

export interface Fato {
  valor: ReactNode;
  rotulo: string;
}

/** Faixa do topo: selos de situação (`.badge`) e 2 ou 3 números-chave, visíveis sem rolar. */
export function Resumo({ selos, fatos }: { selos?: ReactNode; fatos?: Fato[] }) {
  return (
    <div className="det-resumo">
      {selos && <div className="det-selos">{selos}</div>}
      {fatos?.map((f) => (
        <div key={f.rotulo} className="det-fato">
          <span className="n">{f.valor}</span>
          <span className="l">{f.rotulo}</span>
        </div>
      ))}
    </div>
  );
}

/** Seção com título; `nota` é um texto curto à direita do título. */
export function Secao({ titulo, nota, children }: { titulo: string; nota?: string; children: ReactNode }) {
  return (
    <section className="det-secao">
      <div className="det-secao-t">
        <h4>{titulo}</h4>
        {nota && <span className="det-nota-t">{nota}</span>}
      </div>
      {children}
    </section>
  );
}

/** Duas colunas (uma em tela estreita). */
export function Grade({ children }: { children: ReactNode }) {
  return <div className="det-grade">{children}</div>;
}

/** Campo rótulo/valor. `cheio` ocupa a linha toda; `leve` = texto corrido (peso normal). */
export function Campo({ rotulo, children, mono = false, leve = false, cheio = false, nota }: {
  rotulo: string; children: ReactNode; mono?: boolean; leve?: boolean; cheio?: boolean; nota?: ReactNode;
}) {
  const classe = ["det-valor", mono && "mono", leve && "leve"].filter(Boolean).join(" ");
  return (
    <div className={cheio ? "det-campo cheio" : "det-campo"}>
      <label>{rotulo}</label>
      <div className={classe}>{children}</div>
      {nota && <div className="det-nota">{nota}</div>}
    </div>
  );
}

/** Traço cinza para valor ausente. */
export const Vazio = () => <span className="det-vazio">—</span>;
