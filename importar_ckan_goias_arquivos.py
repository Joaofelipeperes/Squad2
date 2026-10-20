"""Importação de alta fidelidade: baixa os arquivos dos recursos do portal dadosabertos.go.gov.br
e os envia FISICAMENTE para o CKAN local (recursos do tipo upload), em vez de só guardar o link.

Complementa o importar_ckan_goias.py (que cria organizações, grupos, datasets e recursos com os
mesmos IDs do portal, mas com a URL apontando para o arquivo original). Este script:

  1. garante que o dataset existe (se não existir, cria com o importar_ckan_goias.py);
  2. baixa cada arquivo do portal (em paralelo), respeitando o tamanho máximo;
  3. envia o arquivo para o recurso de mesmo ID no CKAN local (resource_patch com upload);
     a URL original fica guardada no campo `url_origem` do recurso;
  4. restaura `created` e `last_modified` do portal (o CKAN troca o last_modified para "agora"
     quando recebe um arquivo, e o produto final usa esse campo como indicador de atualização).

Pode ser interrompido e rodado de novo: recursos já enviados são pulados (use --refazer para reenviar).
Arquivos maiores que --max-mb continuam como link para o portal.

Uso (dentro do container, como o subir_ambiente.ps1 faz com -ImportarArquivos):
    python3 importar_ckan_goias_arquivos.py                       # todos, até 20 MB por arquivo
    python3 importar_ckan_goias_arquivos.py --max-mb 50 --paralelo 6
    python3 importar_ckan_goias_arquivos.py --limite 10            # só os 10 primeiros datasets
    python3 importar_ckan_goias_arquivos.py --datasets nome-a,nome-b --formatos CSV,XLSX

Variáveis de ambiente: CKAN_API_KEY (token de um SYSADMIN) e CKAN_URL (padrão localhost:5000).

Atenção ao espaço em disco: o CKAN guarda o arquivo enviado e a extensão de auditoria guarda uma
cópia de cada versão (pasta dsaudit_versions). Com o padrão de 20 MB são cerca de 1,9 GB de
arquivos do portal, ou seja, perto de 4 GB no volume do CKAN.
"""
import argparse
import concurrent.futures
import functools
import json
import os
import re
import shutil
import sys
import tempfile
import time
from urllib.parse import unquote, urlparse

import requests

import importar_ckan_goias as base

CKAN_URL = base.CKAN_URL
API_KEY = base.API_KEY
ORIGEM_PADRAO = "https://dadosabertos.go.gov.br"
TENTATIVAS = 3


# ---------------------------------------------------------------------------
# utilitários
# ---------------------------------------------------------------------------

def _mb(n):
    n = int(n or 0)
    return "%.1f MB" % (n / 1e6) if n >= 1e5 else "%.0f KB" % (n / 1e3)


def _nome_arquivo(url, recurso):
    nome = unquote(os.path.basename(urlparse(url).path)) or recurso.get("name") or recurso["id"]
    nome = re.sub(r"[^\w.\-]+", "_", nome, flags=re.UNICODE).strip("._") or recurso["id"]
    return nome[:180]


def _url_download(url, origem):
    """Permite baixar de um espelho (--origem) mantendo o mesmo caminho do portal."""
    if origem and url.startswith(ORIGEM_PADRAO):
        return origem.rstrip("/") + url[len(ORIGEM_PADRAO):]
    return url


def baixar(url, destino, tamanho_esperado, timeout):
    """Baixa com até TENTATIVAS tentativas. Devolve (ok, bytes, mensagem)."""
    ultimo = ""
    for tentativa in range(1, TENTATIVAS + 1):
        try:
            with requests.get(url, stream=True, timeout=timeout,
                              headers={"User-Agent": "importador-ckan-local/1.0"}) as r:
                if r.status_code != 200:
                    ultimo = "HTTP %s" % r.status_code
                    if r.status_code in (403, 404, 410):
                        break                      # não adianta tentar de novo
                else:
                    total = 0
                    with open(destino, "wb") as f:
                        for bloco in r.iter_content(chunk_size=1 << 20):
                            f.write(bloco)
                            total += len(bloco)
                    if total == 0:
                        ultimo = "arquivo vazio"
                    else:
                        aviso = ""
                        if tamanho_esperado and total != int(tamanho_esperado):
                            aviso = (" (tamanho diferente do exportado: %s no portal agora, "
                                     "%s nos metadados)" % (_mb(total), _mb(tamanho_esperado)))
                        return True, total, aviso
        except requests.RequestException as e:
            ultimo = str(e)[:200]
        time.sleep(2 * tentativa)
    return False, 0, ultimo


def enviar(recurso_id, caminho, nome, url_origem):
    """resource_patch com o arquivo: mantém o ID e os demais campos do recurso."""
    with open(caminho, "rb") as f:
        resp = requests.post(
            "%s/api/3/action/resource_patch" % CKAN_URL,
            headers={"Authorization": API_KEY},
            data={"id": recurso_id, "url_origem": url_origem},
            files={"upload": (nome, f)},
            timeout=900,
        )
    if resp.status_code == 200:
        return True, resp.json()["result"]
    return False, resp.text[:300]


def restaurar_datas(dataset_id, originais, tamanhos):
    """Volta created/last_modified dos recursos enviados para os valores do portal e grava o
    tamanho real do arquivo (size) e o mimetype. Uma única package_update por dataset (gera um
    registro 'changed metadata' na auditoria)."""
    pkg = base._resultado(base._get("package_show", id=dataset_id))
    if not pkg:
        return False, "dataset não encontrado"
    mudou = False
    for r in pkg.get("resources", []):
        o = originais.get(r["id"])
        if not o:
            continue
        for campo in ("created", "last_modified"):
            if o.get(campo) and (r.get(campo) or "")[:19] != o[campo][:19]:
                r[campo] = o[campo]
                mudou = True
        if tamanhos.get(r["id"]) and str(r.get("size")) != str(tamanhos[r["id"]]):
            r["size"] = tamanhos[r["id"]]
            mudou = True
        if o.get("mimetype") and not r.get("mimetype"):
            r["mimetype"] = o["mimetype"]
            mudou = True
    if not mudou:
        return True, "datas já conferem"
    resp = base._post("package_update", pkg)
    if resp.status_code == 200:
        return True, "datas restauradas"
    return False, resp.text[:300]


# ---------------------------------------------------------------------------
# importação
# ---------------------------------------------------------------------------

def garantir_dataset(ds, substituir):
    """Cria o dataset (metadados + recursos como link) se ainda não existir no CKAN local."""
    situacao, id_local = base.situacao_no_ckan(ds)
    if situacao == "ok":
        return True, "existente"
    if situacao == "id_divergente":
        if not substituir:
            return False, ("existe com ID diferente do portal (%s); rode com --substituir"
                           % id_local)
        if base._post("dataset_purge", {"id": id_local}).status_code != 200:
            return False, "não foi possível apagar a versão com ID divergente"
    org_id = base.create_or_get_organization(ds["organization"]) if ds.get("organization") else None
    grupos = [g for g in (base.create_or_get_group(g) for g in ds.get("groups", [])) if g]
    resp = base._post("package_create", base.montar_dataset(ds, org_id, grupos))
    if resp.status_code == 200:
        return True, "criado"
    return False, "erro ao criar: %s" % resp.text[:300]


def planejar(ds, local, args):
    """Separa os recursos do dataset em: a baixar, já enviados e mantidos como link."""
    locais = {r["id"]: r for r in local.get("resources", [])}
    baixar_lista, cont = [], {"ja_enviado": 0, "grande": 0, "sem_url": 0, "fora_filtro": 0,
                              "ausente_local": 0}
    for r in ds.get("resources", []):
        url = r.get("url") or ""
        lr = locais.get(r["id"])
        if not url.startswith(("http://", "https://")):
            cont["sem_url"] += 1
            continue
        if args.formatos and (r.get("format") or "").upper() not in args.formatos:
            cont["fora_filtro"] += 1
            continue
        if lr is None:
            cont["ausente_local"] += 1
            continue
        tamanho = int(r.get("size") or 0)
        if tamanho > args.max_mb * 1e6:
            cont["grande"] += 1
            continue
        ja = lr.get("url_type") == "upload" and lr.get("url_origem") == url
        if ja and not args.refazer:
            cont["ja_enviado"] += 1
            continue
        baixar_lista.append(r)
    return baixar_lista, cont


def importar(args):
    with open(args.arquivo, "r", encoding="utf-8") as f:
        datasets = json.load(f)
    if args.datasets:
        alvo = set(args.datasets)
        datasets = [d for d in datasets if d["name"] in alvo or d["id"] in alvo]
    if args.limite:
        datasets = datasets[:args.limite]

    total = {"datasets": 0, "datasets_com_erro": 0, "enviados": 0, "bytes_enviados": 0,
             "ja_enviado": 0, "grande": 0, "sem_url": 0, "fora_filtro": 0, "ausente_local": 0,
             "falha_download": 0, "falha_envio": 0}
    falhas = []
    enviados_agora = set()
    tmp_raiz = tempfile.mkdtemp(prefix="importacao_", dir=args.pasta_temp)
    inicio = time.time()
    try:
        for n, ds in enumerate(datasets, 1):
            total["datasets"] += 1
            ok, msg = garantir_dataset(ds, args.substituir)
            if not ok:
                print("[%d/%d] %s: %s" % (n, len(datasets), ds["name"], msg))
                total["datasets_com_erro"] += 1
                continue
            local = base._resultado(base._get("package_show", id=ds["id"])) or {}
            lista, cont = planejar(ds, local, args)
            for k, v in cont.items():
                total[k] += v
            if not lista:
                print("[%d/%d] %s: nada a enviar (%s)" % (
                    n, len(datasets), ds["name"],
                    ", ".join("%s=%d" % (k, v) for k, v in cont.items() if v) or "sem recursos"))
                continue
            print("[%d/%d] %s: %d arquivo(s), %s" % (
                n, len(datasets), ds["name"], len(lista),
                _mb(sum(int(r.get("size") or 0) for r in lista))))

            # 1) downloads em paralelo
            pasta = os.path.join(tmp_raiz, ds["id"])
            os.makedirs(pasta, exist_ok=True)

            def _baixar(r):
                nome = _nome_arquivo(r["url"], r)
                destino = os.path.join(pasta, r["id"] + "_" + nome)
                ok, tam, msg = baixar(_url_download(r["url"], args.origem), destino,
                                      r.get("size"), args.timeout)
                return r, nome, destino, ok, tam, msg

            with concurrent.futures.ThreadPoolExecutor(max_workers=args.paralelo) as ex:
                baixados = list(ex.map(_baixar, lista))

            # 2) envios em sequência (alterações no mesmo dataset não podem concorrer)
            originais, tamanhos = {}, {}
            for r, nome, destino, ok, tam, msg in baixados:
                if not ok:
                    total["falha_download"] += 1
                    falhas.append((ds["name"], r.get("name") or r["id"], "download: " + msg))
                    print("    x %s: download falhou (%s); continua como link"
                          % (r.get("name") or nome, msg))
                    continue
                ok_env, res = enviar(r["id"], destino, nome, r["url"])
                os.remove(destino)
                if not ok_env:
                    total["falha_envio"] += 1
                    falhas.append((ds["name"], r.get("name") or r["id"], "envio: " + res))
                    print("    x %s: envio falhou: %s" % (r.get("name") or nome, res))
                    continue
                total["enviados"] += 1
                total["bytes_enviados"] += tam
                originais[r["id"]] = r
                enviados_agora.add(r["id"])
                tamanhos[r["id"]] = tam
                print("    + %s (%s)%s" % (r.get("name") or nome, _mb(tam), msg))
            shutil.rmtree(pasta, ignore_errors=True)

            # 3) datas do portal, tamanho e mimetype
            if originais:
                ok_d, msg_d = restaurar_datas(ds["id"], originais, tamanhos)
                if not ok_d:
                    falhas.append((ds["name"], "-", "datas: " + msg_d))
                    print("    x datas não restauradas: %s" % msg_d)
    finally:
        shutil.rmtree(tmp_raiz, ignore_errors=True)

    resumo = dict(total)
    resumo["bytes_enviados"] = _mb(total["bytes_enviados"])
    resumo["duracao_min"] = round((time.time() - inicio) / 60, 1)
    print("\nResumo:", json.dumps(resumo, ensure_ascii=False))
    if total["grande"]:
        print("%d arquivo(s) acima de %d MB continuam como link (aumente com --max-mb)."
              % (total["grande"], args.max_mb))
    if falhas:
        print("Falhas (%d):" % len(falhas))
        for d, r, m in falhas[:30]:
            print("  - %s / %s: %s" % (d, r, m))
        if len(falhas) > 30:
            print("  ... e mais %d" % (len(falhas) - 30))
    return total, datasets, enviados_agora


def verificar(datasets, enviados, amostra=10):
    """Confere numa amostra dos arquivos enviados NESTA execução: recurso do tipo upload,
    ID e datas do portal preservados e arquivo disponível para download no CKAN local.
    (Recursos enviados antes não são conferidos: podem ter sido alterados depois, por
    exemplo pelo simular_alteracoes.py.)"""
    problemas, conferidos = 0, 0
    if not enviados:
        print("[verificação] nenhum arquivo novo enviado nesta execução")
        print("[verificação] OK")
        return 0
    for ds in datasets:
        if conferidos >= amostra:
            break
        local = base._resultado(base._get("package_show", id=ds["id"]))
        if not local:
            continue
        for lr in local.get("resources", []):
            if conferidos >= amostra:
                break
            if lr["id"] not in enviados:
                continue
            o = next((r for r in ds["resources"] if r["id"] == lr["id"]), None)
            if not o:
                continue
            conferidos += 1
            erros = []
            if o.get("last_modified") and (lr.get("last_modified") or "")[:19] != o["last_modified"][:19]:
                erros.append("last_modified %s (portal %s)" % (lr.get("last_modified"), o["last_modified"]))
            if o.get("created") and (lr.get("created") or "")[:19] != o["created"][:19]:
                erros.append("created %s (portal %s)" % (lr.get("created"), o["created"]))
            url = lr["url"].replace(local_site(), CKAN_URL) if lr.get("url") else ""
            try:
                h = requests.get(url, headers={"Authorization": API_KEY}, stream=True, timeout=60)
                tam = int(h.headers.get("Content-Length") or 0)
                h.close()
                if h.status_code != 200:
                    erros.append("download local HTTP %s" % h.status_code)
                elif lr.get("size") and tam and tam != int(lr["size"]):
                    erros.append("tamanho servido %d != registrado %s" % (tam, lr["size"]))
            except requests.RequestException as e:
                erros.append("download local: %s" % e)
            if erros:
                problemas += 1
                print("[verificação] %s / %s: %s" % (ds["name"], lr.get("name"), "; ".join(erros)))
    print("[verificação] %d recurso(s) enviado(s) conferido(s)" % conferidos)
    print("[verificação] OK" if not problemas else "[verificação] %d problema(s)" % problemas)
    return problemas


@functools.lru_cache(maxsize=1)
def local_site():
    st = base._resultado(base._get("status_show")) or {}
    return (st.get("site_url") or CKAN_URL).rstrip("/")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("arquivo", nargs="?", default=base.ARQUIVO_PADRAO)
    p.add_argument("--max-mb", type=int, default=20,
                   help="tamanho máximo por arquivo (padrão 20). Precisa ser <= "
                        "ckan.max_resource_size (CKAN__MAX_RESOURCE_SIZE no docker-compose.yml)")
    p.add_argument("--paralelo", type=int, default=4, help="downloads simultâneos (padrão 4)")
    p.add_argument("--timeout", type=int, default=120, help="timeout de cada download, em segundos")
    p.add_argument("--limite", type=int, default=0, help="processa só os N primeiros datasets")
    p.add_argument("--datasets", type=lambda s: [x.strip() for x in s.split(",") if x.strip()],
                   default=None, help="só estes datasets (nomes ou IDs, separados por vírgula)")
    p.add_argument("--formatos", type=lambda s: {x.strip().upper() for x in s.split(",") if x.strip()},
                   default=None, help="só estes formatos (ex.: CSV,XLSX)")
    p.add_argument("--origem", default="",
                   help="baixa de um espelho em vez de %s (mesmo caminho)" % ORIGEM_PADRAO)
    p.add_argument("--refazer", action="store_true",
                   help="reenvia mesmo os arquivos que já foram enviados")
    p.add_argument("--substituir", action="store_true",
                   help="apaga e recria datasets que existem com ID diferente do portal")
    p.add_argument("--pasta-temp", default=None, help="pasta para os downloads temporários")
    args = p.parse_args()

    if not API_KEY:
        sys.exit("Defina CKAN_API_KEY com o token de um sysadmin.")
    total, processados, enviados = importar(args)
    problemas = verificar(processados, enviados)
    erro = total["datasets_com_erro"] or total["falha_envio"] or problemas
    sys.exit(1 if erro else 0)
