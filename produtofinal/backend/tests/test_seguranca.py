"""Endurecimento de segurança (ADR-0036): login, senha, sessão, escalada de privilégio pela gestão
de usuários e papéis, exportações e chamadas para fora.
Roteiro manual: docs/roteiro-teste-ciberseguranca.md."""
import io

import httpx
import pytest
from openpyxl import load_workbook

from app.core import rede
from app.core.config import get_settings
from app.core.exportacao import sem_formula
from app.integrations.ai.base import AIProviderError
from app.integrations.ai.providers import _http
from app.integrations.ckan.client import CkanClient, CkanError
from app.modules.acesso import service as acesso
from tests.conftest import SENHA, login

API = "/api/v1"
ACESSO = f"{API}/acesso"


def _papel_id(client, h, codigo):
    return next(p["id"] for p in client.get(f"{ACESSO}/papeis", headers=h).json()
                if p["codigo"] == codigo)


def _usuario(client, h, email):
    return next(u for u in client.get(f"{ACESSO}/usuarios", headers=h).json()
                if u["email"] == email)


def _criar(client, admin, email, papeis):
    r = client.post(f"{ACESSO}/usuarios", headers=admin, json={
        "email": email, "nome": "Pessoa de teste", "senha": SENHA, "papel_ids": papeis})
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ------------------------------------------------------------------ rotas públicas
def test_saude_nao_descreve_o_ambiente(client):
    assert client.get(f"{API}/saude").json() == {"status": "ok"}


def test_documentacao_da_api_so_em_dev_ou_habilitada(monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import create_app

    def docs(valor):
        monkeypatch.setenv("GDA_API_DOCS", valor)
        get_settings.cache_clear()
        c = TestClient(create_app())
        return [c.get(f"{API}/docs").status_code, c.get(f"{API}/openapi.json").status_code,
                c.get("/redoc").status_code]

    try:
        assert docs("false") == [404, 404, 404]
        assert docs("true") == [200, 200, 404]
    finally:
        monkeypatch.delenv("GDA_API_DOCS")
        get_settings.cache_clear()


def test_corpo_grande_demais_e_recusado(client):
    r = client.post(f"{ACESSO}/login", content=b"x" * (get_settings().corpo_maximo_bytes + 1),
                    headers={"content-type": "application/json"})
    assert r.status_code == 413


# ------------------------------------------------------------------ login e sessão
def test_senha_longa_no_login_da_401_e_nao_erro(client):
    for senha, esperado in [("a" * 100, 401), ("a" * 5000, 422)]:
        r = client.post(f"{ACESSO}/login", json={"email": "admin@cge.go.gov.br", "senha": senha})
        assert r.status_code == esperado


def test_login_bloqueia_depois_de_muitas_senhas_erradas(client):
    corpo = {"email": "paloma@cge.go.gov.br", "senha": "errada-1"}
    limite = get_settings().login_max_falhas
    assert [client.post(f"{ACESSO}/login", json=corpo).status_code
            for _ in range(limite)] == [401] * limite
    assert client.post(f"{ACESSO}/login", json=corpo).status_code == 429
    # nem a senha certa entra durante o bloqueio; outro usuário não é afetado
    assert client.post(f"{ACESSO}/login", json={**corpo, "senha": SENHA}).status_code == 429
    assert client.post(f"{ACESSO}/login", json={"email": "admin@cge.go.gov.br",
                                                "senha": SENHA}).status_code == 200


def test_login_certo_zera_a_contagem_de_falhas(client):
    errada = {"email": "paloma@cge.go.gov.br", "senha": "errada-1"}
    for _ in range(get_settings().login_max_falhas - 1):
        client.post(f"{ACESSO}/login", json=errada)
    login(client, "paloma@cge.go.gov.br")
    assert client.post(f"{ACESSO}/login", json=errada).status_code == 401


def test_email_inexistente_tambem_verifica_senha(client, monkeypatch):
    """Tempo de resposta igual para conta existente e inexistente."""
    chamadas = []
    monkeypatch.setattr(acesso, "gastar_tempo_de_verificacao", chamadas.append)
    client.post(f"{ACESSO}/login", json={"email": "ninguem@cge.go.gov.br", "senha": "x"})
    assert chamadas == ["x"]


@pytest.mark.parametrize("senha", ["12345678", "abcdefgh", "senha123", "aaaaaaa1",
                                   "novato2026", "a1" * 40])
def test_senha_fraca_e_recusada(client, admin, senha):
    r = client.post(f"{ACESSO}/usuarios", headers=admin, json={
        "email": "novato@cge.go.gov.br", "nome": "Novato", "senha": senha, "papel_ids": []})
    assert r.status_code == 422, senha


def test_usuario_troca_a_propria_senha_e_as_sessoes_antigas_caem(client, analista):
    nova = "Outra-senha-2027"
    r = client.post(f"{ACESSO}/me/senha", headers=analista,
                    json={"senha_atual": "errada", "senha_nova": nova})
    assert r.status_code == 422
    r = client.post(f"{ACESSO}/me/senha", headers=analista,
                    json={"senha_atual": SENHA, "senha_nova": "12345678"})
    assert r.status_code == 422
    r = client.post(f"{ACESSO}/me/senha", headers=analista,
                    json={"senha_atual": SENHA, "senha_nova": nova})
    assert r.status_code == 200, r.text
    novo = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get(f"{ACESSO}/me", headers=analista).status_code == 401  # token antigo
    assert client.get(f"{ACESSO}/me", headers=novo).status_code == 200
    assert client.post(f"{ACESSO}/login", json={"email": "estagiario@cge.go.gov.br",
                                                "senha": nova}).status_code == 200


def test_senha_trocada_por_gestor_encerra_a_sessao_do_usuario(client, admin, analista):
    u = _usuario(client, admin, "estagiario@cge.go.gov.br")
    client.put(f"{ACESSO}/usuarios/{u['id']}", headers=admin, json={
        "email": u["email"], "nome": u["nome"], "senha": "Trocada-pelo-admin-9",
        "papel_ids": [p["id"] for p in u["papeis"]]})
    assert client.get(f"{ACESSO}/me", headers=analista).status_code == 401


# ------------------------------------------------------------------ escalada de privilégio
def test_gestor_de_usuarios_nao_muda_os_proprios_papeis(client, admin, gerente):
    eu = client.get(f"{ACESSO}/me", headers=gerente).json()["usuario"]
    outro = _papel_id(client, admin, "analista_geda")
    corpo = {"email": eu["email"], "nome": eu["nome"],
             "papel_ids": [p["id"] for p in eu["papeis"]] + [outro]}
    assert client.put(f"{ACESSO}/usuarios/{eu['id']}", headers=gerente,
                      json=corpo).status_code == 422
    corpo["papel_ids"] = [p["id"] for p in eu["papeis"]]  # só o nome: permitido
    assert client.put(f"{ACESSO}/usuarios/{eu['id']}", headers=gerente,
                      json={**corpo, "nome": "Paloma P."}).status_code == 200
    assert client.put(f"{ACESSO}/usuarios/{eu['id']}", headers=gerente,
                      json={**corpo, "ativo": False}).status_code == 422


def test_gestor_nao_concede_nem_altera_quem_tem_papel_acima_do_seu(client, admin, gerente):
    forte = client.post(f"{ACESSO}/papeis", headers=admin, json={
        "codigo": "auditor_ia", "nome": "Auditor de IA",
        "permissoes": ["ia.configurar", "acesso.ver_logs"]}).json()["id"]
    alvo = _criar(client, admin, "auditor@cge.go.gov.br", [forte])
    # conceder o papel a um usuário novo
    r = client.post(f"{ACESSO}/usuarios", headers=gerente, json={
        "email": "cupincha@cge.go.gov.br", "nome": "Cupincha", "senha": SENHA,
        "papel_ids": [forte]})
    assert r.status_code == 422 and "permissões que você não possui" in r.json()["detail"]
    # trocar a senha de quem já tem o papel (tomada de conta)
    r = client.put(f"{ACESSO}/usuarios/{alvo}", headers=gerente, json={
        "email": "auditor@cge.go.gov.br", "nome": "Auditor", "senha": "Tomada-de-conta-1",
        "papel_ids": [forte]})
    assert r.status_code == 422
    # papéis do sistema continuam concedíveis (a GEDA cadastra os órgãos publicadores)
    r = client.post(f"{ACESSO}/usuarios", headers=gerente, json={
        "email": "leitor@cge.go.gov.br", "nome": "Leitor", "senha": SENHA,
        "papel_ids": [_papel_id(client, admin, "analista_geda")]})
    assert r.status_code == 201


def test_gestor_de_papeis_nao_amplia_o_proprio_acesso(client, admin):
    papel = client.post(f"{ACESSO}/papeis", headers=admin, json={
        "codigo": "so_papeis", "nome": "Só papéis",
        "permissoes": ["acesso.gerenciar_papeis"]}).json()
    _criar(client, admin, "papeis@cge.go.gov.br", [papel["id"]])
    h = login(client, "papeis@cge.go.gov.br")
    # o próprio papel
    r = client.put(f"{ACESSO}/papeis/{papel['id']}", headers=h, json={
        "codigo": "so_papeis", "nome": "Só papéis",
        "permissoes": ["acesso.gerenciar_papeis", "ia.configurar"]})
    assert r.status_code == 422
    # papel do sistema
    pid = _papel_id(client, admin, "gerente_geda")
    r = client.put(f"{ACESSO}/papeis/{pid}", headers=h, json={
        "codigo": "gerente_geda", "nome": "Gerência", "permissoes": []})
    assert r.status_code == 422
    # papel novo com permissão que ele não tem
    r = client.post(f"{ACESSO}/papeis", headers=h, json={
        "codigo": "atalho", "nome": "Atalho", "permissoes": ["ia.configurar"]})
    assert r.status_code == 422 and "ia.configurar" in r.json()["detail"]
    # papel novo só com o que ele tem: permitido
    r = client.post(f"{ACESSO}/papeis", headers=h, json={
        "codigo": "copia", "nome": "Cópia", "permissoes": ["acesso.gerenciar_papeis"]})
    assert r.status_code == 201
    assert client.get(f"{ACESSO}/me", headers=h).json()["permissoes"] == [
        "acesso.gerenciar_papeis"]


def test_ultima_coleta_nao_mostra_o_solicitante_a_quem_nao_ve_o_inventario(client, admin, orgao):
    from app.core.db import SessionLocal
    from app.modules.inventario import service as inventario

    with SessionLocal() as db:
        inventario.iniciar(db, origem="manual", solicitante="admin@cge.go.gov.br", usuario_id=1)
    assert client.get(f"{API}/inventario/coletas/ultima",
                      headers=admin).json()["solicitada_por"] == "admin@cge.go.gov.br"
    assert client.get(f"{API}/inventario/coletas/ultima",
                      headers=orgao).json()["solicitada_por"] is None


@pytest.mark.parametrize("rota", ["/lgpd/varreduras", "/lgpd/correcoes", "/inventario/coletas",
                                  "/ia/uso"])
def test_limite_invalido_da_422(client, admin, rota):
    assert client.get(f"{API}{rota}?limite=-1", headers=admin).status_code == 422
    assert client.get(f"{API}{rota}?limite=999999999", headers=admin).status_code == 422


# ------------------------------------------------------------------ exportações
def test_sem_formula():
    assert sem_formula('=HYPERLINK("http://x","y")') == '\'=HYPERLINK("http://x","y")'
    assert sem_formula("+cmd|' /C calc'!A0").startswith("'+")
    assert sem_formula("@SUM(1+1)") == "'@SUM(1+1)"
    assert sem_formula("-12,5") == "-12,5" and sem_formula("+55") == "+55"
    assert sem_formula("Secretaria = SES") == "Secretaria = SES"


def test_exportacao_xlsx_grava_formula_como_texto(client, analista):
    r = client.post(f"{API}/relatorios/tabela/exportar", headers=analista, json={
        "titulo": "Teste", "colunas": ["=1+1", "b"], "formato": "xlsx",
        "linhas": [['=HYPERLINK("http://x","y")', "@SUM(1)"]]})
    assert r.status_code == 200
    ws = load_workbook(io.BytesIO(r.content)).active
    assert [c.data_type for linha in ws.iter_rows() for c in linha] == ["s"] * 4
    assert ws["A2"].value == '=HYPERLINK("http://x","y")'


def test_exportacao_pdf_recusa_tabela_grande_demais(client, analista):
    base = {"titulo": "Teste", "colunas": ["a"], "formato": "pdf"}
    r = client.post(f"{API}/relatorios/tabela/exportar", headers=analista,
                    json={**base, "linhas": [["x"]] * 5001})
    assert r.status_code == 422
    r = client.post(f"{API}/relatorios/tabela/exportar", headers=analista,
                    json={**base, "linhas": [["x" * 2001]]})
    assert r.status_code == 422  # célula longa demais
    r = client.post(f"{API}/relatorios/tabela/exportar", headers=analista,
                    json={**base, "linhas": [["x"]] * 50})
    assert r.status_code == 200


# ------------------------------------------------------------------ chamadas para fora
@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://x/y", "http://", "javascript:1",
                                 "http://169.254.169.254/latest/meta-data"])
def test_url_configuravel_recusada(url):
    with pytest.raises(rede.UrlNaoPermitida):
        rede.exigir_url_configuravel(url)


def test_url_configuravel_aceita_servico_interno():
    rede.exigir_url_configuravel("http://127.0.0.1:11434")  # Ollama e CKAN local são internos
    rede.exigir_url_configuravel("https://203.0.113.10/v1")


@pytest.mark.parametrize("url", ["http://127.0.0.1/x.csv", "http://10.0.0.5/x.csv",
                                 "http://192.168.1.1/x.csv", "http://[::1]/x.csv",
                                 "http://169.254.169.254/x", "file:///etc/passwd"])
def test_url_externa_recusa_rede_interna(url):
    with pytest.raises(rede.UrlNaoPermitida):
        rede.exigir_url_externa(url)
    if url.startswith("http://127"):
        rede.exigir_url_externa(url, ["127.0.0.1"])  # o próprio CKAN em uso é confiável


def test_provedor_de_ia_nao_devolve_o_corpo_da_resposta(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda *a, **k: httpx.Response(
        500, text="segredo interno do servidor"))
    with pytest.raises(AIProviderError) as erro:
        _http.get_json("http://127.0.0.1:9/v1/models", headers=None, timeout=1)
    assert "segredo" not in str(erro.value) and "HTTP 500" in str(erro.value)
    monkeypatch.setattr(httpx, "get", lambda *a, **k: httpx.Response(
        401, json={"error": {"message": "chave inválida"}}))
    with pytest.raises(AIProviderError, match="chave inválida"):
        _http.get_json("http://127.0.0.1:9/v1/models", headers=None, timeout=1)
    with pytest.raises(AIProviderError):
        _http.get_json("file:///etc/passwd", headers=None, timeout=1)


def test_perfis_recusam_url_que_nao_e_http(client, admin):
    r = client.post(f"{API}/ia/testar-conexao", headers=admin,
                    json={"tipo": "ollama", "base_url": "file:///etc/passwd"})
    assert r.status_code == 422
    r = client.post(f"{API}/ckan-config/perfis", headers=admin,
                    json={"nome": "Arquivo", "base_url": "file:///etc/passwd"})
    assert r.status_code == 422


def test_download_de_recurso_nao_segue_redirecionamento_para_a_rede_interna():
    pedidos = []

    def servidor(req: httpx.Request) -> httpx.Response:
        pedidos.append(str(req.url))
        if req.url.path == "/externo.csv":
            return httpx.Response(302, headers={"location": "http://127.0.0.1:5432/interno"})
        if req.url.path == "/volta.csv":
            return httpx.Response(302, headers={"location": "/final.csv"})
        return httpx.Response(200, content=b"a;b")

    c = CkanClient("http://portal", transport=httpx.MockTransport(servidor),
                   intervalo_download_s=0)
    with pytest.raises(CkanError, match="rede interna"):
        c.baixar("http://portal/externo.csv", 1000)
    assert pedidos == ["http://portal/externo.csv"]  # o endereço interno nem foi chamado
    with pytest.raises(CkanError, match="rede interna"):
        c.baixar("http://10.1.2.3/direto.csv", 1000)
    assert c.baixar("http://portal/volta.csv", 1000) == b"a;b"  # redirecionamento comum segue
