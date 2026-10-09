"""Importa no CKAN local (Docker deste repositório) os metadados do portal dadosabertos.go.gov.br.

Fonte: metadados_ckan_goias.json (exportação do portal).

O CKAN local serve de "portal de testes" para o produto final (produtofinal/). Por isso a cópia
precisa ser fiel nos pontos que o produto final usa:
  * IDs de dataset e de recurso iguais aos do portal (o produto final vincula tudo pelo ID);
  * `created` e `last_modified` dos recursos preservados (indicador de atualização real).

Uso (PowerShell):
    $env:CKAN_API_KEY = "<token do usuário admin>"       # CKAN > usuário > API Tokens
    $env:CKAN_URL     = "http://localhost:5000"          # opcional (padrão)
    python importar_ckan_goias.py                        # importa o que ainda não existe
    python importar_ckan_goias.py --substituir           # apaga e reimporta datasets que
                                                         # existem com ID diferente do portal

O token precisa ser de um SYSADMIN: só sysadmin pode criar dataset com ID definido.
"""
import argparse
import json
import os
import sys

import requests

CKAN_URL = os.environ.get("CKAN_URL", "http://localhost:5000").rstrip("/")
API_KEY = os.environ.get("CKAN_API_KEY", "").strip()
ARQUIVO_PADRAO = "metadados_ckan_goias.json"


def _headers():
    return {"Authorization": API_KEY, "Content-Type": "application/json"}


def _get(action, **params):
    return requests.get(f"{CKAN_URL}/api/3/action/{action}", params=params,
                        headers=_headers(), timeout=60)


def _post(action, payload):
    return requests.post(f"{CKAN_URL}/api/3/action/{action}", json=payload,
                         headers=_headers(), timeout=300)


def _resultado(resp):
    """Devolve o `result` de uma resposta bem-sucedida ou None."""
    if resp.status_code == 200:
        return resp.json().get("result")
    return None


def create_or_get_organization(org_data):
    """Cria a organização (com o mesmo ID do portal) caso não exista e retorna o ID."""
    existente = _resultado(_get("organization_show", id=org_data["name"]))
    if existente:
        return existente["id"]

    payload = {
        "id": org_data.get("id"),
        "name": org_data["name"],
        "title": org_data.get("title", org_data["name"]),
        "description": org_data.get("description", ""),
        "image_url": org_data.get("image_url", ""),
    }
    res = _post("organization_create", {k: v for k, v in payload.items() if v is not None})
    criada = _resultado(res)
    if criada:
        return criada["id"]
    print(f"Erro ao criar organização {org_data['name']}: {res.text}")
    return None


def create_or_get_group(group_data):
    """Cria o grupo (categoria) caso não exista e retorna a referência para o dataset."""
    if _resultado(_get("group_show", id=group_data["name"])):
        return {"name": group_data["name"]}

    payload = {
        "id": group_data.get("id"),
        "name": group_data["name"],
        "title": group_data.get("title", group_data["name"]),
        "description": group_data.get("description", ""),
    }
    res = _post("group_create", {k: v for k, v in payload.items() if v is not None})
    if _resultado(res):
        return {"name": group_data["name"]}
    print(f"Erro ao criar grupo {group_data['name']}: {res.text}")
    return None


def montar_recurso(res):
    """Recurso com ID e datas do portal. Campos vazios são omitidos (o CKAN valida as datas),
    exceto `url`: a coluna é NOT NULL no CKAN 2.9 e recurso sem URL (há alguns no portal) daria
    "Internal Server Error" no package_create."""
    recurso = {
        "id": res.get("id"),                       # mesmo ID do portal
        "name": res.get("name"),
        "description": res.get("description", ""),
        "format": res.get("format"),
        "url": res.get("url"),                     # mantém o vínculo com o arquivo original
        "created": res.get("created"),             # data real de criação no portal
        "last_modified": res.get("last_modified"),  # indicador de atualização real
    }
    recurso = {k: v for k, v in recurso.items() if v not in (None, "")}
    recurso["url"] = res.get("url") or ""
    return recurso


def montar_dataset(ds, org_id, group_list):
    return {
        "id": ds["id"],                            # mesmo ID do portal (exige sysadmin)
        "name": ds["name"],
        "title": ds["title"],
        "notes": ds.get("notes", ""),
        "author": ds.get("author", ""),
        "author_email": ds.get("author_email", ""),
        "maintainer": ds.get("maintainer", ""),
        "maintainer_email": ds.get("maintainer_email", ""),
        "license_id": ds.get("license_id", ""),
        "private": ds.get("private", False),
        "owner_org": org_id,
        "groups": group_list,
        "tags": [{"name": t["name"]} for t in ds.get("tags", [])],
        "extras": ds.get("extras", []),
        "resources": [montar_recurso(r) for r in ds.get("resources", [])],
    }


def situacao_no_ckan(ds):
    """'ok' (já existe com o ID do portal), 'id_divergente' (existe pelo name com outro ID,
    importado pela versão antiga deste script) ou 'ausente'."""
    if _resultado(_get("package_show", id=ds["id"])):
        return "ok", None
    pelo_nome = _resultado(_get("package_show", id=ds["name"]))
    if pelo_nome:
        return "id_divergente", pelo_nome["id"]
    return "ausente", None


def import_datasets(filepath, substituir=False):
    """Processa o JSON e faz a ingestão dos pacotes na instância local."""
    with open(filepath, "r", encoding="utf-8") as f:
        datasets = json.load(f)

    cont = {"importados": 0, "ja_existiam": 0, "id_divergente": 0, "substituidos": 0, "erros": 0}

    for ds in datasets:
        print(f"Processando dataset: {ds['name']}...")

        situacao, id_local = situacao_no_ckan(ds)
        if situacao == "ok":
            print("  -> Já existe com o ID do portal.")
            cont["ja_existiam"] += 1
            continue
        if situacao == "id_divergente":
            if not substituir:
                print(f"  -> ATENÇÃO: existe com ID diferente do portal ({id_local}). "
                      "Rode com --substituir para reimportar com o ID correto.")
                cont["id_divergente"] += 1
                continue
            res = _post("dataset_purge", {"id": id_local})
            if res.status_code != 200:
                print(f"  -> Erro ao apagar a versão antiga: {res.text}")
                cont["erros"] += 1
                continue
            print("  -> Versão antiga (ID diferente) apagada; reimportando.")
            cont["substituidos"] += 1

        # 1. Organização
        org_id = None
        if ds.get("organization"):
            org_id = create_or_get_organization(ds["organization"])

        # 2. Grupos
        group_list = [g for g in (create_or_get_group(g) for g in ds.get("groups", [])) if g]

        # 3. Dataset com recursos
        resp = _post("package_create", montar_dataset(ds, org_id, group_list))
        if resp.status_code == 200:
            print(f"  -> Sucesso! Dataset '{ds['name']}' importado.")
            cont["importados"] += 1
        else:
            print(f"  -> Erro ao importar dataset '{ds['name']}': {resp.text}")
            cont["erros"] += 1

    print("\nResumo:", json.dumps(cont, ensure_ascii=False))
    if cont["id_divergente"]:
        print("Há datasets com ID diferente do portal. Rode novamente com --substituir.")
    return cont


def verificar(filepath, cont=None, amostra=5):
    """Confere a carga: todos os datasets do arquivo no banco do CKAN, índice de busca (Solr)
    completo e, numa amostra, ID e last_modified dos recursos iguais aos do portal."""
    with open(filepath, "r", encoding="utf-8") as f:
        datasets = json.load(f)
    problemas = 0
    if cont and cont.get("erros"):
        print(f"[verificação] {cont['erros']} dataset(s) com erro na importação (veja acima)")
        problemas += 1

    # 1) presentes no banco do CKAN (package_list lê o banco: datasets públicos e ativos)
    nomes_banco = set(_resultado(_get("package_list")) or [])
    faltando = [ds["name"] for ds in datasets if ds["name"] not in nomes_banco]
    print(f"[verificação] no banco do CKAN: {len(datasets) - len(faltando)} de {len(datasets)} "
          f"datasets do arquivo")
    if faltando:
        print(f"[verificação] ausentes: {', '.join(faltando[:10])}"
              f"{' ...' if len(faltando) > 10 else ''}")
        problemas += 1

    # 2) índice de busca: é o package_search que o produto final usa na coleta
    busca = _resultado(_get("package_search", rows=0)) or {}
    no_indice = busca.get("count", 0)
    print(f"[verificação] no índice de busca: {no_indice} de {len(nomes_banco)} datasets do banco")
    if no_indice < len(nomes_banco):
        print("[verificação] ÍNDICE INCOMPLETO: rode "
              "'docker compose exec ckan ckan -c /srv/app/ckan.ini search-index rebuild -o'")
        problemas += 1

    # 3) amostra: IDs e last_modified dos recursos
    for ds in datasets[:amostra]:
        local = _resultado(_get("package_show", id=ds["id"]))
        if not local:
            print(f"[verificação] {ds['name']}: não encontrado pelo ID do portal")
            problemas += 1
            continue
        locais = {r["id"]: r for r in local.get("resources", [])}
        for r in ds.get("resources", []):
            lr = locais.get(r["id"])
            if not lr:
                print(f"[verificação] recurso {r['id']} sem o ID do portal")
                problemas += 1
            elif r.get("last_modified") and not (lr.get("last_modified") or "").startswith(
                    r["last_modified"][:19]):
                print(f"[verificação] recurso {r['id']}: last_modified "
                      f"{lr.get('last_modified')} (portal: {r['last_modified']})")
                problemas += 1
    print("[verificação] OK" if not problemas else f"[verificação] {problemas} problema(s)")
    return problemas


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("arquivo", nargs="?", default=ARQUIVO_PADRAO)
    parser.add_argument("--substituir", action="store_true",
                        help="apaga (dataset_purge) e reimporta datasets que existem com ID "
                             "diferente do portal")
    args = parser.parse_args()

    if not API_KEY:
        sys.exit("Defina a variável de ambiente CKAN_API_KEY com o token de um sysadmin "
                 "(CKAN > usuário admin > API Tokens).")

    resumo = import_datasets(args.arquivo, substituir=args.substituir)
    sys.exit(1 if verificar(args.arquivo, resumo) else 0)
