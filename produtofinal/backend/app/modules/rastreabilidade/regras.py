"""Regras puras da rastreabilidade: transformam uma atividade da auditoria do CKAN
(extensão ckanext-dsaudit) em evento da linha do tempo, em linguagem humana (PBI-85).

Sem banco e sem HTTP — reaproveitáveis numa extensão CKAN (ADR-0004).

Privacidade (AGENTS.md, regra 4): de arquivos e do DataStore guardamos só contagens e nomes de
colunas, nunca valores de linhas. De metadados (campos do dataset e dos recursos) guardamos
valor anterior e novo, que são metadados de publicação.
"""
import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime

INCLUSAO = "inclusao"
ALTERACAO = "alteracao"
EXCLUSAO = "exclusao"
PRIVACAO = "privacao"
RECURSO_ATUALIZADO = "recurso_atualizado"

# origem do evento
ORIGEM_AUDITORIA = "auditoria_ckan"        # extensão ckanext-dsaudit: autor e data exatos
ORIGEM_COMPARACAO = "comparacao_coletas"   # diferença entre duas fotografias do cadastro
ORIGEM_NATIVA = "atividade_nativa"         # atividade do CKAN sem registro da extensão

# ordem e rótulos da tela (#screen-traceability do Protótipo V1)
TIPOS: dict[str, str] = {
    INCLUSAO: "Inclusão",
    ALTERACAO: "Alteração",
    EXCLUSAO: "Exclusão",
    PRIVACAO: "Privação",
    RECURSO_ATUALIZADO: "Recurso atualizado",
}

META_TYPE = "changed metadata"
FILE_TYPE = "changed resource file"
DATASTORE_TYPES = ("created datastore", "changed datastore", "deleted datastore")

MAX_DETALHES = 60          # itens de detalhe guardados por evento
MAX_VALOR = 300            # caracteres de cada valor anterior/novo
MAX_CAMPOS_NO_RESUMO = 4

ROTULOS_DATASET = {
    "title": "título", "name": "nome na URL", "notes": "descrição", "author": "autor",
    "author_email": "e-mail do autor", "maintainer": "mantenedor",
    "maintainer_email": "e-mail do mantenedor", "license_id": "licença", "version": "versão",
    "url": "URL da fonte", "owner_org": "organização", "private": "visibilidade",
    "state": "situação", "tags": "tags", "groups": "grupos", "type": "tipo",
}
ROTULOS_RECURSO = {
    "name": "nome", "description": "descrição", "format": "formato", "url": "URL",
    "url_type": "tipo de URL", "created": "data de publicação",
    "last_modified": "última modificação", "size": "tamanho", "mimetype": "tipo MIME",
    "hash": "hash", "state": "situação",
}


@dataclass
class EventoClassificado:
    tipo: str
    resumo: str
    recurso_id: str | None = None
    recurso_nome: str | None = None
    detalhes: list[dict] = field(default_factory=list)
    # há diff linha a linha no CKAN (troca de arquivo comparada ou upsert com valores
    # anteriores): a tela busca sob demanda, sem gravar os valores (LGPD)
    tem_diff: bool = False


def parse_timestamp(valor: str | None) -> datetime | None:
    """`timestamp` da atividade: ISO sem fuso, em UTC (padrão do CKAN 2.9)."""
    if not valor:
        return None
    dt = datetime.fromisoformat(valor)
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def rotulo_campo(escopo: str, campo: str) -> str:
    if campo.startswith("extras."):
        return f'campo extra "{campo[len("extras."):]}"'
    mapa = ROTULOS_DATASET if escopo == "dataset" else ROTULOS_RECURSO
    return mapa.get(campo, campo)


def _texto(valor) -> str | None:
    if valor is None or valor == "":
        return None
    t = str(valor)
    return t if len(t) <= MAX_VALOR else t[:MAX_VALOR - 1] + "…"


def _eh_verdadeiro(valor) -> bool:
    return str(valor).strip().lower() in ("true", "1", "sim")


def _lista_campos(rotulos: list[str]) -> str:
    unicos = list(dict.fromkeys(rotulos))
    if len(unicos) <= MAX_CAMPOS_NO_RESUMO:
        return ", ".join(unicos)
    resto = len(unicos) - MAX_CAMPOS_NO_RESUMO
    return f"{', '.join(unicos[:MAX_CAMPOS_NO_RESUMO])} e mais {resto}"


def _detalhe_meta(c: dict) -> dict:
    escopo = c.get("scope") or "dataset"
    return {
        "escopo": escopo,
        "recurso": c.get("resource_name") if escopo == "resource" else None,
        "situacao": c.get("status"),  # recurso: added | changed | removed
        "campo": rotulo_campo(escopo, c.get("field") or ""),
        "anterior": _texto(c.get("old")),
        "novo": _texto(c.get("new")),
    }


def _metadados(data: dict) -> list[EventoClassificado]:
    metodo = data.get("method")
    mudancas = data.get("changes") or []
    if metodo == "created":
        n_rec = len({c.get("resource_id") for c in mudancas if c.get("scope") == "resource"})
        extra = f", com {n_rec} recurso(s)" if n_rec else ""
        return [EventoClassificado(INCLUSAO, f"Dataset incluído no portal{extra}.",
                                   detalhes=_detalhes_meta(mudancas))]
    if metodo == "deleted":
        return [EventoClassificado(EXCLUSAO, "Dataset excluído do portal.",
                                   detalhes=_detalhes_meta(mudancas))]

    privado = next((c for c in mudancas
                    if c.get("scope") == "dataset" and c.get("field") == "private"), None)
    if privado is None or not _eh_verdadeiro(privado.get("new")):
        return [_alteracao(mudancas, data.get("resource_id"))]
    # Privação vira um evento próprio; o que mais mudou na mesma gravação (título, autor,
    # recursos...) vira um evento de Alteração separado, na mesma data.
    eventos = [EventoClassificado(PRIVACAO, "Dataset tornado privado (deixou de ser público).",
                                  detalhes=_detalhes_meta([privado]))]
    demais = [c for c in mudancas if c is not privado]
    if demais:
        eventos.append(_alteracao(demais, data.get("resource_id")))
    return eventos


def _detalhes_meta(mudancas: list[dict]) -> list[dict]:
    return [_detalhe_meta(c) for c in mudancas][:MAX_DETALHES]


def _alteracao(mudancas: list[dict], recurso_id: str | None) -> EventoClassificado:
    """Evento de Alteração com os campos do dataset e dos recursos que mudaram."""
    rids = {c.get("resource_id") for c in mudancas if c.get("resource_id")}
    if not recurso_id and len(rids) == 1 and all(c.get("resource_id") for c in mudancas):
        recurso_id = next(iter(rids))
    recurso_nome = next((c.get("resource_name") for c in mudancas
                         if recurso_id and c.get("resource_id") == recurso_id), None)
    partes: list[str] = []
    privado = next((c for c in mudancas
                    if c.get("scope") == "dataset" and c.get("field") == "private"), None)
    if privado is not None:
        partes.append("dataset tornado público")
    campos_ds = [rotulo_campo("dataset", c.get("field") or "") for c in mudancas
                 if c.get("scope") == "dataset" and c.get("field") != "private"]
    if campos_ds:
        partes.append(f"alterado(s) no dataset: {_lista_campos(campos_ds)}")
    por_recurso: dict[tuple[str, str], list[dict]] = {}
    for c in mudancas:
        if c.get("scope") == "resource":
            chave = (c.get("resource_id") or "", c.get("resource_name") or "recurso")
            por_recurso.setdefault(chave, []).append(c)
    for (_, nome), itens in por_recurso.items():
        situacao = itens[0].get("status")
        if situacao == "added":
            partes.append(f'recurso "{nome}" incluído')
        elif situacao == "removed":
            partes.append(f'recurso "{nome}" removido')
        else:
            campos = [rotulo_campo("resource", c.get("field") or "") for c in itens]
            partes.append(f'recurso "{nome}": {_lista_campos(campos)}')
    resumo = "; ".join(partes) or "Metadados alterados"
    return EventoClassificado(ALTERACAO, resumo[0].upper() + resumo[1:] + ".",
                              recurso_id=recurso_id, recurso_nome=recurso_nome,
                              detalhes=_detalhes_meta(mudancas))


def _contar(changes: list[dict]) -> dict[str, int]:
    cont = {"inserted": 0, "updated": 0, "deleted": 0}
    for c in changes or []:
        if c.get("status") in cont:
            cont[c["status"]] += 1
    return cont


def _frase_linhas(cont: dict[str, int]) -> str:
    partes = []
    if cont["updated"]:
        partes.append(f"{cont['updated']} linha(s) alterada(s)")
    if cont["inserted"]:
        partes.append(f"{cont['inserted']} incluída(s)")
    if cont["deleted"]:
        partes.append(f"{cont['deleted']} removida(s)")
    return ", ".join(partes) if partes else "nenhuma linha diferente"


def _colunas_alteradas(changes: list[dict]) -> list[str]:
    cols: list[str] = []
    for c in changes or []:
        if c.get("status") == "updated":
            cols.extend(str(f.get("field")) for f in c.get("fields") or [] if f.get("field"))
    return list(dict.fromkeys(cols))


def _arquivo(data: dict) -> EventoClassificado:
    versao = (data.get("version") or {})
    anterior = (data.get("previous_version") or {})
    nome_arq = versao.get("filename") or "arquivo"
    detalhes: list[dict] = [{"campo": "arquivo", "anterior": anterior.get("filename"),
                             "novo": versao.get("filename")},
                            {"campo": "versão", "anterior": _texto(anterior.get("version")),
                             "novo": _texto(versao.get("version"))}]
    if data.get("method") != "replaced":
        resumo = f'Arquivo "{nome_arq}" enviado (versão {versao.get("version", 1)})'
        if data.get("rows_new") is not None:
            resumo += f", {data['rows_new']} linha(s)"
        return EventoClassificado(RECURSO_ATUALIZADO, resumo + ".",
                                  recurso_id=data.get("resource_id"), detalhes=detalhes)
    resumo = (f'Arquivo substituído (versão {anterior.get("version", "?")} → '
              f'{versao.get("version", "?")})')
    tem_diff = False
    if data.get("diff_error"):
        resumo += "; sem comparação linha a linha"
        detalhes.append({"campo": "observação", "anterior": None,
                         "novo": _texto(data["diff_error"])})
    else:
        cont = _contar(data.get("changes"))
        resumo += f": {_frase_linhas(cont)}"
        tem_diff = bool(data.get("changes"))
        cols = _colunas_alteradas(data.get("changes"))
        if cols:
            detalhes.append({"campo": "colunas com valores alterados", "anterior": None,
                             "novo": _texto(", ".join(cols))})
        for nome, qtd in (("linhas alteradas", cont["updated"]),
                          ("linhas incluídas", cont["inserted"]),
                          ("linhas removidas", cont["deleted"])):
            if qtd:
                detalhes.append({"campo": nome, "anterior": None, "novo": str(qtd)})
    return EventoClassificado(RECURSO_ATUALIZADO, resumo + ".",
                              recurso_id=data.get("resource_id"), detalhes=detalhes,
                              tem_diff=tem_diff)


def _datastore(activity_type: str, data: dict) -> EventoClassificado:
    rid = data.get("resource_id")
    campos = [str(f.get("id")) for f in data.get("fields") or [] if f.get("id")]
    detalhes: list[dict] = []
    if campos:
        detalhes.append({"campo": "colunas", "anterior": None,
                         "novo": _texto(", ".join(campos))})
    if activity_type == "created datastore":
        return EventoClassificado(RECURSO_ATUALIZADO,
                                  f"Tabela criada no DataStore com {len(campos)} coluna(s).",
                                  recurso_id=rid, detalhes=detalhes)
    if activity_type == "deleted datastore":
        total = data.get("total")
        if total is None and data.get("records") is not None:
            total = len(data["records"])
        if data.get("filters") is None and not total:
            resumo = "Tabela do DataStore excluída."
        else:
            resumo = f"{total or 0} linha(s) excluída(s) do DataStore."
        return EventoClassificado(RECURSO_ATUALIZADO, resumo, recurso_id=rid, detalhes=detalhes)
    if data.get("changes") is not None:
        cont = _contar(data["changes"])
        cols = _colunas_alteradas(data["changes"])
        if cols:
            detalhes.append({"campo": "colunas com valores alterados", "anterior": None,
                             "novo": _texto(", ".join(cols))})
        resumo = f"DataStore atualizado: {_frase_linhas(cont)}."
        return EventoClassificado(RECURSO_ATUALIZADO, resumo, recurso_id=rid, detalhes=detalhes,
                                  tem_diff=bool(data["changes"]))
    n = len(data.get("records") or [])
    resumo = f"{n} linha(s) carregada(s) no DataStore."
    return EventoClassificado(RECURSO_ATUALIZADO, resumo, recurso_id=rid, detalhes=detalhes)


def classificar(activity_type: str, data: dict | None) -> list[EventoClassificado]:
    """Atividade da auditoria → eventos da linha do tempo (lista vazia = tipo não monitorado).
    Em geral um evento; a privação acompanhada de outras mudanças gera dois (Privação e
    Alteração), na ordem em que serão gravados."""
    data = data or {}
    if activity_type == META_TYPE:
        return _metadados(data)
    if activity_type == FILE_TYPE:
        return [_arquivo(data)]
    if activity_type in DATASTORE_TYPES:
        return [_datastore(activity_type, data)]
    return []


def titulo_do_pacote(data: dict | None) -> str | None:
    """Título do dataset gravado na própria atividade de metadados (data.package)."""
    pkg = (data or {}).get("package") or {}
    return pkg.get("title") or pkg.get("name")


# ------------------------------------------------------------------ diff sob demanda
MAX_LINHAS_DIFF = 500


def linhas_do_diff(changes: list[dict] | None,
                   limite: int | None = MAX_LINHAS_DIFF) -> tuple[list[dict], int]:
    """`changes` de uma troca de arquivo ou de um upsert no DataStore → linhas para a tela:
    chave (texto), situação (incluída, alterada, removida) e campos com antes → depois.
    Devolve (linhas até `limite`, total). `limite=None` traz todas (usado no download em CSV).
    Só para exibição/exportação: nada disso é gravado."""
    rotulos = {"inserted": "incluída", "updated": "alterada", "deleted": "removida"}
    linhas = []
    for c in changes or []:
        chave = c.get("key") or {}
        chave_txt = ", ".join(f"{k}={v}" for k, v in chave.items()) if isinstance(chave, dict) \
            else str(chave)
        linhas.append({
            "chave": chave_txt,
            "situacao": rotulos.get(c.get("status"), c.get("status") or ""),
            "campos": [{"campo": str(f.get("field")), "anterior": _texto(f.get("old")),
                        "novo": _texto(f.get("new"))} for f in c.get("fields") or []],
        })
    return (linhas if limite is None else linhas[:limite]), len(linhas)


# ------------------------------------------------------------------ cadastro dos órgãos
# A extensão de auditoria não registra alterações em órgãos. Elas são detectadas comparando a
# fotografia do cadastro (organization_list com all_fields e include_extras) entre coletas.
ORGAO_IGNORAR = {
    "id", "package_count", "display_name", "image_display_url", "created", "is_organization",
    "type", "approval_status", "num_followers", "users", "packages", "groups", "tags",
    "revision_id", "extras", "state",
}
ROTULOS_ORGAO = {
    "title": "título", "name": "nome na URL", "description": "descrição", "image_url": "imagem",
}


def payload_orgao(org: dict) -> dict:
    """Cadastro do órgão achatado e comparável: campos do próprio órgão (inclusive campos
    personalizados de primeiro nível) e cada campo extra como "extras.<chave>"."""
    out: dict = {}
    for k, v in (org or {}).items():
        if k in ORGAO_IGNORAR:
            continue
        out[k] = json.dumps(v, ensure_ascii=False, sort_keys=True) if isinstance(v, (list, dict)) \
            else v
    for e in (org or {}).get("extras") or []:
        if e.get("key") and e.get("state", "active") == "active":
            out[f"extras.{e['key']}"] = e.get("value")
    return out


def hash_payload(payload: dict) -> str:
    texto = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def rotulo_campo_orgao(campo: str) -> str:
    if campo.startswith("extras."):
        return f'campo extra "{campo[len("extras."):]}"'
    return ROTULOS_ORGAO.get(campo, campo)


def _vazio(v) -> bool:
    return v is None or v == ""


def comparar_orgao(antes: dict | None, depois: dict | None) -> EventoClassificado | None:
    """Duas fotografias do cadastro de um órgão → evento (None = nada mudou).
    antes None = órgão novo (Inclusão); depois None = saiu da listagem (Exclusão)."""
    if antes is None and depois is None:
        return None
    if antes is None:
        return EventoClassificado(INCLUSAO, "Órgão incluído no portal.",
                                  detalhes=_detalhes_orgao({}, depois))
    if depois is None:
        return EventoClassificado(EXCLUSAO, "Órgão excluído do portal.",
                                  detalhes=_detalhes_orgao(antes, {}))
    detalhes = _detalhes_orgao(antes, depois)
    if not detalhes:
        return None
    campos = _lista_campos([d["campo"] for d in detalhes])
    return EventoClassificado(ALTERACAO, f"Alterado(s) no cadastro do órgão: {campos}.",
                              detalhes=detalhes)


def _detalhes_orgao(antes: dict, depois: dict) -> list[dict]:
    detalhes = []
    for campo in sorted(set(antes) | set(depois)):
        a, d = antes.get(campo), depois.get(campo)
        if (_vazio(a) and _vazio(d)) or str(a) == str(d):
            continue
        detalhes.append({"escopo": "orgao", "recurso": None, "situacao": None,
                         "campo": rotulo_campo_orgao(campo),
                         "anterior": _texto(a), "novo": _texto(d)})
    return detalhes[:MAX_DETALHES]


# atividades nativas do CKAN sobre o próprio órgão (usuário e data, sem os campos extras)
ATIVIDADES_DO_ORGAO = ("new organization", "changed organization", "deleted organization")


def autoria_no_intervalo(atividades: list[dict], desde: datetime | None,
                         ate: datetime) -> list[tuple[datetime, str]]:
    """(data, user_id) das atividades do próprio órgão com desde < data <= ate, da mais antiga
    para a mais recente. `desde` None = sem limite inferior (órgão sem fotografia anterior)."""
    saida = []
    for a in atividades:
        if a.get("activity_type") not in ATIVIDADES_DO_ORGAO or not a.get("user_id"):
            continue
        quando = parse_timestamp(a.get("timestamp"))
        if quando is None or quando > ate or (desde is not None and quando <= desde):
            continue
        saida.append((quando, a["user_id"]))
    return sorted(saida)


def texto_autoria(autoria: list[tuple[datetime, str]]) -> str:
    """"admin em 22/10/2026 20:41; ana em 22/10/2026 21:03" (horário de Brasília)."""
    from zoneinfo import ZoneInfo

    fuso = ZoneInfo("America/Sao_Paulo")
    return _texto("; ".join(f"{nome} em {quando.astimezone(fuso):%d/%m/%Y %H:%M}"
                            for quando, nome in autoria)) or ""


# ------------------------------------------------------------------ ações fora da auditoria
# Toda edição de dataset pelo `package_update` gera, na mesma operação, a atividade nativa do
# CKAN ("changed package") e a da extensão ("changed metadata"), com centésimos de segundo de
# diferença. Ações que não passam pelo `package_update` (Make public / Make private / Delete em
# lote na página da organização, package_patch pela API) geram só a nativa: são as "órfãs".
ATIVIDADES_NATIVAS_DATASET = ("new package", "changed package", "deleted package")
JANELA_PAR_SEGUNDOS = 2.0


def nativas_orfas(nativas: list[dict], auditadas: list[datetime]) -> list[dict]:
    """Atividades nativas de dataset sem atividade da extensão do mesmo dataset a menos de
    JANELA_PAR_SEGUNDOS — as demais já estão na linha do tempo pela extensão (duplicadas)."""
    orfas = []
    for a in nativas:
        if a.get("activity_type") not in ATIVIDADES_NATIVAS_DATASET:
            continue
        quando = parse_timestamp(a.get("timestamp"))
        if quando is None:
            continue
        if any(abs((quando - t).total_seconds()) < JANELA_PAR_SEGUNDOS for t in auditadas):
            continue
        orfas.append(a)
    return sorted(orfas, key=lambda a: parse_timestamp(a["timestamp"]))


def versao_anterior_a_acao(versao: dict | None, quando: datetime | None) -> bool:
    """A versão guardada na atividade é a de ANTES da ação (ação em lote na organização)?

    Make private / Make public / Delete em lote (`bulk_update_*` do CKAN 2.9) alteram o banco por
    SQL direto, sem mudar `metadata_modified`, e montam a versão da atividade com `package_show`,
    que devolve o cache do Solr ainda não reindexado: a versão gravada é a de antes da ação. Nas
    demais atividades (package_update/package_patch) `metadata_modified` acompanha a atividade.
    Assim, `metadata_modified` mais de JANELA_PAR_SEGUNDOS antes da atividade = ação em lote."""
    modificado = parse_timestamp((versao or {}).get("metadata_modified"))
    if modificado is None or quando is None:
        return False
    return (quando - modificado).total_seconds() > JANELA_PAR_SEGUNDOS


def visibilidade(valor) -> bool | None:
    """Valor de `private` como gravado nos detalhes ("True"/"False") → bool; vazio → None."""
    if valor is None or valor == "":
        return None
    return _eh_verdadeiro(valor)


def resolver_visibilidade(orfas: list[datetime], marcos: list[tuple[datetime, bool | None, bool]],
                          atual: bool | None, base: bool | None
                          ) -> list[tuple[bool | None, bool | None]]:
    """(privado antes, privado depois) de cada órfã, em ordem de data.

    - antes: o estado conhecido mais recente antes dela (mudança de visibilidade registrada pela
      extensão ou órfã já resolvida); sem nenhum, `base` (o dataset estava na busca pública na
      coleta anterior → False).
    - depois: o "antes" da próxima mudança registrada pela extensão; sem nenhuma, a visibilidade
      atual. Se outra órfã vier antes dessa mudança, o estado intermediário não é conhecido."""
    marcos = sorted(marcos, key=lambda m: m[0])
    resolvidas: list[tuple[datetime, bool | None]] = []
    saida = []
    for i, t in enumerate(orfas):
        conhecidos = [(m[0], m[2]) for m in marcos if m[0] < t] + \
                     [(rt, v) for rt, v in resolvidas if v is not None]
        antes = max(conhecidos, key=lambda c: c[0])[1] if conhecidos else base
        proximo = next((m for m in marcos if m[0] > t), None)
        proxima_orfa = orfas[i + 1] if i + 1 < len(orfas) else None
        if proxima_orfa is not None and (proximo is None or proxima_orfa < proximo[0]):
            depois = None
        elif proximo is not None:
            depois = proximo[1]
        else:
            depois = atual
        resolvidas.append((t, depois))
        saida.append((antes, depois))
    return saida


def _rotulo_visibilidade(privado: bool | None) -> str | None:
    return None if privado is None else str(bool(privado))


# mesma seleção de campos da extensão (ckanext-dsaudit), para o resultado ter o mesmo formato
PACOTE_IGNORAR = {
    "metadata_modified", "metadata_created", "revision_id", "num_resources", "num_tags",
    "organization", "tracking_summary", "relationships_as_object", "relationships_as_subject",
    "isopen", "license_url", "license_title", "resources", "tags", "groups", "extras",
}
RECURSO_IGNORAR = {"metadata_modified", "revision_id", "datastore_active", "position",
                   "package_id", "tracking_summary", "id"}


def _valor(v):
    return json.dumps(v, ensure_ascii=False, sort_keys=True, default=str) \
        if isinstance(v, (list, dict)) else v


def _pacote_achatado(pkg: dict) -> dict:
    out = {k: _valor(v) for k, v in (pkg or {}).items() if k not in PACOTE_IGNORAR}
    out["tags"] = ", ".join(sorted(t.get("display_name") or t.get("name") or ""
                                   for t in (pkg or {}).get("tags") or [])) or None
    out["groups"] = ", ".join(sorted(g.get("name") or ""
                                     for g in (pkg or {}).get("groups") or [])) or None
    for e in (pkg or {}).get("extras") or []:
        out[f"extras.{e.get('key')}"] = _valor(e.get("value"))
    return out


def _iguais(a, b) -> bool:
    if _vazio(a) or _vazio(b):
        return _vazio(a) and _vazio(b)
    return a == b or str(a) == str(b)


def mudancas_pacote(antes: dict, depois: dict) -> list[dict]:
    """Diferenças entre duas versões completas de um dataset (fotografias das atividades nativas),
    no mesmo formato de `changes` da extensão: campos do dataset e dos recursos."""
    mudancas = []
    fa, fd = _pacote_achatado(antes), _pacote_achatado(depois)
    for k in sorted(set(fa) | set(fd)):
        if not _iguais(fa.get(k), fd.get(k)):
            mudancas.append({"scope": "dataset", "field": k, "old": fa.get(k), "new": fd.get(k)})
    ra = {r["id"]: r for r in (antes or {}).get("resources") or [] if r.get("id")}
    rd = {r["id"]: r for r in (depois or {}).get("resources") or [] if r.get("id")}
    for rid in list(ra) + [r for r in rd if r not in ra]:
        a, d = ra.get(rid), rd.get(rid)
        nome = (d or a).get("name") or rid
        status = "added" if a is None else "removed" if d is None else "changed"
        ca = {k: _valor(v) for k, v in (a or {}).items() if k not in RECURSO_IGNORAR}
        cd = {k: _valor(v) for k, v in (d or {}).items() if k not in RECURSO_IGNORAR}
        for k in sorted(set(ca) | set(cd)):
            if not _iguais(ca.get(k), cd.get(k)):
                mudancas.append({"scope": "resource", "resource_id": rid, "resource_name": nome,
                                 "status": status, "field": k, "old": ca.get(k),
                                 "new": cd.get(k)})
    return mudancas


OBS_FORA_DA_AUDITORIA = ("Ação registrada só pelo CKAN, fora da edição auditada pela extensão "
                         "(ex.: Make public/Make private/Delete em lote na página da organização "
                         "ou package_patch pela API).")


def classificar_orfa(activity_type: str, antes: bool | None, depois: bool | None,
                     mudancas: list[dict] | None = None) -> list[EventoClassificado]:
    """Atividade nativa sem registro da extensão → eventos. Com `mudancas` (diferença entre as
    versões guardadas pelo CKAN), mesmo tratamento da extensão (privação vira evento próprio);
    sem elas, só a visibilidade (o que as ações em lote alteram) pode ser deduzida."""
    obs = {"escopo": None, "recurso": None, "situacao": None, "campo": "observação",
           "anterior": None, "novo": OBS_FORA_DA_AUDITORIA}
    if activity_type == "deleted package":
        return [EventoClassificado(EXCLUSAO, "Dataset excluído do portal (fora da edição "
                                   "auditada, ex.: exclusão em lote na organização).",
                                   detalhes=[obs])]
    if activity_type == "new package":
        return [EventoClassificado(INCLUSAO, "Dataset incluído no portal (fora da edição "
                                   "auditada).", detalhes=[obs])]
    if mudancas is None and antes is not None and depois is not None and antes != depois:
        mudancas = [{"scope": "dataset", "field": "private", "old": antes, "new": depois}]
    if mudancas:
        estado = next((m for m in mudancas if m.get("scope") == "dataset"
                       and m.get("field") == "state" and m.get("new") == "deleted"), None)
        if estado is not None:
            return [EventoClassificado(EXCLUSAO, "Dataset excluído do portal (fora da edição "
                                       "auditada, ex.: exclusão em lote na organização).",
                                       detalhes=[_detalhe_meta(estado), obs])]
        eventos = _metadados({"method": "updated", "changes": mudancas})
        for e in eventos:
            e.resumo = e.resumo.rstrip(".") + " (fora da edição auditada)."
            e.detalhes = e.detalhes + [obs]
        return eventos
    vis = {"escopo": "dataset", "recurso": None, "situacao": None, "campo": "visibilidade",
           "anterior": _rotulo_visibilidade(antes), "novo": _rotulo_visibilidade(depois)}
    base = "Dataset alterado fora da edição auditada; campos não identificados"
    if depois is True and antes is None:
        return [EventoClassificado(PRIVACAO, "Dataset tornado privado (fora da edição auditada, "
                                   "ex.: em lote na organização).", detalhes=[vis, obs])]
    if depois is None:
        resumo = f"{base} (visibilidade após a ação desconhecida)."
    elif antes is None:
        resumo = f"{base} (visibilidade após a ação: {'privado' if depois else 'público'})."
    else:
        resumo = f"{base} (visibilidade sem mudança: {'privado' if depois else 'público'})."
    return [EventoClassificado(ALTERACAO, resumo, detalhes=[vis, obs])]
