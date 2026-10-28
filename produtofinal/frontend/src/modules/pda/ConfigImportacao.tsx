import { useState } from "react";
import type { CampoImportacao, ConfigImportacao } from "./api";

/** Chave no localStorage: a configuração fica no navegador de quem importa (ADR-0020). */
const CHAVE = "pda.importacao.config";

interface DefCampo {
  campo: CampoImportacao;
  rotulo: string;
  exemplo: string;
  obrigatorio?: boolean;
}

/** Ordem do formulário: obrigatórios e vínculo primeiro, depois os demais campos da planilha. */
const CAMPOS: DefCampo[] = [
  { campo: "orgao", rotulo: "Órgão (sigla)", exemplo: "SIGLA", obrigatorio: true },
  { campo: "base", rotulo: "Nome da base no PDA", exemplo: "NOME_PDA", obrigatorio: true },
  { campo: "id_ckan", rotulo: "ID do dataset no CKAN", exemplo: "ID_UNICO" },
  { campo: "orgao_nome", rotulo: "Nome do órgão", exemplo: "ORGAO" },
  { campo: "periodicidade", rotulo: "Periodicidade", exemplo: "PERIODICIDADE" },
  { campo: "prazo", rotulo: "Prazo de abertura", exemplo: "PREVISAO_DE_ABERTURA" },
  { campo: "descricao", rotulo: "Descrição", exemplo: "Descrição" },
  { campo: "unidade", rotulo: "Unidade responsável", exemplo: "Unidade Responsável" },
  { campo: "politicas", rotulo: "Políticas públicas", exemplo: "Políticas Públicas" },
  { campo: "sigiloso", rotulo: "Possui conteúdo sigiloso", exemplo: "Possui Conteúdo Sigiloso?" },
  { campo: "portal", rotulo: "Link no portal", exemplo: "Disponível no Portal" },
];

/** Padrão = tabela fato do PDA (SIGLA;ORGAO;NOME_PDA;NOME_DA_BASE_CKAN;ID_UNICO;PERIODICIDADE;…). */
export const CONFIG_PADRAO: ConfigImportacao = {
  colunas: {
    orgao: "SIGLA", base: "NOME_PDA", id_ckan: "ID_UNICO", orgao_nome: "ORGAO",
    periodicidade: "PERIODICIDADE", prazo: "PREVISAO_DE_ABERTURA",
  },
  linha_cabecalho: 1,
  delimitador: ";",
};

/** Configuração salva neste navegador, ou o padrão (navegador sem armazenamento também cai no padrão). */
export function configSalva(): ConfigImportacao {
  try {
    const bruto = window.localStorage.getItem(CHAVE);
    if (!bruto) return CONFIG_PADRAO;
    const c = JSON.parse(bruto) as Partial<ConfigImportacao>;
    return {
      colunas: typeof c.colunas === "object" && c.colunas ? c.colunas : CONFIG_PADRAO.colunas,
      linha_cabecalho: typeof c.linha_cabecalho === "number" ? c.linha_cabecalho : null,
      delimitador: typeof c.delimitador === "string" ? c.delimitador : "",
    };
  } catch {
    return CONFIG_PADRAO;
  }
}

function salvarConfig(c: ConfigImportacao): boolean {
  try {
    window.localStorage.setItem(CHAVE, JSON.stringify(c));
    return true;
  } catch {
    return false;
  }
}

/** Problema que impede usar a configuração na importação, ou null. */
export function validarConfig(c: ConfigImportacao): string | null {
  if (c.linha_cabecalho != null && (!Number.isInteger(c.linha_cabecalho) || c.linha_cabecalho < 1)) {
    return "Configuração: o início da leitura deve ser a linha do cabeçalho (1 ou mais).";
  }
  if (c.delimitador.trim() && ![";", ",", "|", "\\t", "tab"].includes(c.delimitador.trim().toLowerCase())) {
    return 'Configuração: delimitador não suportado (use ";", ",", "|" ou "\\t").';
  }
  return null;
}

interface Props {
  config: ConfigImportacao;
  onMudar: (c: ConfigImportacao) => void;
}

/**
 * Aba Configuração da importação do PDA: nome de cada coluna no arquivo, linha do cabeçalho e
 * delimitador. "Salvar Config." guarda neste navegador; a importação usa o que está na tela.
 */
export function ConfigImportacaoPainel({ config, onMudar }: Props) {
  const [ajuda, setAjuda] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; texto: string } | null>(null);

  const mudar = (c: ConfigImportacao) => { setMsg(null); onMudar(c); };
  const setColuna = (campo: CampoImportacao, valor: string) =>
    mudar({ ...config, colunas: { ...config.colunas, [campo]: valor } });

  function salvar() {
    const problema = validarConfig(config);
    if (problema) { setMsg({ ok: false, texto: problema }); return; }
    setMsg(salvarConfig(config)
      ? { ok: true, texto: "Configuração salva neste navegador." }
      : { ok: false, texto: "Não foi possível salvar: o navegador bloqueou o armazenamento local." });
  }

  return (
    <>
      <div className="secao-titulo">
        <h4>
          Colunas da Tabela
          <button type="button" className="btn-ajuda" aria-expanded={ajuda} aria-label="Ajuda sobre as colunas"
                  onClick={() => setAjuda((a) => !a)}>?</button>
        </h4>
        <div className="row-actions">
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => mudar(CONFIG_PADRAO)}>
            Restaurar padrão
          </button>
          <button type="button" className="btn btn-outline btn-sm" onClick={salvar}>
            <i className="fa-solid fa-floppy-disk" />Salvar Config.
          </button>
        </div>
      </div>
      {ajuda && (
        <p className="help-texto" style={{ marginBottom: 14 }}>
          Informe o nome de cada coluna como está no cabeçalho do arquivo (maiúsculas, acentos e “_” não
          importam). Campo em branco, ou coluna que não estiver no arquivo, é procurado pelos nomes usuais
          (ex.: “Órgão”, “Base de Dados”, “Atualização”, “Meta/Prazo para abertura”). Com o <strong>ID do
          dataset no CKAN</strong>, a base já é vinculada ao dataset do inventário na importação; ID ainda não
          coletado fica como vínculo pendente e é resolvido em “Atualizar vínculos”. Sem ID, o vínculo usa o
          link do portal, se houver.
        </p>
      )}
      <div className="form-grid cols-4">
        {CAMPOS.map((d) => (
          <div className="form-field" key={d.campo}>
            <label htmlFor={`pda-cfg-${d.campo}`}>{d.obrigatorio && "*"}{d.rotulo}:</label>
            <input id={`pda-cfg-${d.campo}`} className="text-input" value={config.colunas[d.campo] ?? ""}
                   placeholder={`Ex: ${d.exemplo}`} maxLength={200}
                   onChange={(e) => setColuna(d.campo, e.target.value)} />
          </div>
        ))}
      </div>

      <div className="secao-titulo"><h4>Leitura</h4></div>
      <div className="form-grid cols-4">
        <div className="form-field">
          <label htmlFor="pda-cfg-linha">Início da leitura:</label>
          <div className="campo-com-sufixo">
            <input id="pda-cfg-linha" className="text-input" type="number" min={1} step={1}
                   value={config.linha_cabecalho ?? ""} placeholder="Automático"
                   onChange={(e) => mudar({ ...config,
                     linha_cabecalho: e.target.value === "" ? null : Number(e.target.value) })} />
            <span className="sufixo">linha</span>
          </div>
        </div>
        <div className="form-field">
          <label htmlFor="pda-cfg-delim">Delimitador:</label>
          <input id="pda-cfg-delim" className="text-input" value={config.delimitador} maxLength={5}
                 placeholder="Automático" onChange={(e) => mudar({ ...config, delimitador: e.target.value })} />
        </div>
      </div>
      {msg && <div className={`inline-msg ${msg.ok ? "ok" : "err"}`} role="status" style={{ marginTop: 14 }}>{msg.texto}</div>}
      <div className="notas-rodape">
        *Os campos com (*) asterisco são obrigatórios no arquivo!<br />
        Início da leitura = linha onde estão os nomes das colunas; os dados começam na linha seguinte (vazio =
        procurar nas 30 primeiras linhas).<br />
        O Delimitador somente será utilizado em casos de arquivo <strong>.csv</strong> (vazio = detectar “;” ou “,”).
      </div>
    </>
  );
}
