import { useMutation } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import type { GrupoCatalogo, Papel, PapelIn } from "./api";
import { NOME_MODULO, acessoApi } from "./api";
import { Modal } from "@/shared/ui/Modal";

interface Props {
  aberto: boolean; papel: Papel | null; catalogo: GrupoCatalogo[];
  somenteLeitura?: boolean; // quem só pode ver papéis (sem acesso.gerenciar_papeis)
  onFechar: () => void; onSalvo: () => void;
}

export function PapelForm({ aberto, papel, catalogo, somenteLeitura: soVer = false, onFechar, onSalvo }: Props) {
  const [f, setF] = useState<PapelIn>({ codigo: "", nome: "", descricao: "", exige_orgao: false, permissoes: [] });
  const [erro, setErro] = useState<string | null>(null);
  const todas = !!papel?.todas;
  const somenteLeitura = soVer || todas;

  useEffect(() => {
    if (!aberto) return;
    setF(papel
      ? { codigo: papel.codigo, nome: papel.nome, descricao: papel.descricao, exige_orgao: papel.exige_orgao,
          permissoes: papel.permissoes }
      : { codigo: "", nome: "", descricao: "", exige_orgao: false, permissoes: [] });
    setErro(null);
  }, [aberto, papel]);

  const alternar = (c: string) => setF((s) => ({
    ...s, permissoes: s.permissoes.includes(c) ? s.permissoes.filter((x) => x !== c) : [...s.permissoes, c],
  }));

  const salvar = useMutation({
    mutationFn: () => (papel ? acessoApi.atualizarPapel(papel.id, f) : acessoApi.criarPapel(f)),
    onSuccess: () => { onSalvo(); onFechar(); },
    onError: (e: Error) => setErro(e.message),
  });

  return (
    <Modal aberto={aberto} onFechar={onFechar}
      titulo={papel ? `Papel “${papel.nome}”` : "Novo papel"}
      subtitulo={todas ? "O Administrador sempre tem todas as permissões." :
        soVer ? "Visualização. Alterar papéis exige a permissão Gerenciar papéis." :
        "Marque o que este papel pode ver (acessar) e fazer em cada módulo."}
      rodape={!somenteLeitura && (
        <button className="btn btn-primary btn-sm" onClick={() => salvar.mutate()} disabled={salvar.isPending}>
          <i className="fa-solid fa-floppy-disk" />Salvar papel
        </button>)}>
      <div className="form-grid">
        <div className="form-field">
          <label htmlFor="pp-nome">Nome</label>
          <input id="pp-nome" className="text-input" value={f.nome} disabled={somenteLeitura}
                 onChange={(e) => setF({ ...f, nome: e.target.value })} />
        </div>
        <div className="form-field">
          <label htmlFor="pp-codigo">Código</label>
          <input id="pp-codigo" className="text-input mono" value={f.codigo} placeholder="ex.: auditoria_interna"
                 disabled={somenteLeitura || !!papel?.sistema}
                 onChange={(e) => setF({ ...f, codigo: e.target.value })} />
        </div>
        <div className="form-field full">
          <label htmlFor="pp-desc">Descrição</label>
          <input id="pp-desc" className="text-input" value={f.descricao ?? ""} disabled={somenteLeitura}
                 onChange={(e) => setF({ ...f, descricao: e.target.value })} />
        </div>
        <label className="check-line full">
          <input type="checkbox" checked={f.exige_orgao} disabled={somenteLeitura}
                 onChange={(e) => setF({ ...f, exige_orgao: e.target.checked })} />
          <span>Exige vínculo com um órgão (usuários deste papel só veem dados do próprio órgão)</span>
        </label>
        {catalogo.map((g) => (
          <div key={g.modulo} className="form-field full" style={{ borderTop: "1px dashed var(--gray-200)", paddingTop: 10 }}>
            <label>{NOME_MODULO[g.modulo] ?? g.modulo}</label>
            {g.permissoes.map((p) => (
              <label key={p.codigo} className="check-line" title={p.codigo}>
                <input type="checkbox" disabled={somenteLeitura}
                       checked={todas || f.permissoes.includes(p.codigo)} onChange={() => alternar(p.codigo)} />
                <span>
                  {p.rotulo}{p.sensivel && <span className="badge badge-red" style={{ marginLeft: 6 }}>Sensível</span>}
                  <span className="cell-muted" style={{ display: "block", fontSize: 12 }}>{p.descricao}</span>
                </span>
              </label>
            ))}
          </div>
        ))}
        {erro && <div className="inline-msg err full">{erro}</div>}
      </div>
    </Modal>
  );
}
