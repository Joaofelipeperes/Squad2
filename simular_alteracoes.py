"""Simula alterações variadas em datasets do CKAN local e confere, campo a campo, o que a auditoria
(ckanext-dsaudit) registrou. Serve para popular o histórico com registros diversificados (tipos de
alteração e autores diferentes) e para testar a extensão de ponta a ponta, em escala.

Trabalha SOMENTE com os datasets e recursos da importação de alta fidelidade
(importar_ckan_goias_arquivos.py): não cria recursos nem datasets novos. Rode antes:
    .\\subir_ambiente.ps1 -ImportarArquivos

Usuários de teste (criados ou reaproveitados e vinculados à organização de cada dataset):

    aud-editora-ana     editor          aud-admin-carla   admin
    aud-editor-bruno    editor          aud-membro-davi   member (só leitura)

Catálogo de cenários (python3 simular_alteracoes.py --listar mostra todos). Cada dataset recebe uma
combinação diferente; com 30 datasets ou mais, todos os cenários são aplicados pelo menos uma vez:

  Dataset      título, descrição, autor, e-mail do autor, mantenedor, e-mail do mantenedor,
               licença, versão, URL da fonte, inclusão e remoção de tag, alteração/inclusão/
               remoção de campo extra, inclusão e remoção de grupo, nome na URL (renomeia e volta),
               visibilidade (privado e volta), organização (move e volta), exclusão e restauração
  Recurso      nome, descrição, formato (muda e volta), data de publicação (created),
               data de atualização (last_modified), campo extra
  Conteúdo     troca do arquivo CSV importado (diff linha a linha) e carga dele no DataStore
  Acesso       o membro tenta editar e ler a auditoria (deve ser recusado)

Uso (dentro do container, como o subir_ambiente.ps1 faz com -Simular):
    python3 simular_alteracoes.py                       # 4 datasets
    python3 simular_alteracoes.py --quantidade 100      # escala: 100 datasets
    python3 simular_alteracoes.py --datasets nome-a,nome-b
    python3 simular_alteracoes.py --listar              # mostra o catálogo de cenários
    python3 simular_alteracoes.py --relatorio /tmp/relatorio.json

Os datasets escolhidos são ALTERADOS de verdade (é o objetivo). Para voltar o arquivo e as datas de
um recurso ao estado do portal:
    python3 importar_ckan_goias_arquivos.py --datasets <nome> --refazer

Ao começar, remove os recursos de teste criados por versões anteriores deste script
("Amostra tabular (DataStore)" e "Nota técnica (teste)").

Variáveis de ambiente: CKAN_API_KEY (token de um SYSADMIN) e CKAN_URL (padrão localhost:5000).
"""
import argparse
import collections
import csv
import datetime
import io
import json
import os
import re
import secrets
import sys

import requests

CKAN_URL = os.environ.get("CKAN_URL", "http://localhost:5000").rstrip("/")
ADMIN_TOKEN = os.environ.get("CKAN_API_KEY", "").strip()

USUARIOS = [
    # (nome, nome completo, papel na organização)
    ("aud-editora-ana", "Ana Editora (teste de auditoria)", "editor"),
    ("aud-editor-bruno", "Bruno Editor (teste de auditoria)", "editor"),
    ("aud-admin-carla", "Carla Administradora (teste de auditoria)", "admin"),
    ("aud-membro-davi", "Davi Membro (teste de auditoria)", "member"),
]
RESIDUOS = ("Amostra tabular (DataStore)", "Nota técnica (teste)")
SUFIXO = " (revisado)"


class ErroApi(Exception):
    def __init__(self, action, status, corpo):
        super().__init__("%s -> HTTP %s: %s" % (action, status, corpo[:300]))
        self.status = status


class Pular(Exception):
    """O cenário não se aplica a este dataset (ex.: não há tag para remover)."""


def api(action, payload=None, token=None, get=False):
    url = "%s/api/3/action/%s" % (CKAN_URL, action)
    h = {"Authorization": token or ADMIN_TOKEN}
    if get:
        r = requests.get(url, params=payload or {}, headers=h, timeout=120)
    else:
        r = requests.post(url, json=payload or {}, headers=h, timeout=600)
    if r.status_code != 200:
        raise ErroApi(action, r.status_code, r.text)
    return r.json()["result"]


def api_upload(action, campos, nome, conteudo, token):
    r = requests.post("%s/api/3/action/%s" % (CKAN_URL, action),
                      headers={"Authorization": token}, data=campos,
                      files={"upload": (nome, conteudo)}, timeout=600)
    if r.status_code != 200:
        raise ErroApi(action, r.status_code, r.text)
    return r.json()["result"]


def pacote(pkg_id):
    return api("package_show", {"id": pkg_id}, get=True)


def atualizar_dataset(pkg_id, campos, token=None):
    """Altera campos do dataset com package_show + package_update (o mesmo caminho da
    interface web). Não usa package_patch: no CKAN 2.9 ele chama o package_update do core
    diretamente e a extensão de auditoria não registra a alteração."""
    pkg = api("package_show", {"id": pkg_id}, token, get=True)
    pkg.update(campos)
    return api("package_update", pkg, token)


def agora():
    return datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def carimbo():
    return datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")


# ---------------------------------------------------------------------------
# usuários de teste e limpeza de versões anteriores
# ---------------------------------------------------------------------------

def preparar_usuarios():
    tokens = {}
    for nome, completo, _papel in USUARIOS:
        try:
            api("user_show", {"id": nome}, get=True)
        except ErroApi:
            api("user_create", {"name": nome, "fullname": completo,
                                "email": "%s@teste.local" % nome,
                                "password": secrets.token_urlsafe(16) + "Aa1!"})
            print("  usuário criado: %s" % nome)
        tok = api("api_token_create", {"user": nome, "name": "simulacao-%s" % carimbo()})
        tokens[nome] = tok["token"] if isinstance(tok, dict) else tok
    return tokens


def vincular_na_org(org_id):
    for nome, _completo, papel in USUARIOS:
        api("organization_member_create", {"id": org_id, "username": nome, "role": papel})


def limpar_residuos():
    """Remove recursos de teste criados por versões anteriores deste script."""
    removidos = 0
    for nome in RESIDUOS:
        busca = api("resource_search", {"query": "name:%s" % nome, "limit": 1000}, get=True)
        for res in busca.get("results", []):
            if res.get("name") != nome:
                continue
            try:
                api("resource_delete", {"id": res["id"]})
                removidos += 1
            except ErroApi as e:
                print("  não foi possível remover o recurso %s: %s" % (res["id"], e))
    for nome in api("package_list", get=True):
        if nome.startswith("auditoria-cenario-"):
            api("dataset_purge", {"id": nome})
            removidos += 1
    if removidos:
        print("  %d recurso(s)/dataset(s) de teste de versões anteriores removido(s)" % removidos)


# ---------------------------------------------------------------------------
# escolha dos datasets
# ---------------------------------------------------------------------------

def ler_csv(texto, delim):
    linhas = list(csv.reader(io.StringIO(texto), delimiter=delim))
    cab = linhas[0] if linhas else []
    dados = [l for l in linhas[1:] if any(c.strip() for c in l)]
    return cab, dados


def chave_unica(cab, dados):
    for i, _col in enumerate(cab):
        vals = [l[i] if i < len(l) else "" for l in dados]
        if all(v.strip() for v in vals) and len(set(vals)) == len(vals):
            return i
    return None


def _csv_do_recurso(res):
    """Baixa o arquivo de um recurso do CKAN local. Devolve (texto, delimitador, chave) ou None.
    Só aceita CSV de texto com pelo menos 6 linhas e uma coluna de valores únicos (necessária
    para casar as linhas no diff e para a chave primária do DataStore)."""
    url = res.get("url") or ""
    m = re.search(r"/dataset/.+", url)
    if not m:
        return None
    r = requests.get(CKAN_URL + m.group(0), headers={"Authorization": ADMIN_TOKEN}, timeout=120)
    if r.status_code != 200 or not r.content or b"\x00" in r.content[:4096] \
            or r.content[:2] == b"PK":
        return None
    texto = None
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            texto = r.content.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if texto is None:
        return None
    amostra = texto[:65536]
    delim = ";" if amostra.count(";") > amostra.count(",") else ","
    cab, dados = ler_csv(texto, delim)
    if len(dados) < 6 or len(cab) < 2:
        return None
    k = chave_unica(cab, dados)
    if k is None:
        return None
    return texto, delim, k


def escolher_datasets(args):
    """Datasets com pelo menos um recurso da importação de arquivos. Para cada um, guarda o
    recurso usado nos cenários de recurso e, quando houver, um CSV com coluna de valores únicos
    para os cenários de conteúdo (troca de arquivo e DataStore)."""
    escolhidos = []
    nomes = args.datasets or sorted(api("package_list", get=True))
    for nome in nomes:
        if len(escolhidos) >= args.quantidade:
            break
        try:
            pkg = pacote(nome)
        except ErroApi:
            print("  dataset não encontrado: %s" % nome)
            continue
        if not pkg.get("owner_org") or pkg.get("state") != "active":
            continue
        importados = [r for r in pkg.get("resources", [])
                      if r.get("url_type") == "upload" and r.get("url_origem")]
        if not importados:
            continue
        csv_ok = None
        for res in importados:
            if (res.get("format") or "").upper() != "CSV":
                continue
            if int(res.get("size") or 0) > args.max_mb * 1e6:
                continue
            achado = _csv_do_recurso(res)
            if achado:
                csv_ok = (res,) + achado
                break
        recurso = csv_ok[0] if csv_ok else importados[0]
        escolhidos.append({"pkg": pkg, "recurso": recurso, "csv": csv_ok})
    return escolhidos


# ---------------------------------------------------------------------------
# cenários: cada um devolve um texto curto e registra o que espera na auditoria
# ---------------------------------------------------------------------------

def _alterar_valor(v):
    try:
        n = float(v.replace(",", "."))
        novo = n + 1
        s = ("%d" % novo) if novo == int(novo) and "." not in v and "," not in v else ("%.2f" % novo)
        return s.replace(".", ",") if "," in v else s
    except ValueError:
        return (v + " (corrigido)") if v else "corrigido"


def _alternar_sufixo(texto, sufixo=SUFIXO):
    texto = texto or ""
    return texto[:-len(sufixo)] if texto.endswith(sufixo) else texto + sufixo


def _data_deslocada(valor, dias):
    try:
        base = datetime.datetime.strptime((valor or "")[:19], "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        base = datetime.datetime(2025, 1, 1)
    return (base + datetime.timedelta(days=dias)).strftime("%Y-%m-%dT%H:%M:%S")


class Contexto:
    """Dados de um dataset durante a simulação e o que se espera encontrar na auditoria."""

    def __init__(self, item, i, tokens, orgs, grupos, licencas):
        self.pkg_id = item["pkg"]["id"]
        self.nome = item["pkg"]["name"]
        self.res_id = item["recurso"]["id"]
        self.csv = item["csv"]
        self.i = i
        self.tokens = tokens
        autores = [tokens["aud-editora-ana"], tokens["aud-editor-bruno"], tokens["aud-admin-carla"]]
        self.autores = autores[i % 3:] + autores[:i % 3]
        self.orgs, self.grupos, self.licencas = orgs, grupos, licencas
        self.esperado = collections.Counter()   # (escopo, campo) -> nº mínimo de registros
        self.texto_csv = self.csv[1] if self.csv else None

    def autor(self, n):
        return self.autores[n % len(self.autores)]

    def espera(self, escopo, campo, vezes=1):
        self.esperado[(escopo, campo)] += vezes

    def pkg(self, token=None):
        return api("package_show", {"id": self.pkg_id}, token, get=True)

    def res(self):
        return api("resource_show", {"id": self.res_id}, get=True)


# --- dataset -------------------------------------------------------------------------

def _campo_texto(campo, rotulo, gerar):
    def cenario(c):
        atual = c.pkg().get(campo)
        novo = gerar(atual, c)
        atualizar_dataset(c.pkg_id, {campo: novo}, c.autor(0))
        c.espera("dataset", campo)
        return "%s: '%s' -> '%s'" % (rotulo, (atual or "")[:40], novo[:40])
    return cenario


cen_titulo = _campo_texto("title", "título", lambda v, c: _alternar_sufixo(v))
cen_descricao = _campo_texto("notes", "descrição",
                             lambda v, c: (v or "") + "\n\nRevisão de auditoria em %s." % agora())
cen_autor = _campo_texto("author", "autor",
                         lambda v, c: "Equipe de Dados %d (revisão %s)" % (c.i + 1, carimbo()))
cen_email_autor = _campo_texto("author_email", "e-mail do autor",
                               lambda v, c: "dados.%s@exemplo.go.gov.br" % carimbo())
cen_mantenedor = _campo_texto("maintainer", "mantenedor",
                              lambda v, c: "Gerência de Dados (revisão %s)" % carimbo())
cen_email_mantenedor = _campo_texto("maintainer_email", "e-mail do mantenedor",
                                    lambda v, c: "gerencia.%s@exemplo.go.gov.br" % carimbo())
cen_versao = _campo_texto("version", "versão", lambda v, c: "2.%d.%s" % (c.i + 1, carimbo()))
cen_url_fonte = _campo_texto("url", "URL da fonte",
                             lambda v, c: "https://dadosabertos.go.gov.br/fonte-revisada/%s" % carimbo())


def cen_licenca(c):
    atual = c.pkg().get("license_id") or ""
    opcoes = [l for l in c.licencas if l != atual]
    novo = "cc-by-sa" if "cc-by-sa" in opcoes else opcoes[0]
    atualizar_dataset(c.pkg_id, {"license_id": novo}, c.autor(1))
    c.espera("dataset", "license_id")
    return "licença: '%s' -> '%s'" % (atual, novo)


def cen_tag_inclusao(c):
    tags = [{"name": t["name"]} for t in c.pkg().get("tags", [])]
    nova = "auditoria-teste" if not any(t["name"] == "auditoria-teste" for t in tags) \
        else "revisao-%s" % carimbo()
    atualizar_dataset(c.pkg_id, {"tags": tags + [{"name": nova}]}, c.autor(1))
    c.espera("dataset", "tags")
    return "tag incluída: %s" % nova


def cen_tag_remocao(c):
    tags = [{"name": t["name"]} for t in c.pkg().get("tags", [])]
    removiveis = [t for t in tags if t["name"] != "auditoria-teste"]
    if not removiveis:
        raise Pular("o dataset não tem tag para remover")
    tira = removiveis[-1]["name"]
    atualizar_dataset(c.pkg_id, {"tags": [t for t in tags if t["name"] != tira]}, c.autor(2))
    c.espera("dataset", "tags")
    return "tag removida: %s" % tira


def cen_extra_alteracao(c):
    extras = c.pkg().get("extras", [])
    alvo = next((e for e in extras if e["key"] != "revisao_auditoria"), None)
    if alvo is None:
        raise Pular("o dataset não tem campo extra para alterar")
    novo = _alternar_sufixo(alvo["value"])
    novos = [dict(e, value=novo) if e["key"] == alvo["key"] else e for e in extras]
    atualizar_dataset(c.pkg_id, {"extras": novos}, c.autor(0))
    c.espera("dataset", "extras.%s" % alvo["key"])
    return "extra '%s': '%s' -> '%s'" % (alvo["key"], alvo["value"][:30], novo[:30])


def cen_extra_inclusao(c):
    extras = [e for e in c.pkg().get("extras", []) if e["key"] != "revisao_auditoria"]
    extras.append({"key": "revisao_auditoria", "value": agora()})
    atualizar_dataset(c.pkg_id, {"extras": extras}, c.autor(1))
    c.espera("dataset", "extras.revisao_auditoria")
    return "extra 'revisao_auditoria' incluído/atualizado"


def cen_extra_remocao(c):
    extras = c.pkg().get("extras", [])
    alvo = next((e for e in extras if e["key"] not in ("revisao_auditoria", "Atualização")), None)
    if alvo is None:
        raise Pular("o dataset não tem campo extra removível")
    atualizar_dataset(c.pkg_id, {"extras": [e for e in extras if e["key"] != alvo["key"]]},
                      c.autor(2))
    c.espera("dataset", "extras.%s" % alvo["key"])
    return "extra '%s' removido" % alvo["key"]


def cen_grupo_inclusao(c):
    atuais = [g["name"] for g in c.pkg().get("groups", [])]
    livres = [g for g in c.grupos if g not in atuais]
    if not livres:
        raise Pular("não há grupo disponível para incluir")
    atualizar_dataset(c.pkg_id, {"groups": [{"name": g} for g in atuais + [livres[0]]]})
    c.espera("dataset", "groups")
    return "grupo incluído: %s (sysadmin)" % livres[0]


def cen_grupo_remocao(c):
    atuais = [g["name"] for g in c.pkg().get("groups", [])]
    if not atuais:
        raise Pular("o dataset não está em nenhum grupo")
    atualizar_dataset(c.pkg_id, {"groups": [{"name": g} for g in atuais[:-1]]})
    c.espera("dataset", "groups")
    return "grupo removido: %s (sysadmin)" % atuais[-1]


def cen_nome_url(c):
    nome = c.pkg()["name"]
    temp = (nome[:80] + "-rev")[:100]
    atualizar_dataset(c.pkg_id, {"name": temp}, c.autor(2))
    atualizar_dataset(c.pkg_id, {"name": nome}, c.autor(2))
    c.espera("dataset", "name", 2)
    return "nome na URL: '%s' -> '%s' -> volta" % (nome, temp)


def cen_visibilidade(c):
    atualizar_dataset(c.pkg_id, {"private": True}, c.tokens["aud-admin-carla"])
    atualizar_dataset(c.pkg_id, {"private": False}, c.tokens["aud-admin-carla"])
    c.espera("dataset", "private", 2)
    return "privado e depois público"


def cen_organizacao(c):
    origem = c.pkg()["owner_org"]
    destino = next((o for o in c.orgs if o != origem), None)
    if destino is None:
        raise Pular("só existe uma organização")
    atualizar_dataset(c.pkg_id, {"owner_org": destino})
    atualizar_dataset(c.pkg_id, {"owner_org": origem})
    c.espera("dataset", "owner_org", 2)
    return "movido para outra organização e de volta (sysadmin)"


def cen_exclusao(c):
    api("package_delete", {"id": c.pkg_id})
    atualizar_dataset(c.pkg_id, {"state": "active"})
    c.espera("dataset", "state", 2)
    return "excluído e restaurado (sysadmin)"


# --- recurso -------------------------------------------------------------------------

def _recurso(campo, rotulo, gerar, autor=0):
    def cenario(c):
        atual = c.res().get(campo)
        novo = gerar(atual, c)
        api("resource_patch", {"id": c.res_id, campo: novo}, c.autor(autor))
        c.espera("resource", campo)
        return "recurso, %s: '%s' -> '%s'" % (rotulo, str(atual or "")[:40], str(novo)[:40])
    return cenario


cen_rec_nome = _recurso("name", "nome", lambda v, c: _alternar_sufixo(v), 1)
cen_rec_descricao = _recurso("description", "descrição",
                             lambda v, c: "Descrição revisada em %s." % agora(), 2)
cen_rec_publicacao = _recurso("created", "data de publicação",
                              lambda v, c: _data_deslocada(v, -30), 0)
cen_rec_atualizacao = _recurso("last_modified", "data de atualização",
                               lambda v, c: _data_deslocada(v, 1), 1)
cen_rec_extra = _recurso("observacao_auditoria", "campo extra",
                         lambda v, c: "Conferido em %s" % agora(), 2)


def cen_rec_formato(c):
    atual = c.res().get("format") or ""
    temp = "TXT" if atual.upper() != "TXT" else "CSV"
    api("resource_patch", {"id": c.res_id, "format": temp}, c.autor(0))
    api("resource_patch", {"id": c.res_id, "format": atual}, c.autor(0))
    c.espera("resource", "format", 2)
    return "recurso, formato: '%s' -> '%s' -> volta" % (atual, temp)


# --- conteúdo --------------------------------------------------------------------------

def cen_troca_arquivo(c):
    if not c.csv:
        raise Pular("o dataset não tem CSV importado com coluna de valores únicos")
    res, texto, delim, k = c.res(), c.texto_csv, c.csv[2], c.csv[3]
    cab, dados = ler_csv(texto, delim)
    api("resource_patch", {"id": res["id"], "chave_auditoria": cab[k]}, c.autor(2))
    col = next((x for x in range(len(cab)) if x != k), 0)
    col2 = next((x for x in range(len(cab)) if x not in (k, col)), col)
    novo = [list(l) + [""] * (len(cab) - len(l)) for l in dados]
    novo[0][col] = _alterar_valor(novo[0][col])
    novo[1][col2] = _alterar_valor(novo[1][col2])
    novo.pop(2)
    extra = list(novo[-1])
    existentes = set(l[k] for l in novo)
    base, n = extra[k], 1
    while True:
        cand = str(int(base) + 100000 * n) if base.isdigit() else "%s-NOVO%d" % (base, n)
        if cand not in existentes:
            break
        n += 1
    extra[k] = cand
    novo.append(extra)
    saida = io.StringIO()
    w = csv.writer(saida, delimiter=delim, lineterminator="\n")
    w.writerow(cab)
    w.writerows(novo)
    c.texto_csv = saida.getvalue()
    nome = (os.path.basename(res.get("url") or "") or "dados.csv").split("?")[0]
    api_upload("resource_patch", {"id": res["id"]}, nome, c.texto_csv.encode("utf-8"), c.autor(2))
    c.espera("arquivo", "replaced")
    return ("arquivo trocado: 2 células alteradas (%s, %s), 1 linha removida, 1 incluída; "
            "chave '%s'" % (cab[col], cab[col2], cab[k]))


def _limitar_bytes(texto, maximo=60):
    """Corta pelo tamanho em bytes UTF-8 (o PostgreSQL limita nomes de coluna a 63 bytes,
    e letras acentuadas ocupam 2) sem partir um caractere, e tira espaços das pontas."""
    return texto.encode("utf-8")[:maximo].decode("utf-8", "ignore").strip()


def _nomes_campos(cab):
    """Nomes de coluna aceitos pelo DataStore, o mais próximos possível do original."""
    usados, nomes = set(), []
    for i, col in enumerate(cab):
        base = re.sub(r"[\x00-\x1f]+", " ", col or "").replace('"', "")
        base = re.sub(r"\s+", " ", base).strip()
        if base.startswith("_"):
            base = "c" + base
        base = _limitar_bytes(base) or "coluna_%d" % (i + 1)
        final, n = base, 1
        while final.lower() in usados:
            n += 1
            sufixo = "_%d" % n
            final = _limitar_bytes(base, 60 - len(sufixo)) + sufixo
        usados.add(final.lower())
        nomes.append(final)
    return nomes


def cen_datastore(c):
    """Carrega o CSV do próprio recurso no DataStore dele, sem criar recurso (como o portal faz
    com 1.705 recursos). A extensão registra a criação da tabela e as linhas carregadas.
    Edições linha a linha no DataStore não são feitas: a extensão só as audita em tabelas
    criadas direto pela API (url_type = 'datastore'), e o portal não tem nenhuma."""
    if not c.csv:
        raise Pular("o dataset não tem CSV importado com coluna de valores únicos")
    if c.res().get("datastore_active"):
        raise Pular("o recurso já tem DataStore (carregado em rodada anterior)")
    cab, dados = ler_csv(c.texto_csv, c.csv[2])
    campos = _nomes_campos(cab)
    k = c.csv[3]
    registros = [{col: (l[j] if j < len(l) else None) for j, col in enumerate(campos)}
                 for l in dados]
    api("datastore_create", {
        "resource_id": c.res_id, "force": True,
        "fields": [{"id": col, "type": "text"} for col in campos],
        "primary_key": [campos[k]], "records": registros,
    }, c.autor(0))
    c.espera("datastore", "created")
    renomeadas = [x for x, o in zip(campos, cab) if x != o]
    txt = "%d linhas carregadas no DataStore do recurso (chave '%s')" % (len(registros), campos[k])
    if renomeadas:
        txt += "; colunas renomeadas: %s" % ", ".join(renomeadas)
    return txt


# --- acesso ----------------------------------------------------------------------------

def cen_acesso_negado(c):
    membro, editor = c.tokens["aud-membro-davi"], c.tokens["aud-editora-ana"]
    out = []
    try:
        api("package_update", dict(c.pkg(), notes="não deveria gravar"), membro)
        out.append("FALHA: o membro conseguiu editar")
    except ErroApi as e:
        out.append("edição pelo membro recusada (HTTP %s)" % e.status)
    try:
        api("dsaudit_activity_list", {"id": c.pkg_id}, membro, get=True)
        out.append("FALHA: o membro leu a auditoria")
    except ErroApi as e:
        out.append("leitura pelo membro recusada (HTTP %s)" % e.status)
    api("dsaudit_activity_list", {"id": c.pkg_id, "limit": 1}, editor, get=True)
    out.append("leitura pela editora permitida")
    return "; ".join(out)


# (código, grupo, descrição, função, de quantos em quantos datasets roda)
#   frequência 1 = entra no rodízio normal; N > 1 = só a cada N datasets (cenários pesados)
CATALOGO = [
    ("titulo", "dataset", "título", cen_titulo, 1),
    ("descricao", "dataset", "descrição", cen_descricao, 1),
    ("autor", "dataset", "autor", cen_autor, 1),
    ("email_autor", "dataset", "e-mail do autor", cen_email_autor, 1),
    ("mantenedor", "dataset", "mantenedor", cen_mantenedor, 1),
    ("email_mantenedor", "dataset", "e-mail do mantenedor", cen_email_mantenedor, 1),
    ("licenca", "dataset", "licença", cen_licenca, 1),
    ("versao", "dataset", "versão", cen_versao, 1),
    ("url_fonte", "dataset", "URL da fonte", cen_url_fonte, 1),
    ("tag_inclusao", "dataset", "inclusão de tag", cen_tag_inclusao, 1),
    ("tag_remocao", "dataset", "remoção de tag", cen_tag_remocao, 1),
    ("extra_alteracao", "dataset", "alteração de campo extra", cen_extra_alteracao, 1),
    ("extra_inclusao", "dataset", "inclusão de campo extra", cen_extra_inclusao, 1),
    ("extra_remocao", "dataset", "remoção de campo extra", cen_extra_remocao, 1),
    ("grupo_inclusao", "dataset", "inclusão em grupo", cen_grupo_inclusao, 1),
    ("grupo_remocao", "dataset", "remoção de grupo", cen_grupo_remocao, 1),
    ("visibilidade", "dataset", "privado e volta a público", cen_visibilidade, 1),
    ("nome_url", "dataset", "nome na URL (renomeia e volta)", cen_nome_url, 10),
    ("organizacao", "dataset", "organização (move e volta)", cen_organizacao, 10),
    ("exclusao", "dataset", "exclusão e restauração", cen_exclusao, 10),
    ("rec_nome", "recurso", "nome do recurso", cen_rec_nome, 1),
    ("rec_descricao", "recurso", "descrição do recurso", cen_rec_descricao, 1),
    ("rec_publicacao", "recurso", "data de publicação do recurso (created)", cen_rec_publicacao, 1),
    ("rec_atualizacao", "recurso", "data de atualização do recurso (last_modified)",
     cen_rec_atualizacao, 1),
    ("rec_extra", "recurso", "campo extra do recurso", cen_rec_extra, 1),
    ("rec_formato", "recurso", "formato do recurso (muda e volta)", cen_rec_formato, 10),
    ("troca_arquivo", "conteudo", "troca do arquivo (diff linha a linha)", cen_troca_arquivo, 1),
    ("datastore", "conteudo", "carga do arquivo no DataStore", cen_datastore, 1),
    ("acesso_negado", "acesso", "membro tenta editar e ler a auditoria", cen_acesso_negado, 5),
]
POR_DATASET = {"dataset": 6, "recurso": 2}   # quantos do rodízio cada dataset recebe


def plano(i, total):
    """Cenários do dataset i: um rodízio que distribui todos os cenários entre os datasets,
    mais os pesados a cada N datasets e os de conteúdo sempre que possível. Com uma amostra
    pequena (até 10 datasets), os pesados também entram para que todos apareçam."""
    escolhidos = []
    for grupo, n in POR_DATASET.items():
        leves = [x for x in CATALOGO if x[1] == grupo and x[4] == 1]
        inicio = (i * n) % len(leves)
        escolhidos += [leves[(inicio + j) % len(leves)] for j in range(n)]
    for x in CATALOGO:
        if x[4] > 1:
            deslocamento = CATALOGO.index(x) % x[4]
            if i % x[4] == deslocamento or (total <= x[4] and i == total - 1):
                escolhidos.append(x)
    escolhidos += [x for x in CATALOGO if x[1] == "conteudo"]
    return escolhidos


# ---------------------------------------------------------------------------
# conferência
# ---------------------------------------------------------------------------

def conferir(c, inicio, nomes_usuarios):
    res = api("dsaudit_activity_list", {"id": c.pkg_id, "limit": 500}, get=True)
    novos = [a for a in res["results"] if a["timestamp"][:19].replace("T", " ") >= inicio]
    por_tipo = collections.Counter(a["activity_type"] for a in novos)
    por_autor = collections.Counter(nomes_usuarios.get(a["user_id"], a["user_id"]) for a in novos)
    vistos = collections.Counter()
    for a in novos:
        d = a["data"]
        if a["activity_type"] == "changed metadata":
            campos = set()
            for ch in d.get("changes", []):
                escopo = "dataset" if ch.get("scope") == "dataset" else "resource"
                if escopo == "resource" and ch.get("resource_id") != c.res_id:
                    continue
                campos.add((escopo, ch.get("field")))
            for k in campos:
                vistos[k] += 1
        elif a["activity_type"] == "changed resource file" and d.get("method") == "replaced":
            st = collections.Counter(ch.get("status") for ch in d.get("changes", []))
            if st.get("updated") and st.get("deleted") and st.get("inserted"):
                vistos[("arquivo", "replaced")] += 1
        elif a["activity_type"] == "created datastore":
            vistos[("datastore", "created")] += 1
    problemas = []
    for (escopo, campo), n in sorted(c.esperado.items()):
        if vistos[(escopo, campo)] < n:
            problemas.append("esperado(s) %d registro(s) de %s '%s', encontrado(s) %d"
                             % (n, escopo, campo, vistos[(escopo, campo)]))
    return novos, por_tipo, por_autor, problemas


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--quantidade", type=int, default=4, help="quantos datasets alterar (padrão 4)")
    p.add_argument("--datasets", type=lambda s: [x.strip() for x in s.split(",") if x.strip()],
                   default=None, help="datasets específicos (nomes ou IDs, separados por vírgula)")
    p.add_argument("--max-mb", type=float, default=2,
                   help="tamanho máximo do CSV usado nos cenários de conteúdo (padrão 2 MB)")
    p.add_argument("--sysadmin", default="admin",
                   help="nome do sysadmin dono do CKAN_API_KEY (só para o relatório)")
    p.add_argument("--relatorio", default="", help="grava o resultado completo em JSON")
    p.add_argument("--listar", action="store_true", help="mostra o catálogo de cenários e sai")
    args = p.parse_args()
    if args.listar:
        for cod, grupo, desc, _f, freq in CATALOGO:
            print("  %-17s %-9s %s%s" % (cod, grupo, desc,
                                        "" if freq == 1 else " (a cada %d datasets)" % freq))
        return 0
    if not ADMIN_TOKEN:
        sys.exit("Defina CKAN_API_KEY com o token de um sysadmin.")

    inicio = agora()
    print("Simulação iniciada em %s UTC" % inicio)
    limpar_residuos()
    print("Usuários de teste:")
    tokens = preparar_usuarios()
    nomes_usuarios = {api("user_show", {"id": u[0]}, get=True)["id"]: u[0] for u in USUARIOS}
    try:
        admin = api("user_show", {"id": args.sysadmin}, get=True)
        nomes_usuarios[admin["id"]] = "%s (sysadmin)" % args.sysadmin
    except ErroApi:
        pass
    orgs = [o["id"] for o in api("organization_list", {"all_fields": True}, get=True)]
    grupos = api("group_list", get=True)
    licencas = [l["id"] for l in api("license_list", get=True)]

    print("Escolhendo datasets (com recursos da importação de arquivos)...")
    alvos = escolher_datasets(args)
    if not alvos:
        sys.exit("Nenhum dataset com recursos importados. Rode antes a importação de arquivos: "
                 ".\\subir_ambiente.ps1 -ImportarArquivos")
    if len(alvos) < args.quantidade:
        print("  só %d dataset(s) com recursos importados (importe mais com -ImportarArquivos)"
              % len(alvos))
    print("  %d dataset(s); %d com CSV para os cenários de conteúdo"
          % (len(alvos), sum(1 for a in alvos if a["csv"])))

    cobertura = {cod: collections.Counter() for cod, *_ in CATALOGO}
    relatorio, total_problemas, total_registros = [], 0, 0
    for i, item in enumerate(alvos):
        c = Contexto(item, i, tokens, orgs, grupos, licencas)
        print("\n[%d/%d] %s" % (i + 1, len(alvos), c.nome))
        vincular_na_org(item["pkg"]["owner_org"])
        passos = []
        for cod, _grupo, _desc, func, _freq in plano(i, len(alvos)):
            try:
                txt = func(c)
                cobertura[cod]["aplicado"] += 1
                passos.append({"cenario": cod, "resultado": txt})
                print("    %-16s %s" % (cod, txt))
            except Pular as e:
                cobertura[cod]["pulado"] += 1
                passos.append({"cenario": cod, "pulado": str(e)})
            except ErroApi as e:
                cobertura[cod]["erro"] += 1
                passos.append({"cenario": cod, "erro": str(e)})
                print("    %-16s ERRO: %s" % (cod, e))
        novos, por_tipo, por_autor, problemas = conferir(c, inicio, nomes_usuarios)
        problemas += [p_["erro"] for p_ in passos if "erro" in p_]
        problemas += [p_["resultado"] for p_ in passos if "FALHA" in str(p_.get("resultado", ""))]
        total_problemas += len(problemas)
        total_registros += len(novos)
        print("    auditoria: %d registro(s) | por autor: %s" % (
            len(novos), ", ".join("%s=%d" % kv for kv in sorted(por_autor.items()))))
        for prob in problemas:
            print("    PROBLEMA: %s" % prob)
        relatorio.append({"dataset": c.nome, "passos": passos, "registros": len(novos),
                          "por_tipo": por_tipo, "por_autor": por_autor, "problemas": problemas})

    print("\nCobertura por cenário (aplicado / pulado por não se aplicar / erro):")
    nao_aplicados = []
    for cod, grupo, desc, _f, _freq in CATALOGO:
        k = cobertura[cod]
        print("  %-17s %4d  %4d  %4d   %s" % (cod, k["aplicado"], k["pulado"], k["erro"], desc))
        if not k["aplicado"]:
            nao_aplicados.append(cod)
    if nao_aplicados:
        print("  Cenários não aplicados nesta rodada: %s (use mais datasets)"
              % ", ".join(nao_aplicados))
    print("\nResumo: %d dataset(s), %d registro(s) de auditoria, %d problema(s)"
          % (len(relatorio), total_registros, total_problemas))
    print("Consulta: %s/api/3/action/dsaudit_activity_list?id=<dataset>" % CKAN_URL)
    if args.relatorio:
        with open(args.relatorio, "w", encoding="utf-8") as f:
            json.dump({"inicio_utc": inicio, "cobertura": cobertura, "datasets": relatorio},
                      f, ensure_ascii=False, indent=1)
        print("Relatório: %s" % args.relatorio)
    print("[simulação] OK" if not total_problemas else "[simulação] COM PROBLEMAS")
    return 1 if total_problemas else 0


if __name__ == "__main__":
    sys.exit(main())
