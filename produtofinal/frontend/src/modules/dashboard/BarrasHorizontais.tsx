import { useState } from "react";

export interface Barra { rotulo: string; total: number; cor: string }

const fmt = new Intl.NumberFormat("pt-BR");

/**
 * Gráfico de barras horizontais em HTML (sem biblioteca): rótulo à esquerda, barra crescendo da
 * linha de base com ponta arredondada e o valor na ponta. Ao passar o mouse, uma dica mostra a
 * quantidade e o % do total; leitores de tela leem rótulo, valor e % como texto da linha (sem uma
 * parada de Tab por barra). O rótulo sempre acompanha a cor.
 */
export function BarrasHorizontais({ barras, unidade, rotuloAcessivel }: {
  barras: Barra[]; unidade: [string, string]; rotuloAcessivel: string;
}) {
  const [ativa, setAtiva] = useState<number | null>(null);
  const maximo = Math.max(1, ...barras.map((b) => b.total));
  const soma = barras.reduce((s, b) => s + b.total, 0);
  const qtd = (n: number) => `${fmt.format(n)} ${n === 1 ? unidade[0] : unidade[1]}`;

  return (
    <div className="barras" role="list" aria-label={rotuloAcessivel}>
      {barras.map((b, i) => {
        const pct = soma ? Math.round((b.total / soma) * 1000) / 10 : 0;
        const dica = `${b.rotulo}: ${qtd(b.total)} (${fmt.format(pct)}% do total)`;
        return (
          <div key={b.rotulo} className="barras-linha" role="listitem"
            onMouseEnter={() => setAtiva(i)} onMouseLeave={() => setAtiva(null)}>
            <span className="barras-rotulo">{b.rotulo}</span>
            <span className="barras-trilho">
              <span className="barras-barra" aria-hidden="true"
                style={{ width: `${(b.total / maximo) * 100}%`, background: b.cor }} />
              <span className="barras-valor">{fmt.format(b.total)}</span>
              <span className="sr-only"> ({fmt.format(pct)}% do total)</span>
              {ativa === i && <span className="barras-dica" aria-hidden="true">{dica}</span>}
            </span>
          </div>
        );
      })}
    </div>
  );
}
