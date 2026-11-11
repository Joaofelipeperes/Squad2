"""Comandos administrativos.

    python -m app.cli gerar-chave
    python -m app.cli criar-usuario --email a@b.gov.br --nome "Fulana" --papel administrador
    python -m app.cli criar-usuario --email x@seduc.go.gov.br --nome "Servidor" \
        --papel orgao_publicador --orgao <id_ckan ou name da organizacao>
    python -m app.cli papeis                  # lista papéis e permissões
    python -m app.cli coletar                 # roda uma coleta agora, em primeiro plano
    python -m app.cli semear-ia               # cria perfis de IA de exemplo (mock + ollama)
    python -m app.cli configurar-ia-local     # perfis do Ollama do pacote de produção (ADR-0032)
    python -m app.cli backups                 # lista os backups internos do banco (ADR-0034)
    python -m app.cli backup-agora diario     # gera um backup agora (diario | mensal)
    python -m app.cli exportar-backup 12 copia.dump
    python -m app.cli restaurar-backup 12 --banco gda_restaurado   # PostgreSQL, via pg_restore
"""
import argparse
import getpass

import app.integrations.ai  # noqa: F401
from app.core.crypto import generate_key
from app.core.db import SessionLocal
from app.core.permissoes import PAPEIS_PADRAO
from app.modules import import_all_models

import_all_models()


def main() -> None:
    p = argparse.ArgumentParser(prog="app.cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("gerar-chave")
    u = sub.add_parser("criar-usuario")
    u.add_argument("--email", required=True)
    u.add_argument("--nome", required=True)
    u.add_argument("--papel", action="append", required=True,
                   choices=[p.codigo for p in PAPEIS_PADRAO], help="pode repetir")
    u.add_argument("--orgao", default=None, help="id_ckan ou name da organização (escopo de órgão)")
    sub.add_parser("papeis")
    sub.add_parser("coletar")
    sub.add_parser("semear-ia")
    ia = sub.add_parser("configurar-ia-local",
                        help="perfis do Ollama do servidor e vínculo das tarefas da varredura LGPD")
    ia.add_argument("--url", default="http://ollama:11434")
    ia.add_argument("--modelo-chat", default="qwen2.5:7b-instruct")
    ia.add_argument("--modelo-embeddings", default="bge-m3")
    sub.add_parser("backups")
    ba = sub.add_parser("backup-agora")
    ba.add_argument("tipo", choices=["diario", "mensal"])
    ex = sub.add_parser("exportar-backup")
    ex.add_argument("id", type=int)
    ex.add_argument("arquivo")
    rs = sub.add_parser("restaurar-backup")
    rs.add_argument("id", type=int)
    rs.add_argument("--banco", required=True, help="banco de destino (já criado)")
    rs.add_argument("--sobrescrever", action="store_true",
                    help="permite restaurar no banco em uso, apagando os dados atuais")
    args = p.parse_args()

    if args.cmd in ("backups", "backup-agora", "exportar-backup", "restaurar-backup"):
        _comando_backup(args)
    elif args.cmd == "gerar-chave":
        print(generate_key())
    elif args.cmd == "criar-usuario":
        from app.modules.acesso.service import criar_usuario, orgao_por_referencia
        senha = getpass.getpass("Senha (mín. 8 caracteres): ")
        with SessionLocal() as db:
            orgao_id = None
            if args.orgao:
                orgao_id = orgao_por_referencia(db, args.orgao)
                if orgao_id is None:
                    raise SystemExit(f"Organização {args.orgao!r} não encontrada (rode a coleta).")
            user = criar_usuario(db, args.email, args.nome, senha, args.papel, orgao_id)
            print(f"Usuário {user.email} criado com papéis {[p.codigo for p in user.papeis]}.")
    elif args.cmd == "papeis":
        for p in PAPEIS_PADRAO:
            perms = "TODAS" if p.todas else ", ".join(sorted(p.permissoes))
            print(f"{p.codigo:18} {p.nome}\n{'':18} {perms}\n")
    elif args.cmd == "coletar":
        from app.modules.inventario import service
        with SessionLocal() as db:
            c = service.iniciar(db, origem="manual", solicitante="cli")
        service.executar(c.id)
        print(f"Coleta {c.id} finalizada.")
    elif args.cmd == "semear-ia":
        from app.integrations.ai.policy import TarefaIA
        from app.modules.ia import service
        from app.modules.ia.schemas import PerfilIn, VinculoIn
        with SessionLocal() as db:
            mock = service.salvar_perfil(db, PerfilIn(nome="Simulado (dev)", tipo="mock",
                                                      modelo="eco", execucao_local=True))
            service.salvar_perfil(db, PerfilIn(nome="Ollama local", tipo="ollama",
                                               modelo="qwen2.5:7b", execucao_local=True))
            for t in TarefaIA:
                service.vincular(db, t, VinculoIn(perfil_id=mock.id), "cli")
            print("Perfis de exemplo criados; tarefas vinculadas ao provedor simulado.")
    elif args.cmd == "configurar-ia-local":
        configurar_ia_local(args.url, args.modelo_chat, args.modelo_embeddings)


def _comando_backup(args) -> None:
    from app.modules.backup import service
    try:
        if args.cmd == "backups":
            for c in service.listar():
                print(f"{c.id:>5}  {c.tipo:7} {c.referencia:10} {c.situacao:5} "
                      f"{(c.tamanho_bytes or 0):>12} bytes  expira {c.expira_em:%d/%m/%Y}")
        elif args.cmd == "backup-agora":
            c = service.executar_backup(args.tipo)
            print(f"Backup {c.id} ({c.tipo} {c.referencia}): {c.situacao}"
                  + (f" — {c.erro}" if c.erro else ""))
        elif args.cmd == "exportar-backup":
            print(f"Gravado em {service.exportar(args.id, args.arquivo)}")
        else:
            service.restaurar(args.id, args.banco, args.sobrescrever)
            print(f"Backup {args.id} restaurado em {args.banco!r}.")
    except service.ErroBackup as exc:
        raise SystemExit(str(exc)) from exc


def configurar_ia_local(url: str, modelo_chat: str, modelo_embeddings: str) -> None:
    from app.modules.ia import service
    with SessionLocal() as db:
        for linha in service.configurar_ia_local(db, url, modelo_chat, modelo_embeddings, "cli"):
            print(linha)


if __name__ == "__main__":
    main()
