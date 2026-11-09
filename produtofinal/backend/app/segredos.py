"""Gera os segredos do servidor na primeira subida (ADR-0032), sem ninguém rodar comando.

    python -m app.segredos /segredos

Roda no serviço `segredos` do docker-compose.prod.yml, antes do banco, da API e do worker. Cria só
os arquivos que faltam: rodar de novo nunca troca um segredo já gerado (trocar a chave de
criptografia tornaria ilegíveis as chaves de IA salvas; trocar a senha do banco depois da primeira
subida deixaria a API sem acesso a ele).

Os arquivos ficam num volume do Docker montado só em `db`, `api` e `worker`. O docker-entrypoint.sh
da API e do worker os transforma nas variáveis GDA_*; o Postgres lê `db_senha` pelo
POSTGRES_PASSWORD_FILE. Só biblioteca padrão: o módulo não importa a configuração da aplicação,
que exige estes segredos para carregar.
"""
import base64
import os
import secrets
import sys
from pathlib import Path

UID_APLICACAO = 10001  # usuário `gda` da imagem do backend (Dockerfile)


def _fernet() -> str:
    """Chave no formato do `cryptography.fernet.Fernet.generate_key()`."""
    return base64.urlsafe_b64encode(os.urandom(32)).decode()


# arquivo → (gerador, legível por outros usuários?)
SEGREDOS = {
    "secret_key": (lambda: secrets.token_urlsafe(48), False),   # assinatura dos tokens (JWT)
    "encryption_key": (_fernet, False),                        # cifra as chaves de IA e do CKAN
    "lgpd_sal_hash": (lambda: secrets.token_hex(32), False),   # operador "hash" da anonimização
    # O Postgres a lê com o próprio usuário (uid 70), diferente do da aplicação
    "db_senha": (lambda: secrets.token_hex(24), True),
}


def gerar(pasta: Path) -> list[str]:
    """Cria os segredos que faltam em `pasta`. Devolve os nomes criados."""
    pasta.mkdir(parents=True, exist_ok=True)
    criados = []
    for nome, (gerador, publico) in SEGREDOS.items():
        arquivo = pasta / nome
        if arquivo.exists() and arquivo.read_text().strip():
            continue
        arquivo.write_text(gerador())
        arquivo.chmod(0o444 if publico else 0o400)
        if not publico and hasattr(os, "chown") and os.geteuid() == 0:
            os.chown(arquivo, UID_APLICACAO, UID_APLICACAO)
        criados.append(nome)
    return criados


def main() -> None:
    pasta = Path(sys.argv[1] if len(sys.argv) > 1 else "/segredos")
    criados = gerar(pasta)
    if criados:
        print(f"Segredos gerados em {pasta}: {', '.join(criados)}. Faça backup deste volume.")
    else:
        print(f"Segredos já existentes em {pasta}; nada alterado.")


if __name__ == "__main__":
    main()
