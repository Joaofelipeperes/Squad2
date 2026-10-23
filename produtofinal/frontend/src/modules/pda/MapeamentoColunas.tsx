import type { ColunasPlanilha } from "./api";

/** Campo do sistema → índice da coluna escolhida (null = não importar). */
export type Escolhas = Record<string, number | null>;

export const escolhasIniciais = (c: ColunasPlanilha): Escolhas =>
  Object.fromEntries(c.campos.map((f) => [f.campo, f.sugestao]));

export const nomeColuna = (c: ColunasPlanilha, i: number) => c.colunas[i] || `Coluna ${i + 1} (sem título)`;

/** Campos obrigatórios ainda sem coluna (bloqueiam a importação). */
export const pendentes = (c: ColunasPlanilha, e: Escolhas) =>
  c.campos.filter((f) => f.obrigatorio && e[f.campo] == null);

/**
 * Etapa de mapeamento da importação do PDA: cada campo esperado pelo sistema ao lado das colunas
 * encontradas na planilha. Uma coluna só pode ir para um campo (as já usadas ficam desabilitadas).
 */
export function MapeamentoColunas({ colunas, escolhas, onMudar }: {
  colunas: ColunasPlanilha; escolhas: Escolhas; onMudar: (e: Escolhas) => void;
}) {
  const c = colunas;
  const usadaPor = new Map<number, string>();
  c.campos.forEach((f) => {
    const i = escolhas[f.campo];
    if (i != null) usadaPor.set(i, f.rotulo);
  });
  const mapeados = c.campos.filter((f) => escolhas[f.campo] != null);
  const faltando = pendentes(c, escolhas);

  return (
    <>
      <p className="help-texto">
        Cabeçalho encontrado na linha {c.linha + 1} da planilha. Confira a coluna de cada campo; as
        sugestões vêm de nomes iguais ou parecidos (sem diferença de maiúsculas, acentos, espaços e “_”).
      </p>
      <div className="table-scroll" style={{ marginTop: 10 }}>
        <table>
          <thead><tr><th>Campo do sistema</th><th>Coluna da planilha</th><th>Exemplo (1ª linha)</th></tr></thead>
          <tbody>
            {c.campos.map((f) => {
              const i = escolhas[f.campo];
              const sem = f.obrigatorio && i == null;
              const id = `pda-map-${f.campo}`;
              return (
                <tr key={f.campo}>
                  <td className="cell-strong">
                    <label htmlFor={id}>{f.rotulo}</label>
                    {f.obrigatorio && (
                      <>{" "}<span className={`badge ${sem ? "badge-red" : "badge-gray"}`}>obrigatório</span></>
                    )}
                  </td>
                  <td>
                    <select id={id} value={i ?? ""} aria-invalid={sem || undefined}
                      onChange={(e) => onMudar({ ...escolhas, [f.campo]: e.target.value === "" ? null : Number(e.target.value) })}>
                      <option value="">{f.obrigatorio ? "— escolha a coluna —" : "— não importar —"}</option>
                      {c.colunas.map((_, n) => {
                        const outro = usadaPor.get(n);
                        const ocupada = outro != null && n !== i;
                        return (
                          <option key={n} value={n} disabled={ocupada}>
                            {nomeColuna(c, n)}{ocupada ? ` · já usada em “${outro}”` : ""}
                          </option>
                        );
                      })}
                    </select>
                  </td>
                  <td className="cell-muted">{i != null ? (c.previa[0]?.[i] ?? "—") : "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {faltando.length > 0 && (
        <div className="inline-msg err" role="alert" style={{ marginTop: 10 }}>
          Escolha a coluna de: {faltando.map((f) => f.rotulo).join(", ")}.
        </div>
      )}
      <div className="def-item full" style={{ marginTop: 16 }}>
        <label>Prévia com o mapeamento ({c.previa.length} primeira(s) linha(s))</label>
        {c.previa.length === 0 || mapeados.length === 0 ? (
          <p className="help-texto">Nada a mostrar.</p>
        ) : (
          <div className="table-scroll">
            <table>
              <thead><tr>{mapeados.map((f) => <th key={f.campo}>{f.rotulo}</th>)}</tr></thead>
              <tbody>
                {c.previa.map((linha, n) => (
                  <tr key={n}>
                    {mapeados.map((f) => <td key={f.campo}>{linha[escolhas[f.campo] as number] ?? "—"}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
