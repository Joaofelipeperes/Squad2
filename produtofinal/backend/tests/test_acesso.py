import pytest
from fastapi import APIRouter, Depends

from app.core.deps import require
from app.core.module import BackendModule
from app.core.permissoes import META, PAPEIS_PADRAO, P
from app.main import RotaSemControleDeAcesso, verificar_controle_de_acesso
from tests.conftest import SEDUC, SENHA, SES, login

API = "/api/v1/acesso"


# ---------------------------------------------------------- catálogo
def test_toda_permissao_tem_metadados():
    assert set(META) == set(P)


def test_papeis_padrao_usam_permissoes_do_catalogo():
    for papel in PAPEIS_PADRAO:
        assert papel.permissoes <= set(P), papel.codigo


# ---------------------------------------------------------- sessão
def test_login_devolve_permissoes(client):
    r = client.post(f"{API}/login", json={"email": "paloma@cge.go.gov.br", "senha": SENHA})
    sessao = r.json()["sessao"]
    assert "lgpd.aprovar_correcao" in sessao["permissoes"]
    assert "ia.configurar" not in sessao["permissoes"]
    assert sessao["usuario"]["papeis"][0]["codigo"] == "gerente_geda"


def test_admin_tem_todas(client, admin):
    assert set(client.get(f"{API}/me", headers=admin).json()["permissoes"]) == {str(p) for p in P}


def test_senha_errada_e_sem_token(client):
    assert client.post(f"{API}/login", json={"email": "admin@cge.go.gov.br",
                                             "senha": "x"}).status_code == 401
    assert client.get(f"{API}/me").status_code == 401


def test_orgao_publicador_tem_escopo(client, orgao):
    me = client.get(f"{API}/me", headers=orgao).json()
    assert me["usuario"]["orgao"]["id"] == SEDUC
    assert me["usuario"]["orgao"]["id_ckan"] == "org-seduc"
    assert set(me["permissoes"]) == {"envio.acessar", "envio.enviar_recurso"}


# ---------------------------------------------------------- autorização por rota
@pytest.mark.parametrize("metodo,rota,fixture,esperado", [
    ("get", "/api/v1/ia/perfis", "gerente", 403),            # IA só admin
    ("get", "/api/v1/ia/perfis", "admin", 200),
    ("get", "/api/v1/parametros", "orgao", 403),             # órgão não vê parâmetros
    ("get", "/api/v1/parametros", "analista", 200),
    ("put", "/api/v1/parametros/janela_alerta_prazo_dias", "analista", 403),  # vê, não edita
    ("post", "/api/v1/inventario/coletas", "analista", 403), # não força coleta
    ("get", "/api/v1/acesso/usuarios", "analista", 403),
    ("get", "/api/v1/acesso/usuarios", "gerente", 200),
    ("post", "/api/v1/acesso/papeis", "gerente", 403),       # gerente não cria papéis
    ("get", "/api/v1/inventario/coletas/ultima", "orgao", 200),  # topbar: qualquer logado
])
def test_matriz_de_autorizacao(client, request, metodo, rota, fixture, esperado):
    h = request.getfixturevalue(fixture)
    body = {"valor": 15} if metodo == "put" else None
    r = getattr(client, metodo)(rota, headers=h, **({"json": body} if body else {}))
    assert r.status_code == esperado, r.text


def test_mensagem_403_cita_permissao(client, analista):
    r = client.post("/api/v1/inventario/coletas", headers=analista)
    assert "Atualizar dados" in r.json()["detail"]


# ---------------------------------------------------------- guarda de subida
def test_rota_sem_controle_impede_subida():
    r = APIRouter()

    @r.get("/aberta")
    def aberta():
        return {}

    with pytest.raises(RotaSemControleDeAcesso, match="/x/aberta"):
        verificar_controle_de_acesso([BackendModule(name="x", prefix="/x", tags=[], router=r)])


def test_rota_com_permissao_passa():
    r = APIRouter()

    @r.get("/ok", dependencies=[Depends(require(P.PAINEL_ACESSAR))])
    def ok():
        return {}

    verificar_controle_de_acesso([BackendModule(name="x", prefix="/x", tags=[], router=r)])


# ---------------------------------------------------------- administração de usuários e papéis
def _papel_id(client, h, codigo):
    return next(p["id"] for p in client.get(f"{API}/papeis", headers=h).json()
                if p["codigo"] == codigo)


def test_papel_que_exige_orgao(client, gerente):
    pid = _papel_id(client, gerente, "orgao_publicador")
    r = client.post(f"{API}/usuarios", headers=gerente, json={
        "email": "novo@ses.go.gov.br", "nome": "Novo", "senha": SENHA, "papel_ids": [pid]})
    assert r.status_code == 422 and "órgão" in r.json()["detail"]
    r = client.post(f"{API}/usuarios", headers=gerente, json={
        "email": "novo@ses.go.gov.br", "nome": "Novo", "senha": SENHA, "papel_ids": [pid],
        "orgao_id": SES})
    assert r.status_code == 201 and r.json()["orgao"]["titulo"] == "Secretaria da Saúde"


def test_gerente_nao_concede_administrador(client, gerente):
    pid = _papel_id(client, gerente, "administrador")
    r = client.post(f"{API}/usuarios", headers=gerente, json={
        "email": "x@cge.go.gov.br", "nome": "X", "senha": SENHA, "papel_ids": [pid]})
    assert r.status_code == 422


def test_nao_remove_ultimo_administrador(client, admin):
    me = client.get(f"{API}/me", headers=admin).json()["usuario"]
    r = client.put(f"{API}/usuarios/{me['id']}", headers=admin, json={
        "email": me["email"], "nome": me["nome"], "papel_ids": []})
    assert r.status_code == 422 and "administrador" in r.json()["detail"]


def test_papel_personalizado_e_efeito_imediato(client, admin):
    r = client.post(f"{API}/papeis", headers=admin, json={
        "codigo": "auditoria", "nome": "Auditoria", "permissoes": ["painel.acessar", "nao.existe"]})
    assert r.status_code == 422
    r = client.post(f"{API}/papeis", headers=admin, json={
        "codigo": "auditoria", "nome": "Auditoria", "permissoes": ["painel.acessar"]})
    assert r.status_code == 201
    papel = r.json()
    u = client.post(f"{API}/usuarios", headers=admin, json={
        "email": "aud@cge.go.gov.br", "nome": "Aud", "senha": SENHA,
        "papel_ids": [papel["id"]]}).json()
    h = login(client, "aud@cge.go.gov.br")
    assert client.get(f"{API}/me", headers=h).json()["permissoes"] == ["painel.acessar"]
    # muda o papel → o mesmo token já reflete (permissões lidas do banco a cada requisição)
    client.put(f"{API}/papeis/{papel['id']}", headers=admin, json={
        "codigo": "auditoria", "nome": "Auditoria",
        "permissoes": ["painel.acessar", "relatorios.acessar"]})
    assert "relatorios.acessar" in client.get(f"{API}/me", headers=h).json()["permissoes"]
    # desativar o usuário derruba a sessão
    client.put(f"{API}/usuarios/{u['id']}", headers=admin, json={
        "email": u["email"], "nome": u["nome"], "papel_ids": [papel["id"]], "ativo": False})
    assert client.get(f"{API}/me", headers=h).status_code == 401


def test_papel_do_sistema_nao_exclui(client, admin):
    pid = _papel_id(client, admin, "analista_geda")
    assert client.delete(f"{API}/papeis/{pid}", headers=admin).status_code == 422


# ---------------------------------------------------------- log de acesso
def test_log_de_acesso_registra_cada_requisicao(client, admin, analista):
    client.post(f"{API}/login", json={"email": "Paloma@cge.go.gov.br", "senha": "errada"})
    client.delete(f"{API}/papeis/999999", headers=analista)          # 403
    client.get("/api/v1/saude")                                       # fora do log
    logs = client.get(f"{API}/logs", headers=admin).json()
    assert [(x["usuario"], x["metodo"], x["acao"], x["status_http"]) for x in logs[:2]] == [
        ("estagiario@cge.go.gov.br", "DELETE", "excluir_papel", 403),
        ("paloma@cge.go.gov.br", "POST", "login", 401),
    ]
    assert logs[0]["rota"] == "/api/v1/acesso/papeis/{papel_id}"
    assert logs[0]["caminho"] == "/api/v1/acesso/papeis/999999"
    assert not any(x["caminho"].endswith("/saude") for x in logs)
    assert [x["usuario"] for x in client.get(f"{API}/logs?usuario=paloma", headers=admin)
            .json()] == ["paloma@cge.go.gov.br"]
    assert client.get(f"{API}/logs", headers=analista).status_code == 403


# ---------------------------------------------------------- exclusão lógica e auditoria (ADR-0019)
def _usuario(db, email):
    from app.modules.acesso.dao import AcessoDao
    return AcessoDao(db).usuario_por_email(email)


def test_auditoria_registra_quem_criou_e_quem_alterou(client, admin, gerente):
    from app.core.db import SessionLocal
    from app.modules.acesso.models import UsuarioPapel

    pid = _papel_id(client, admin, "analista_geda")
    u = client.post(f"{API}/usuarios", headers=admin, json={
        "email": "novo@cge.go.gov.br", "nome": "Novo", "senha": SENHA, "papel_ids": [pid]}).json()
    client.put(f"{API}/usuarios/{u['id']}", headers=gerente, json={
        "email": u["email"], "nome": "Novo Nome", "papel_ids": [pid]})
    ids = {e: client.get(f"{API}/me", headers=h).json()["usuario"]["id"]
           for e, h in (("admin", admin), ("gerente", gerente))}
    with SessionLocal() as db:
        novo = _usuario(db, "novo@cge.go.gov.br")
        assert (novo.created_id, novo.changed_id) == (ids["admin"], ids["gerente"])
        assert novo.changed >= novo.created
        vinculo = db.query(UsuarioPapel).filter_by(usuario_id=novo.id).one()
        assert vinculo.created_id == ids["admin"]


def test_usuario_excluido_some_e_libera_o_email(client, admin):
    from app.core.db import SessionLocal
    from app.modules.acesso import service
    from app.modules.acesso.models import Usuario, UsuarioPapel

    pid = _papel_id(client, admin, "analista_geda")
    corpo = {"email": "temp@cge.go.gov.br", "nome": "Temp", "senha": SENHA, "papel_ids": [pid]}
    u = client.post(f"{API}/usuarios", headers=admin, json=corpo).json()
    h = login(client, "temp@cge.go.gov.br")
    with SessionLocal() as db:
        alvo = _usuario(db, "temp@cge.go.gov.br")
        service.excluir_usuario(db, alvo)
    assert u["id"] not in [x["id"] for x in client.get(f"{API}/usuarios", headers=admin).json()]
    assert client.get(f"{API}/me", headers=h).status_code == 401  # token antigo deixa de valer
    r = client.post(f"{API}/login", json={"email": "temp@cge.go.gov.br", "senha": SENHA})
    assert r.status_code == 401
    assert client.put(f"{API}/usuarios/{u['id']}", headers=admin, json=corpo).status_code == 404
    # o e-mail volta a ficar disponível; o registro antigo continua no banco, marcado
    r = client.post(f"{API}/usuarios", headers=admin, json=corpo)
    assert r.status_code == 201 and r.json()["id"] != u["id"]
    with SessionLocal() as db:
        antigo = db.get(Usuario, u["id"])
        assert antigo.deleted and antigo.changed >= antigo.created
        assert all(v.deleted for v in db.query(UsuarioPapel).filter_by(usuario_id=u["id"]))


def test_trocar_papeis_exclui_vinculo_antigo_e_cria_novo(client, admin):
    from app.core.db import SessionLocal
    from app.modules.acesso.models import UsuarioPapel

    analista, gerencia = (_papel_id(client, admin, c) for c in ("analista_geda", "gerente_geda"))
    u = client.post(f"{API}/usuarios", headers=admin, json={
        "email": "troca@cge.go.gov.br", "nome": "Troca", "senha": SENHA,
        "papel_ids": [analista]}).json()
    for papeis in ([gerencia], [analista]):
        r = client.put(f"{API}/usuarios/{u['id']}", headers=admin, json={
            "email": u["email"], "nome": u["nome"], "papel_ids": papeis})
        assert [p["id"] for p in r.json()["papeis"]] == papeis
    with SessionLocal() as db:
        vinculos = db.query(UsuarioPapel).filter_by(usuario_id=u["id"]).order_by(UsuarioPapel.id)
        # analista (excluído) → gerência (excluído) → analista de novo (vínculo NOVO, ativo)
        assert [(v.papel_id, v.deleted) for v in vinculos] == [
            (analista, True), (gerencia, True), (analista, False)]


def test_excluir_papel_exclui_logicamente_os_vinculos(client, admin):
    from app.core.db import SessionLocal
    from app.modules.acesso.models import Papel, PapelPermissao

    p = client.post(f"{API}/papeis", headers=admin, json={
        "codigo": "temporario", "nome": "Temporário", "permissoes": ["painel.acessar"]}).json()
    assert client.delete(f"{API}/papeis/{p['id']}", headers=admin).status_code == 204
    assert p["id"] not in [x["id"] for x in client.get(f"{API}/papeis", headers=admin).json()]
    assert client.delete(f"{API}/papeis/{p['id']}", headers=admin).status_code == 404
    with SessionLocal() as db:
        assert db.get(Papel, p["id"]).deleted
        assert [pp.deleted for pp in db.query(PapelPermissao).filter_by(papel_id=p["id"])] == [True]
    # o código fica livre para um papel novo
    assert client.post(f"{API}/papeis", headers=admin, json={
        "codigo": "temporario", "nome": "De novo", "permissoes": []}).status_code == 201
