"""Comandos administrativos.

    python -m app.cli gerar-chave
    python -m app.cli criar-usuario --email a@b.gov.br --nome "Fulana" --papel administrador
    python -m app.cli criar-usuario --email x@seduc.go.gov.br --nome "Servidor" \
        --papel orgao_publicador --orgao <ckan_id_da_organizacao>
    python -m app.cli papeis                  # lista papéis e permissões
    python -m app.cli coletar                 # roda uma coleta agora, em primeiro plano
    python -m app.cli semear-ia               # cria perfis de IA de exemplo (mock + ollama)
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
    u.add_argument("--orgao", default=None, help="ckan_id da organização (escopo de órgão)")
    sub.add_parser("papeis")
    sub.add_parser("coletar")
    sub.add_parser("semear-ia")
    args = p.parse_args()

    if args.cmd == "gerar-chave":
        print(generate_key())
    elif args.cmd == "criar-usuario":
        from app.modules.acesso.service import criar_usuario
        senha = getpass.getpass("Senha (mín. 8 caracteres): ")
        with SessionLocal() as db:
            user = criar_usuario(db, args.email, args.nome, senha, args.papel, args.orgao)
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


if __name__ == "__main__":
    main()
