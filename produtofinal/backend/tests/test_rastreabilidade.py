"""Rastreabilidade (US14, US29): classificação das atividades da auditoria do CKAN
(ckanext-dsaudit), sincronização incremental e tela /rastreabilidade/eventos."""
from datetime import UTC, datetime

import httpx
import pytest

from app.core.db import SessionLocal
from app.core.deps import UsuarioAtual
from app.integrations.ckan.client import CkanClient, CkanError
from app.modules.inventario.models import Dataset, Organizacao
from app.modules.rastreabilidade import regras, service
from app.modules.rastreabilidade.models import EventoRastreabilidade, SincronizacaoRastreabilidade


def _id_orgao(db, org_id_ckan: str) -> int:
    """`id` do órgão no inventário pelo ID do CKAN (cria o órgão se ainda não existir)."""
    org = db.query(Organizacao).filter_by(id_ckan=org_id_ckan).one_or_none()
    if org is None:
        org = Organizacao(id_ckan=org_id_ckan, name=org_id_ckan, titulo=org_id_ckan)
        db.add(org)
        db.flush()
    return org.id


def _dataset(db, id_ckan: str, name: str, titulo: str, org_id_ckan: str, **kw) -> Dataset:
    return Dataset(id_ckan=id_ckan, name=name, titulo=titulo,
                   organizacao_id=_id_orgao(db, org_id_ckan), **kw)


# ------------------------------------------------------------------ regras
def _meta(method, changes):
    return {"method": method, "changes": changes, "package": {"title": "Censo Escolar"}}


def _um(activity_type, data):
    eventos = regras.classificar(activity_type, data)
    assert len(eventos) == 1, eventos
    return eventos[0]


def test_inclusao_e_exclusao():
    c = _um("changed metadata", _meta("created", [
        {"scope": "dataset", "field": "title", "old": None, "new": "Censo Escolar"},
        {"scope": "resource", "resource_id": "r1", "resource_name": "dados.csv",
         "status": "added", "field": "name", "old": None, "new": "dados.csv"}]))
    assert c.tipo == regras.INCLUSAO and "1 recurso" in c.resumo
    c = _um("changed metadata", _meta("deleted", [
        {"scope": "dataset", "field": "state", "old": "active", "new": "deleted"}]))
    assert c.tipo == regras.EXCLUSAO


def test_privacao_e_publicacao():
    privar = _um("changed metadata", _meta("updated", [
        {"scope": "dataset", "field": "private", "old": False, "new": True}]))
    assert privar.tipo == regras.PRIVACAO
    publicar = _um("changed metadata", _meta("updated", [
        {"scope": "dataset", "field": "private", "old": "True", "new": "False"}]))
    assert publicar.tipo == regras.ALTERACAO and "público" in publicar.resumo


def test_privacao_com_outras_mudancas_gera_dois_eventos():
    """Privar e mudar o título na mesma gravação: um evento de Privação e outro de Alteração."""
    eventos = regras.classificar("changed metadata", _meta("updated", [
        {"scope": "dataset", "field": "private", "old": "False", "new": "True"},
        {"scope": "dataset", "field": "title", "old": "DataSet Teste",
         "new": "DataSet Teste, ALTERADO"}]))
    assert [e.tipo for e in eventos] == [regras.PRIVACAO, regras.ALTERACAO]
    privacao, alteracao = eventos
    assert [d["campo"] for d in privacao.detalhes] == ["visibilidade"]
    assert [d["campo"] for d in alteracao.detalhes] == ["título"]
    assert alteracao.resumo == "Alterado(s) no dataset: título."


def test_alteracao_em_linguagem_humana():
    c = _um("changed metadata", _meta("updated", [
        {"scope": "dataset", "field": "author", "old": "Ana", "new": "Bruno"},
        {"scope": "dataset", "field": "extras.periodicidade", "old": "Mensal", "new": "Anual"},
        {"scope": "resource", "resource_id": "r1", "resource_name": "dados.csv",
         "status": "changed", "field": "created", "old": "2024-01-01", "new": "2024-02-01"}]))
    assert c.tipo == regras.ALTERACAO
    assert 'autor, campo extra "periodicidade"' in c.resumo
    assert 'recurso "dados.csv": data de publicação' in c.resumo
    assert {"campo": "autor", "anterior": "Ana", "novo": "Bruno"}.items() <= c.detalhes[0].items()


def test_troca_de_arquivo_guarda_so_contagens():
    c = _um("changed resource file", {
        "resource_id": "r1", "method": "replaced",
        "version": {"version": 3, "filename": "dados.csv"},
        "previous_version": {"version": 2, "filename": "dados.csv"},
        "changes": [
            {"key": {"cpf": "123"}, "status": "updated",
             "fields": [{"field": "nome", "old": "Maria Silva", "new": "Maria S."}]},
            {"key": {"cpf": "456"}, "status": "inserted", "fields": []},
            {"key": {"cpf": "789"}, "status": "deleted", "fields": []}]})
    assert c.tipo == regras.RECURSO_ATUALIZADO
    assert "2 → 3" in c.resumo and "1 linha(s) alterada(s)" in c.resumo
    texto = str(c.detalhes)
    assert "Maria" not in texto and "123" not in texto  # nenhum valor de linha é guardado
    assert "nome" in texto
    assert c.tem_diff is True


def test_datastore_e_tipo_desconhecido():
    c = _um("created datastore", {"resource_id": "r1", "fields": [{"id": "a"}, {"id": "b"}]})
    assert c.tipo == regras.RECURSO_ATUALIZADO and "2 coluna" in c.resumo
    c = _um("changed datastore", {"resource_id": "r1", "records": [{}, {}, {}]})
    assert "3 linha(s) carregada(s)" in c.resumo and c.tem_diff is False
    assert regras.classificar("new package", {}) == []


def test_linhas_do_diff():
    linhas, total = regras.linhas_do_diff([
        {"key": {"id": "7"}, "status": "updated",
         "fields": [{"field": "valor", "old": "20", "new": "25"}]},
        {"key": {"linha": 4}, "status": "inserted", "fields": []}])
    assert total == 2
    assert linhas[0] == {"chave": "id=7", "situacao": "alterada",
                         "campos": [{"campo": "valor", "anterior": "20", "novo": "25"}]}
    assert linhas[1]["situacao"] == "incluída"


# ------------------------------------------------------------------ sincronização
ATIVIDADES = {
    "d1": [
        {"id": "a3", "timestamp": "2026-10-20T12:00:00", "user_id": "u1",
         "activity_type": "changed metadata",
         "data": _meta("updated", [{"scope": "dataset", "field": "private",
                                    "old": False, "new": True}])},
        {"id": "a2", "timestamp": "2026-10-19T12:00:00", "user_id": "u1",
         "activity_type": "changed resource file",
         "data": {"resource_id": "r1", "method": "new",
                  "version": {"version": 1, "filename": "dados.csv"}}},
        {"id": "a1", "timestamp": "2026-10-18T12:00:00", "user_id": "u2",
         "activity_type": "changed metadata", "data": _meta("created", [])},
    ],
}


def _handler(chamadas):
    def handler(request: httpx.Request):
        action = request.url.path.rsplit("/", 1)[-1]
        p = request.url.params
        chamadas.append((action, dict(p)))
        if action == "dsaudit_activity_list":
            ds = p["id"]
            if ds == "d2":
                return httpx.Response(403, json={"success": False, "error": {}})
            if ds == "d3":
                return httpx.Response(404, json={"success": False, "error": {}})
            acts = ATIVIDADES.get(ds, [])
            off, lim = int(p["offset"]), int(p["limit"])
            return httpx.Response(200, json={"success": True, "result": {
                "count": len(acts), "results": acts[off:off + lim]}})
        if action == "user_show":
            return httpx.Response(200, json={"success": True,
                                             "result": {"name": f"editor-{p['id']}"}})
        return httpx.Response(404, json={"success": False})
    return handler


def _datasets():
    with SessionLocal() as db:
        db.add_all([_dataset(db, "d1", "censo", "Censo", "org-seduc"),
                    _dataset(db, "d2", "sus", "SUS", "org-ses"),
                    _dataset(db, "d3", "velho", "Velho", "org-ses", ativo_no_portal=False)])
        db.commit()


def test_sincronizacao_incremental_e_permissoes(monkeypatch):
    _datasets()
    monkeypatch.setattr(service, "PAGINA_CKAN", 2)  # força paginação
    chamadas: list = []
    client = CkanClient("http://ckan.local", transport=httpx.MockTransport(_handler(chamadas)))
    sid = service.sincronizar(client)
    with SessionLocal() as db:
        s = db.get(SincronizacaoRastreabilidade, sid)
        assert s.status == "ok", s.erro
        assert (s.datasets_consultados, s.datasets_sem_permissao,
                s.datasets_nao_encontrados, s.eventos_novos) == (1, 1, 1, 3)
        evs = {e.ckan_activity_id: e for e in db.query(EventoRastreabilidade)}
        assert evs["a3"].tipo == regras.PRIVACAO and evs["a3"].usuario == "editor-u1"
        assert evs["a2"].recurso_nome == "dados.csv"
        assert evs["a1"].tipo == regras.INCLUSAO and evs["a1"].dataset_titulo == "Censo Escolar"
        assert evs["a1"].organizacao_id_ckan == "org-seduc"

    # segunda rodada: só a atividade nova é lida, e a leitura para na primeira já conhecida
    ATIVIDADES["d1"].insert(0, {"id": "a4", "timestamp": "2026-10-21T08:00:00", "user_id": "u1",
                                "activity_type": "changed metadata",
                                "data": _meta("updated", [{"scope": "dataset", "field": "notes",
                                                           "old": "x", "new": "y"}])})
    try:
        chamadas.clear()
        sid = service.sincronizar(client)
        with SessionLocal() as db:
            assert db.get(SincronizacaoRastreabilidade, sid).eventos_novos == 1
            assert db.query(EventoRastreabilidade).count() == 4
        lidas_d1 = [c for c in chamadas if c[0] == "dsaudit_activity_list" and c[1]["id"] == "d1"]
        assert len(lidas_d1) == 1
    finally:
        ATIVIDADES["d1"].pop(0)


def test_sem_token_sincronizacao_ignorada():
    sid = service.sincronizar()
    with SessionLocal() as db:
        s = db.get(SincronizacaoRastreabilidade, sid)
        assert s.status == "ignorada" and "GDA_CKAN_AUDITORIA_API_TOKEN" in s.erro


def test_token_sem_permissao_em_nenhum_dataset_vira_erro():
    with SessionLocal() as db:
        db.add(_dataset(db, "d2", "sus", "SUS", "org-ses"))
        db.commit()
    client = CkanClient("http://ckan.local", transport=httpx.MockTransport(_handler([])))
    sid = service.sincronizar(client)
    with SessionLocal() as db:
        assert db.get(SincronizacaoRastreabilidade, sid).status == "erro"


# ------------------------------------------------------------------ API da tela
def test_eventos_filtros_e_escopo_de_orgao(client, analista, orgao):
    _datasets()
    service.sincronizar(CkanClient("http://ckan.local",
                                   transport=httpx.MockTransport(_handler([]))))
    with SessionLocal() as db:
        db.add(EventoRastreabilidade(
            ckan_activity_id="x1", ocorrido_em=regras.parse_timestamp("2026-10-17T10:00:00"),
            tipo=regras.ALTERACAO, activity_type="changed metadata", dataset_id_ckan="d2",
            dataset_titulo="SUS", organizacao_id_ckan="org-ses", resumo="Alterado.", detalhes=[]))
        db.commit()
        seduc, ses = _id_orgao(db, "org-seduc"), _id_orgao(db, "org-ses")

    r = client.get("/api/v1/rastreabilidade/eventos", headers=analista)
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["total"] == 4
    assert corpo["eventos"][0]["dataset_id_ckan"] == "d1"  # mais recente primeiro
    assert corpo["eventos"][0]["organizacao_id"] == seduc
    assert corpo["eventos"][0]["organizacao_id_ckan"] == "org-seduc"
    assert corpo["eventos"][0]["tipo_rotulo"] == "Privação"
    assert corpo["sincronizacao"]["status"] == "ok"
    assert {o["valor"] for o in corpo["opcoes"]["orgaos"]} == {str(seduc), str(ses)}
    assert next(t["rotulo"] for t in corpo["opcoes"]["tipos"]) == "Inclusão"

    r = client.get("/api/v1/rastreabilidade/eventos?tipo=Inclusão", headers=analista)
    assert [e["tipo"] for e in r.json()["eventos"]] == ["inclusao"]
    r = client.get(f"/api/v1/rastreabilidade/eventos?orgao={ses}", headers=analista)
    assert r.json()["total"] == 1

    # órgão publicador não tem a permissão (papel padrão)
    assert client.get("/api/v1/rastreabilidade/eventos", headers=orgao).status_code == 403
    # usuário restrito a um órgão só vê os eventos desse órgão
    restrito = UsuarioAtual(id=99, email="x@seduc.go.gov.br", nome="X", orgao_id=seduc,
                            papeis=[], permissoes=frozenset({"rastreabilidade.acessar"}))
    with SessionLocal() as db:
        saida = service.listar_eventos(db, restrito)
    assert {e.organizacao_id_ckan for e in saida.eventos} == {"org-seduc"}
    assert [o.valor for o in saida.opcoes.orgaos] == [str(seduc)]


def test_eventos_exige_permissao(client):
    assert client.get("/api/v1/rastreabilidade/eventos").status_code == 401


def test_coleta_concluida_dispara_sincronizacao():
    from app.modules.inventario import service as inventario

    def ckan(request: httpx.Request):
        action = request.url.path.rsplit("/", 1)[-1]
        if action == "organization_list":
            return httpx.Response(200, json={"success": True, "result": []})
        return httpx.Response(200, json={"success": True, "result": {"count": 0, "results": []}})

    with SessionLocal() as db:
        c = inventario.iniciar(db, origem="manual")
    inventario.executar(c.id, client=CkanClient("http://ckan.local",
                                                transport=httpx.MockTransport(ckan)))
    with SessionLocal() as db:
        assert db.query(SincronizacaoRastreabilidade).count() == 1  # sem token: "ignorada"


# ------------------------------------------------------------------ partes, filtros e diff
DIFF_ARQUIVO = {"resource_id": "r1", "method": "replaced", "keys": ["id"],
                "version": {"version": 2, "filename": "dados.csv"},
                "previous_version": {"version": 1, "filename": "dados.csv"},
                "changes": [{"key": {"id": "2"}, "status": "updated",
                             "fields": [{"field": "valor", "old": "20", "new": "25"}]},
                            {"key": {"id": "3"}, "status": "deleted",
                             "fields": [{"field": "valor", "old": "30", "new": None}]}]}

ATIVIDADES_D4 = [
    {"id": "b2", "timestamp": "2026-10-21T20:43:00", "user_id": "u1",
     "activity_type": "changed metadata",
     "data": _meta("updated", [
         {"scope": "dataset", "field": "private", "old": "False", "new": "True"},
         {"scope": "dataset", "field": "title", "old": "Teste", "new": "Teste ALTERADO"}])},
    {"id": "b1", "timestamp": "2026-10-10T09:00:00", "user_id": "u1",
     "activity_type": "changed resource file", "data": DIFF_ARQUIVO},
]


def _handler_d4(request: httpx.Request):
    action = request.url.path.rsplit("/", 1)[-1]
    p = request.url.params
    if action == "dsaudit_activity_list":
        acts = [a for a in ATIVIDADES_D4
                if not p.get("activity_type") or a["activity_type"] == p["activity_type"]]
        ini = int(p["offset"])
        return httpx.Response(200, json={"success": True, "result": {
            "count": len(acts), "results": acts[ini:ini + int(p["limit"])]}})
    if action == "user_show":
        return httpx.Response(200, json={"success": True, "result": {"name": "admin"}})
    return httpx.Response(404, json={"success": False})


def _sincronizar_d4():
    with SessionLocal() as db:
        db.add(_dataset(db, "d4", "saude-escolar", "Saúde Escolar", "org-ses"))
        db.commit()
    client = CkanClient("http://ckan.local", transport=httpx.MockTransport(_handler_d4))
    service.sincronizar(client)
    return client


def test_privacao_e_titulo_viram_dois_eventos_da_mesma_atividade():
    _sincronizar_d4()
    with SessionLocal() as db:
        partes = db.query(EventoRastreabilidade).filter_by(ckan_activity_id="b2") \
            .order_by(EventoRastreabilidade.sequencia).all()
        assert [(e.sequencia, e.tipo) for e in partes] == [(0, regras.PRIVACAO),
                                                           (1, regras.ALTERACAO)]
        assert partes[1].detalhes[0]["novo"] == "Teste ALTERADO"
        arquivo = db.query(EventoRastreabilidade).filter_by(ckan_activity_id="b1").one()
        assert arquivo.tem_diff is True


def test_busca_periodo_e_ordem(client, analista):
    _sincronizar_d4()
    url = "/api/v1/rastreabilidade/eventos"
    r = client.get(f"{url}?busca=saude escolar", headers=analista)  # sem acento
    assert r.json()["total"] == 3
    assert client.get(f"{url}?busca=inexistente", headers=analista).json()["total"] == 0
    r = client.get(f"{url}?desde=2026-10-15T00:00:00-03:00", headers=analista)
    assert {e["tipo"] for e in r.json()["eventos"]} == {"privacao", "alteracao"}
    r = client.get(f"{url}?ate=2026-10-15T00:00:00-03:00", headers=analista)
    assert [e["tipo"] for e in r.json()["eventos"]] == ["recurso_atualizado"]
    antigos = client.get(f"{url}?ordem=antigos", headers=analista).json()["eventos"]
    assert antigos[0]["tipo"] == "recurso_atualizado" and antigos[0]["tem_diff"] is True
    assert client.get(f"{url}?ordem=qualquer", headers=analista).status_code == 422


def test_diff_lido_do_ckan_sem_gravar(client, analista):
    ckan = _sincronizar_d4()
    with SessionLocal() as db:
        arquivo = db.query(EventoRastreabilidade).filter_by(ckan_activity_id="b1").one()
        privacao = db.query(EventoRastreabilidade).filter_by(ckan_activity_id="b2",
                                                             sequencia=0).one()
        assert "25" not in str(arquivo.detalhes)  # valores não ficam no banco da solução
        restrito = UsuarioAtual(id=1, email="a@cge.go.gov.br", nome="A", orgao_id=None,
                                papeis=[], permissoes=frozenset({"rastreabilidade.acessar"}))
        diff = service.diff_evento(db, restrito, arquivo.id, client=ckan)
    assert (diff.versao_anterior, diff.versao_nova, diff.colunas_chave) == (1, 2, ["id"])
    assert diff.total_linhas == 2
    assert diff.linhas[0].chave == "id=2" and diff.linhas[0].campos[0].novo == "25"
    # pela API: sem diff → 409; inexistente → 404; sem token configurado → 409
    url = "/api/v1/rastreabilidade/eventos"
    assert client.get(f"{url}/{privacao.id}/diff", headers=analista).status_code == 409
    assert client.get(f"{url}/99999/diff", headers=analista).status_code == 404
    r = client.get(f"{url}/{arquivo.id}/diff", headers=analista)
    assert r.status_code == 409 and "GDA_CKAN_AUDITORIA_API_TOKEN" in r.json()["detail"]


def test_diff_respeita_escopo_de_orgao():
    ckan = _sincronizar_d4()
    with SessionLocal() as db:
        seduc = _id_orgao(db, "org-seduc")
        db.commit()
    outro = UsuarioAtual(id=2, email="b@seduc.go.gov.br", nome="B", orgao_id=seduc,
                         papeis=[], permissoes=frozenset({"rastreabilidade.acessar"}))
    with SessionLocal() as db:
        ev = db.query(EventoRastreabilidade).filter_by(ckan_activity_id="b1").one()
        with pytest.raises(service.EventoNaoEncontrado):
            service.diff_evento(db, outro, ev.id, client=ckan)


def test_diff_le_do_ckan_em_uso(monkeypatch):
    """Sem cliente injetado, a auditoria/diff constrói o CkanClient com a URL/token do CKAN em uso
    (config_ativa = perfil selecionado ou .env, ADR-0024) — não com o CKAN do inventário."""
    from app.modules.ckan_config.service import ConfigCkan
    _sincronizar_d4()  # popula os eventos; 'b1' (troca de arquivo) tem tem_diff=True
    capturado = {}

    monkeypatch.setattr(service, "config_ativa",
                        lambda: ConfigCkan("http://inventario:5000",
                                           "http://ckan-auditoria.example:5000", "token-editor"))

    def _fabricar(*, base_url=None, api_token=None, **kw):
        capturado["base_url"] = base_url
        return CkanClient(base_url=base_url, transport=httpx.MockTransport(_handler_d4),
                          api_token=api_token)

    monkeypatch.setattr(service, "CkanClient", _fabricar)

    analista = UsuarioAtual(id=1, email="a@cge.go.gov.br", nome="A", orgao_id=None,
                            papeis=[], permissoes=frozenset({"rastreabilidade.acessar"}))
    with SessionLocal() as db:
        arquivo = db.query(EventoRastreabilidade).filter_by(ckan_activity_id="b1").one()
        diff = service.diff_evento(db, analista, arquivo.id)
    assert capturado["base_url"] == "http://ckan-auditoria.example:5000"
    assert diff.total_linhas == 2  # leu o diff pela URL de auditoria, não pela do inventário


def test_linhas_do_diff_sem_corte_para_o_csv():
    """A tela mantém o corte de MAX_LINHAS_DIFF; o CSV (limite=None) traz todas as linhas."""
    changes = [{"status": "inserted", "key": {"id": i}, "fields": []}
               for i in range(regras.MAX_LINHAS_DIFF + 1)]
    recortadas, total = regras.linhas_do_diff(changes)
    assert len(recortadas) == regras.MAX_LINHAS_DIFF
    assert total == regras.MAX_LINHAS_DIFF + 1
    todas, total_sem_corte = regras.linhas_do_diff(changes, limite=None)
    assert len(todas) == regras.MAX_LINHAS_DIFF + 1 == total_sem_corte


def test_diff_csv_do_evento_traz_todas_as_linhas_detalhadas():
    """Download da tela: CSV (;) com cabeçalho e uma linha por campo alterado, sem corte."""
    ckan = _sincronizar_d4()
    analista_user = UsuarioAtual(id=1, email="a@cge.go.gov.br", nome="A", orgao_id=None,
                                 papeis=[], permissoes=frozenset({"rastreabilidade.acessar"}))
    with SessionLocal() as db:
        arquivo = db.query(EventoRastreabilidade).filter_by(ckan_activity_id="b1").one()
        nome, csv_txt = service.diff_evento_csv(db, analista_user, arquivo.id, client=ckan)
    assert nome == f"rastreabilidade-diff-evento-{arquivo.id}.csv"
    linhas = csv_txt.strip().splitlines()
    assert linhas[0] == "Linha;Situação;Coluna;Antes;Depois"
    assert any("id=2" in linha and "25" in linha for linha in linhas[1:])
    assert len(linhas) >= 3  # cabeçalho + pelo menos as 2 linhas do diff


def test_diff_csv_api_mapeia_erros(client, analista):
    _sincronizar_d4()
    url = "/api/v1/rastreabilidade/eventos"
    with SessionLocal() as db:
        privacao = db.query(EventoRastreabilidade).filter_by(ckan_activity_id="b2",
                                                             sequencia=0).one()
    # evento sem diff → 409; inexistente → 404 (antes de exigir token)
    assert client.get(f"{url}/{privacao.id}/diff.csv", headers=analista).status_code == 409
    assert client.get(f"{url}/99999/diff.csv", headers=analista).status_code == 404


def _handler_html_acesso_negado(request: httpx.Request) -> httpx.Response:
    """Imita um portal que devolve HTML de 'Acesso Negado' com HTTP 200 (sem o dsaudit)."""
    return httpx.Response(200, text="<!DOCTYPE html><html>Acesso Negado</html>",
                          headers={"content-type": "text/html"})


def test_action_resposta_nao_json_vira_ckan_error():
    """HTML com HTTP 200 (portal sem o endpoint) → CkanError tratado, não JSONDecodeError cru."""
    ckan = CkanClient("http://portal.local", transport=httpx.MockTransport(_handler_html_acesso_negado))
    with pytest.raises(CkanError):
        ckan.status()


def test_diff_com_resposta_nao_json_vira_indisponivel_sem_500():
    """Regressão: auditoria devolvendo HTML não pode estourar 500; vira DiffIndisponivel (409)."""
    _sincronizar_d4()  # popula o evento 'b1' (tem_diff=True)
    html = CkanClient("http://portal.local", transport=httpx.MockTransport(_handler_html_acesso_negado))
    user = UsuarioAtual(id=1, email="a@cge.go.gov.br", nome="A", orgao_id=None,
                        papeis=[], permissoes=frozenset({"rastreabilidade.acessar"}))
    with SessionLocal() as db:
        arquivo = db.query(EventoRastreabilidade).filter_by(ckan_activity_id="b1").one()
        with pytest.raises(service.DiffIndisponivel):
            service.diff_evento(db, user, arquivo.id, client=html)


# ------------------------------------------------------------------ cadastro dos órgãos
def _org(oid, titulo, descricao="", extras=None):
    return {"id": oid, "name": oid, "title": titulo, "description": descricao,
            "image_url": "", "package_count": 3, "display_name": titulo,
            "extras": [{"key": k, "value": v, "state": "active"} for k, v in (extras or {}).items()]}


def test_payload_e_comparacao_do_orgao():
    antes = regras.payload_orgao(_org("o1", "Saúde", "Antiga", {"sigla": "SES"}))
    assert antes == {"name": "o1", "title": "Saúde", "description": "Antiga", "image_url": "",
                     "extras.sigla": "SES"}  # contagens e campos derivados ficam de fora
    depois = regras.payload_orgao(_org("o1", "Saúde", "Nova", {"sigla": "SES-GO", "site": "x"}))
    c = regras.comparar_orgao(antes, depois)
    assert c.tipo == regras.ALTERACAO
    assert c.resumo == ("Alterado(s) no cadastro do órgão: "
                        'descrição, campo extra "sigla", campo extra "site".')
    assert {(d["campo"], d["anterior"], d["novo"]) for d in c.detalhes} == {
        ("descrição", "Antiga", "Nova"), ('campo extra "sigla"', "SES", "SES-GO"),
        ('campo extra "site"', None, "x")}
    assert regras.comparar_orgao(antes, dict(antes)) is None
    assert regras.comparar_orgao(None, antes).tipo == regras.INCLUSAO
    assert regras.comparar_orgao(antes, None).tipo == regras.EXCLUSAO


def _eventos_de_orgao(db):
    return db.query(EventoRastreabilidade).filter_by(origem=regras.ORIGEM_COMPARACAO) \
        .order_by(EventoRastreabilidade.id).all()


def test_comparacao_entre_coletas_gera_eventos_de_orgao():
    from app.modules.rastreabilidade.models import OrgaoSnapshot

    base = [_org("org-seduc", "Educação", "Desc"), _org("org-ses", "Saúde", "Desc")]
    service.sincronizar(orgaos=base)  # primeira vez: só a fotografia de base, sem eventos
    with SessionLocal() as db:
        assert db.query(OrgaoSnapshot).count() == 2 and _eventos_de_orgao(db) == []

    service.sincronizar(orgaos=base)  # nada mudou: nenhuma fotografia nova
    with SessionLocal() as db:
        assert db.query(OrgaoSnapshot).count() == 2

    mudou = [_org("org-seduc", "Educação", "Desc nova", {"campo_custom": "1"}),
             _org("org-novo", "Órgão Novo")]  # org-ses sumiu
    sid = service.sincronizar(orgaos=mudou)
    with SessionLocal() as db:
        evs = _eventos_de_orgao(db)
        assert sorted((e.organizacao_id_ckan, e.tipo) for e in evs) == [
            ("org-novo", regras.INCLUSAO), ("org-seduc", regras.ALTERACAO),
            ("org-ses", regras.EXCLUSAO)]
        alt = next(e for e in evs if e.tipo == regras.ALTERACAO)
        assert alt.usuario is None and alt.dataset_id_ckan is None and alt.ckan_activity_id is None
        assert {d["campo"] for d in alt.detalhes} == {"descrição", 'campo extra "campo_custom"'}
        s = db.get(SincronizacaoRastreabilidade, sid)
        assert (s.orgaos_consultados, s.eventos_novos, s.status) == (2, 3, "ignorada")


def test_coleta_compara_cadastro_dos_orgaos(client, analista):
    from app.modules.inventario import service as inventario

    orgs = {"lista": [_org("org-seduc", "Secretaria da Educação", "Desc")]}

    def ckan(request: httpx.Request):
        action = request.url.path.rsplit("/", 1)[-1]
        if action == "organization_list":
            return httpx.Response(200, json={"success": True, "result": orgs["lista"]})
        return httpx.Response(200, json={"success": True, "result": {"count": 0, "results": []}})

    for descricao in ("Desc", "Desc alterada"):
        orgs["lista"] = [_org("org-seduc", "Secretaria da Educação", descricao)]
        with SessionLocal() as db:
            c = inventario.iniciar(db, origem="manual")
        inventario.executar(c.id, client=CkanClient("http://ckan.local",
                                                    transport=httpx.MockTransport(ckan)))
    r = client.get("/api/v1/rastreabilidade/eventos?busca=educacao", headers=analista)
    eventos = r.json()["eventos"]
    assert [(e["origem"], e["tipo"], e["dataset_titulo"]) for e in eventos] == [
        ("comparacao_coletas", "alteracao", None)]
    assert eventos[0]["orgao_nome"] == "Secretaria da Educação"


def test_autoria_do_orgao_pelas_atividades_do_ckan():
    """Com token, o evento do órgão recebe quem alterou e quando (atividades nativas do CKAN);
    atividades de datasets do órgão e fora do intervalo são ignoradas."""
    def ckan(request: httpx.Request):
        action = request.url.path.rsplit("/", 1)[-1]
        p = request.url.params
        if action == "organization_activity_list":
            acts = [
                {"id": "x3", "timestamp": "2099-01-01T00:00:00", "user_id": "futuro",
                 "activity_type": "changed organization"},  # depois da coleta: fora
                {"id": "x2", "timestamp": "2026-10-22T23:41:00", "user_id": "u-bruno",
                 "activity_type": "changed organization"},
                {"id": "x1", "timestamp": "2026-10-22T23:30:00", "user_id": "u-ana",
                 "activity_type": "changed package"},  # dataset do órgão: ignorada
                {"id": "x0", "timestamp": "2026-10-22T23:00:00", "user_id": "u-ana",
                 "activity_type": "changed organization"},
                {"id": "xa", "timestamp": "2020-01-01T00:00:00", "user_id": "u-velho",
                 "activity_type": "changed organization"},  # antes da fotografia anterior
            ]
            ini = int(p["offset"])
            return httpx.Response(200, json={"success": True,
                                             "result": acts[ini:ini + int(p["limit"])]})
        if action == "user_show":
            return httpx.Response(200, json={"success": True,
                                             "result": {"name": p["id"].replace("u-", "")}})
        return httpx.Response(200, json={"success": True, "result": {"count": 0, "results": []}})

    from datetime import UTC, datetime

    from app.modules.rastreabilidade.models import OrgaoSnapshot

    client = CkanClient("http://ckan.local", transport=httpx.MockTransport(ckan))
    service.sincronizar(client, orgaos=[_org("org-ses", "Saúde", "Antes")])
    with SessionLocal() as db:  # fotografia de base "tirada" em 2026-10-22 22:00 UTC
        db.query(OrgaoSnapshot).update(
            {"capturado_em": datetime(2026, 10, 22, 22, 0, tzinfo=UTC)})
        db.commit()
    service.sincronizar(client, orgaos=[_org("org-ses", "Saúde", "Depois")])
    with SessionLocal() as db:
        ev = _eventos_de_orgao(db)[0]
        assert ev.usuario == "ana, bruno"
        assert ev.ocorrido_em.replace(tzinfo=None) == datetime(2026, 10, 22, 23, 41)
        autoria = ev.detalhes[-1]
        assert autoria["campo"] == "alterações registradas no CKAN no período"
        assert autoria["novo"] == "ana em 22/10/2026 20:00; bruno em 22/10/2026 20:41"


def test_sem_acesso_as_atividades_do_orgao_evento_fica_sem_autor():
    def ckan(request: httpx.Request):
        if request.url.path.endswith("organization_activity_list"):
            return httpx.Response(403, json={"success": False, "error": {}})
        return httpx.Response(200, json={"success": True, "result": {"count": 0, "results": []}})

    client = CkanClient("http://ckan.local", transport=httpx.MockTransport(ckan))
    service.sincronizar(client, orgaos=[_org("org-ses", "Saúde", "Antes")])
    service.sincronizar(client, orgaos=[_org("org-ses", "Saúde", "Depois")])
    with SessionLocal() as db:
        ev = _eventos_de_orgao(db)[0]
        assert ev.usuario is None and ev.tipo == regras.ALTERACAO


# ------------------------------------------------------------------ ações fora da auditoria
def _ts(texto):
    return regras.parse_timestamp(texto)


def test_nativas_orfas_ignora_as_que_tem_par_na_extensao():
    nativas = [
        {"id": "n1", "timestamp": "2026-10-20T21:16:20.726", "activity_type": "changed package"},
        {"id": "n2", "timestamp": "2026-10-23T00:21:21.220", "activity_type": "changed package"},
        {"id": "n3", "timestamp": "2026-10-23T00:30:00", "activity_type": "deleted package"},
        {"id": "n4", "timestamp": "2026-10-23T00:31:00", "activity_type": "follow dataset"},
    ]
    auditadas = [_ts("2026-10-20T21:16:20.752")]  # 0,026 s depois de n1: mesma edição
    assert [a["id"] for a in regras.nativas_orfas(nativas, auditadas)] == ["n2", "n3"]


def test_resolver_visibilidade():
    t1, t2, t3 = _ts("2026-10-01T10:00:00"), _ts("2026-10-02T10:00:00"), _ts("2026-10-03T10:00:00")
    # sem marcos: antes = base (estava na busca pública), depois = estado atual
    assert regras.resolver_visibilidade([t2], [], atual=True, base=False) == [(False, True)]
    # marco da extensão depois da órfã: o "antes" dele é o estado logo após a órfã
    marcos = [(t1, None, False), (t3, True, False)]
    assert regras.resolver_visibilidade([t2], marcos, atual=False, base=None) == [(False, True)]
    # duas órfãs seguidas sem marco no meio: a primeira fica com estado intermediário desconhecido
    assert regras.resolver_visibilidade([t1, t2], [], atual=True, base=False) == [
        (False, None), (False, True)]


def test_classificar_orfa():
    [privar] = regras.classificar_orfa("changed package", False, True)
    assert privar.tipo == regras.PRIVACAO
    [publica] = regras.classificar_orfa("changed package", True, False)
    assert publica.tipo == regras.ALTERACAO and "tornado público" in publica.resumo
    assert regras.classificar_orfa("deleted package", None, None)[0].tipo == regras.EXCLUSAO
    [sem] = regras.classificar_orfa("changed package", False, False)
    assert sem.tipo == regras.ALTERACAO and "campos não identificados" in sem.resumo


def test_mudancas_pacote_no_formato_da_extensao():
    antes = {"title": "A", "private": False, "metadata_modified": "x", "tags": [{"name": "t1"}],
             "extras": [{"key": "fonte", "value": "SES"}],
             "resources": [{"id": "r1", "name": "dados.csv", "format": "CSV"}]}
    depois = {"title": "B", "private": True, "metadata_modified": "y", "tags": [{"name": "t1"}],
              "extras": [{"key": "fonte", "value": "SES-GO"}],
              "resources": [{"id": "r1", "name": "dados.csv", "format": "XLSX"}]}
    m = regras.mudancas_pacote(antes, depois)
    assert {(c["scope"], c["field"]) for c in m} == {
        ("dataset", "title"), ("dataset", "private"), ("dataset", "extras.fonte"),
        ("resource", "format")}
    eventos = regras.classificar_orfa("changed package", None, None, m)
    assert [e.tipo for e in eventos] == [regras.PRIVACAO, regras.ALTERACAO]
    assert all("fora da edição auditada" in e.resumo for e in eventos)


def test_acao_em_lote_vira_evento_sem_duplicar():
    """Make private em lote: só a atividade nativa existe. A edição comum (com par na extensão)
    não é duplicada; a leitura seguinte não grava de novo."""
    auditoria = [{"id": "d-edit", "timestamp": "2026-10-20T10:00:00.050", "user_id": "u-ana",
                  "activity_type": "changed metadata",
                  "data": _meta("updated", [{"scope": "dataset", "field": "title",
                                             "old": "A", "new": "B"}])}]
    nativas = [
        {"id": "n-lote", "timestamp": "2026-10-21T15:00:00", "user_id": "u-bruno",
         "activity_type": "changed package", "data": {"package": {"title": "Censo"}}},
        {"id": "n-edit", "timestamp": "2026-10-20T10:00:00.020", "user_id": "u-ana",
         "activity_type": "changed package", "data": {"package": {"title": "Censo"}}},
    ]

    def ckan(request: httpx.Request):
        action = request.url.path.rsplit("/", 1)[-1]
        p = request.url.params
        if action == "dsaudit_activity_list":
            return httpx.Response(200, json={"success": True, "result": {
                "count": len(auditoria), "results": auditoria}})
        if action == "package_activity_list":
            return httpx.Response(200, json={"success": True, "result": nativas})
        if action == "package_show":
            return httpx.Response(200, json={"success": True, "result": {"private": True}})
        if action == "user_show":
            return httpx.Response(200, json={"success": True,
                                             "result": {"name": p["id"].replace("u-", "")}})
        return httpx.Response(404, json={"success": False})

    with SessionLocal() as db:
        db.add(_dataset(db, "d1", "censo", "Censo", "org-seduc"))
        db.commit()
    client = CkanClient("http://ckan.local", transport=httpx.MockTransport(ckan))
    sid = service.sincronizar(client)
    with SessionLocal() as db:
        nativos = db.query(EventoRastreabilidade).filter_by(origem=regras.ORIGEM_NATIVA).all()
        assert [(e.ckan_activity_id, e.tipo, e.usuario) for e in nativos] == [
            ("n-lote", regras.PRIVACAO, "bruno")]
        assert db.get(SincronizacaoRastreabilidade, sid).atividades_nativas_ate is not None
    service.sincronizar(client)  # segunda leitura: nada novo
    with SessionLocal() as db:
        assert db.query(EventoRastreabilidade).filter_by(origem=regras.ORIGEM_NATIVA).count() == 1
        assert db.query(EventoRastreabilidade).count() == 2  # edição (extensão) + lote (nativa)


def test_versao_anterior_a_acao():
    quando = datetime(2026, 10, 21, 15, 0, tzinfo=UTC)
    # lote: metadata_modified não muda (versão do cache do Solr, de antes da ação)
    assert regras.versao_anterior_a_acao({"metadata_modified": "2026-10-20T09:00:00"}, quando)
    # package_update/package_patch: metadata_modified acompanha a atividade
    assert not regras.versao_anterior_a_acao(
        {"metadata_modified": "2026-10-21T14:59:59.990"}, quando)
    assert not regras.versao_anterior_a_acao({}, quando)


def test_versoes_do_ckan_dao_o_que_mudou_em_cada_acao_em_lote():
    """Make private, Make public e Delete em lote, como o CKAN 2.9 grava de fato: a versão da
    atividade em lote vem do cache do Solr e é a de ANTES da ação (metadata_modified antigo).
    O estado depois de cada ação é o de antes da atividade seguinte; salvar sem mudar nada não
    gera evento."""
    auditoria = [{"id": "d-criacao", "timestamp": "2026-10-20T09:00:00.030", "user_id": "u-ana",
                  "activity_type": "changed metadata", "data": _meta("created", [])}]
    nativas = [  # da mais recente para a mais antiga, como o CKAN devolve
        {"id": "n-excluido", "timestamp": "2026-10-23T10:00:00", "user_id": "u-bruno",
         "activity_type": "deleted package"},
        {"id": "n-nada", "timestamp": "2026-10-22T09:00:00", "user_id": "u-ana",
         "activity_type": "changed package"},
        {"id": "n-publico", "timestamp": "2026-10-21T16:00:00", "user_id": "u-bruno",
         "activity_type": "changed package"},
        {"id": "n-privado", "timestamp": "2026-10-21T15:00:00", "user_id": "u-bruno",
         "activity_type": "changed package"},
        {"id": "n-criacao", "timestamp": "2026-10-20T09:00:00", "user_id": "u-ana",
         "activity_type": "new package"},
    ]
    criado = "2026-10-20T09:00:00"
    versoes = {
        "n-criacao": {"title": "Censo", "private": False, "metadata_modified": criado},
        "n-privado": {"title": "Censo", "private": False, "metadata_modified": criado},  # antes
        "n-publico": {"title": "Censo", "private": True, "metadata_modified": criado},   # antes
        "n-nada": {"title": "Censo", "private": False,
                   "metadata_modified": "2026-10-22T08:59:59.990"},
        "n-excluido": {"title": "Censo", "private": False, "state": "active",
                       "metadata_modified": "2026-10-22T08:59:59.990"},
    }

    def ckan(request: httpx.Request):
        action = request.url.path.rsplit("/", 1)[-1]
        p = request.url.params
        if action == "dsaudit_activity_list":
            return httpx.Response(200, json={"success": True, "result": {
                "count": 1, "results": auditoria}})
        if action == "package_activity_list":
            return httpx.Response(200, json={"success": True, "result": nativas})
        if action == "activity_data_show":
            return httpx.Response(200, json={"success": True, "result": versoes[p["id"]]})
        if action == "package_show":
            return httpx.Response(200, json={"success": True, "result": {"private": False}})
        if action == "user_show":
            return httpx.Response(200, json={"success": True,
                                             "result": {"name": p["id"].replace("u-", "")}})
        return httpx.Response(404, json={"success": False})

    with SessionLocal() as db:
        db.add(_dataset(db, "d1", "censo", "Censo", "org-seduc"))
        db.commit()
    service.sincronizar(CkanClient("http://ckan.local", transport=httpx.MockTransport(ckan)))
    with SessionLocal() as db:
        nativos = db.query(EventoRastreabilidade).filter_by(origem=regras.ORIGEM_NATIVA) \
            .order_by(EventoRastreabilidade.ocorrido_em).all()
        assert [(e.ckan_activity_id, e.tipo, e.usuario) for e in nativos] == [
            ("n-privado", regras.PRIVACAO, "bruno"), ("n-publico", regras.ALTERACAO, "bruno"),
            ("n-excluido", regras.EXCLUSAO, "bruno")]
        assert "tornado público" in nativos[1].resumo
        vis = [[(d["anterior"], d["novo"]) for d in e.detalhes if d["campo"] == "visibilidade"]
               for e in nativos[:2]]
        assert vis == [[("False", "True")], [("True", "False")]]
