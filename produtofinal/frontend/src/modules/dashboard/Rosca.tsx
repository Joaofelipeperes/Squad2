import { useId, useState } from "react";

export interface Fatia {
  rotulo: string;
  total: number;
  cor: string;
  icone: string; // Font Awesome: a cor nunca identifica a fatia sozinha
  hachurada?: boolean; // textura (diagonais) para "não se aplica"
}

const fmt = new Intl.NumberFormat("pt-BR");
const R = 70; // raio do anel
const ESPESSURA = 22;
const VAO = 2; // vão (cor da superfície) entre fatias
const CIRC = 2 * Math.PI * R;

/**
 * Rosca (SVG, sem biblioteca) com legenda fixa ao lado: ícone, rótulo, quantidade e %. As fatias têm
 * um vão de 2px; passar o mouse ou focar uma linha da legenda destaca a fatia e mostra o valor no
 * centro. Sem foco, o centro mostra o total.
 */
export function Rosca({ fatias, unidade, rotuloAcessivel }: {
  fatias: Fatia[]; unidade: [string, string]; rotuloAcessivel: string;
}) {
  const [ativa, setAtiva] = useState<number | null>(null);
  const idTextura = `hachura-${useId().replace(/:/g, "")}`;
  const total = fatias.reduce((s, f) => s + f.total, 0);
  const pct = (n: number) => (total ? Math.round((n / total) * 1000) / 10 : 0);
  const qtd = (n: number) => `${fmt.format(n)} ${n === 1 ? unidade[0] : unidade[1]}`;
  const visiveis = fatias.filter((f) => f.total > 0).length;

  let inicio = 0;
  const arcos = fatias.map((f, i) => {
    const tamanho = total ? (f.total / total) * CIRC : 0;
    const arco = { i, f, offset: -inicio, tamanho: Math.max(0, tamanho - (visiveis > 1 ? VAO : 0)) };
    inicio += tamanho;
    return arco;
  });
  const destaque = ativa != null ? fatias[ativa] : null;
  const resumo = fatias.map((f) => `${f.rotulo}: ${qtd(f.total)} (${fmt.format(pct(f.total))}%)`).join("; ");

  return (
    <div className="rosca">
      <svg viewBox="0 0 180 180" className="rosca-svg" role="img" aria-label={`${rotuloAcessivel}. ${resumo}`}>
        <defs>
          <pattern id={idTextura} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="6" height="6" fill="var(--surface)" />
            <rect width="2.5" height="6" fill="var(--gray-500)" />
          </pattern>
        </defs>
        <g transform="rotate(-90 90 90)">
          {total === 0 && (
            <circle cx="90" cy="90" r={R} fill="none" stroke="var(--gray-200)" strokeWidth={ESPESSURA} />
          )}
          {arcos.map(({ i, f, offset, tamanho }) => tamanho > 0 && (
            <circle key={f.rotulo} cx="90" cy="90" r={R} fill="none"
              stroke={f.hachurada ? `url(#${idTextura})` : f.cor}
              strokeWidth={ativa === i ? ESPESSURA + 6 : ESPESSURA}
              strokeDasharray={`${tamanho} ${CIRC - tamanho}`} strokeDashoffset={offset}
              opacity={ativa == null || ativa === i ? 1 : 0.35}
              onMouseEnter={() => setAtiva(i)} onMouseLeave={() => setAtiva(null)} />
          ))}
        </g>
        <text x="90" y="86" textAnchor="middle" className="rosca-numero">
          {fmt.format(destaque ? destaque.total : total)}
        </text>
        <text x="90" y="106" textAnchor="middle" className="rosca-sub">
          {destaque ? `${fmt.format(pct(destaque.total))}%` : unidade[1]}
        </text>
      </svg>
      <ul className="rosca-legenda">
        {fatias.map((f, i) => (
          <li key={f.rotulo} tabIndex={0} className={ativa === i ? "ativa" : undefined}
            onMouseEnter={() => setAtiva(i)} onMouseLeave={() => setAtiva(null)}
            onFocus={() => setAtiva(i)} onBlur={() => setAtiva(null)}>
            <span className={`rosca-amostra${f.hachurada ? " hachurada" : ""}`}
              style={f.hachurada ? undefined : { background: f.cor }} />
            <i className={`fa-solid ${f.icone}`} aria-hidden="true" />
            <span className="rosca-rotulo">{f.rotulo}</span>
            <span className="rosca-valor">{fmt.format(f.total)}</span>
            <span className="rosca-pct">{fmt.format(pct(f.total))}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
