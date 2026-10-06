import httpx

from app.integrations.ai.base import ChatMessage, ChatRequest, ProviderConfig
from app.integrations.ai.providers import _http
from app.integrations.ai.registry import build_provider

MOCK = {"nome": "Simulado", "tipo": "mock", "modelo": "eco", "execucao_local": True}
GEMINI = {"nome": "Gemini SECTI", "tipo": "gemini", "modelo": "gemini-2.5-flash",
          "api_key": "AIzaFAKE-1234567890abcd", "execucao_local": False}


def _criar(client, h, body):
    r = client.post("/api/v1/ia/perfis", json=body, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def test_tipos_disponiveis(client, admin):
    tipos = {t["tipo"] for t in client.get("/api/v1/ia/tipos-provedor", headers=admin).json()}
    assert {"gemini", "ollama", "openai_compat", "mock"} <= tipos


def test_chave_nunca_retorna(client, admin):
    p = _criar(client, admin, GEMINI)
    assert p["tem_chave"] and p["api_key_dica"] == "••••abcd"
    assert "api_key" not in p
    # atualizar sem mandar api_key mantém a chave
    body = {**GEMINI, "modelo": "gemini-2.5-pro"}
    body.pop("api_key")
    r = client.put(f"/api/v1/ia/perfis/{p['id']}", json=body, headers=admin)
    assert r.json()["tem_chave"] and r.json()["modelo"] == "gemini-2.5-pro"


def test_gemini_exige_chave(client, admin):
    body = {**GEMINI}
    body.pop("api_key")
    assert client.post("/api/v1/ia/perfis", json=body, headers=admin).status_code == 422


def test_politica_bloqueia_externo_em_tarefa_sensivel(client, admin):
    g = _criar(client, admin, GEMINI)
    r = client.put("/api/v1/ia/tarefas/classificacao_dp", json={"perfil_id": g["id"]}, headers=admin)
    assert r.status_code == 422 and "local" in r.json()["detail"]
    # a mesma chave comercial pode atender o Assistente
    r = client.put("/api/v1/ia/tarefas/assistente", json={"perfil_id": g["id"]}, headers=admin)
    assert r.status_code == 200


def test_nao_desmarca_local_de_perfil_em_uso_sensivel(client, admin):
    m = _criar(client, admin, MOCK)
    client.put("/api/v1/ia/tarefas/classificacao_dp", json={"perfil_id": m["id"]}, headers=admin)
    r = client.put(f"/api/v1/ia/perfis/{m['id']}", json={**MOCK, "execucao_local": False},
                   headers=admin)
    assert r.status_code == 422


def test_playground_e_registro_de_uso(client, admin):
    m = _criar(client, admin, MOCK)
    client.put("/api/v1/ia/tarefas/assistente", json={"perfil_id": m["id"]}, headers=admin)
    r = client.post("/api/v1/ia/playground", json={"mensagem": "Olá"}, headers=admin)
    assert r.status_code == 200 and "Olá" in r.json()["texto"]
    uso = client.get("/api/v1/ia/uso", headers=admin).json()
    assert uso[0]["sucesso"] and uso[0]["perfil_nome"] == "Simulado"


def test_fallback_quando_principal_falha(client, admin):
    ruim = _criar(client, admin, {"nome": "Ollama fora do ar", "tipo": "ollama",
                                  "modelo": "qwen2.5:7b", "base_url": "http://127.0.0.1:9",
                                  "execucao_local": True, "timeout_s": 5})
    m = _criar(client, admin, MOCK)
    client.put("/api/v1/ia/tarefas/assistente",
               json={"perfil_id": ruim["id"], "perfil_fallback_id": m["id"]}, headers=admin)
    r = client.post("/api/v1/ia/playground", json={"mensagem": "teste"}, headers=admin)
    assert r.status_code == 200 and r.json()["usou_fallback"] is True
    uso = client.get("/api/v1/ia/uso", headers=admin).json()
    assert [u["sucesso"] for u in uso][:2] == [True, False]


def test_sem_vinculo_retorna_409(client, admin):
    r = client.post("/api/v1/ia/playground", json={"mensagem": "x"}, headers=admin)
    assert r.status_code == 409


def test_excluir_perfil_em_uso_bloqueado(client, admin):
    m = _criar(client, admin, MOCK)
    client.put("/api/v1/ia/tarefas/assistente", json={"perfil_id": m["id"]}, headers=admin)
    assert client.delete(f"/api/v1/ia/perfis/{m['id']}", headers=admin).status_code == 409


# ---------------------------------------------------------- adaptadores (HTTP simulado)
def _fake_post(expected_url_part, payload, captured):
    def fake(url, json=None, headers=None, timeout=None):
        assert expected_url_part in url
        captured.update(url=url, json=json, headers=headers)
        return httpx.Response(200, json=payload, request=httpx.Request("POST", url))
    return fake


def test_adaptador_gemini(monkeypatch):
    cap = {}
    monkeypatch.setattr(_http.httpx, "post", _fake_post(":generateContent", {
        "candidates": [{"content": {"parts": [{"text": "Olá!"}]}}],
        "usageMetadata": {"promptTokenCount": 7, "candidatesTokenCount": 2}}, cap))
    p = build_provider(ProviderConfig(kind="gemini", model="gemini-2.5-flash", api_key="k" * 10))
    r = p.chat(ChatRequest(messages=[ChatMessage(role="system", content="Seja breve"),
                                     ChatMessage(role="user", content="Oi")], json_mode=True))
    assert r.text == "Olá!" and r.input_tokens == 7
    assert cap["json"]["systemInstruction"]["parts"][0]["text"] == "Seja breve"
    assert cap["json"]["generationConfig"]["responseMimeType"] == "application/json"
    assert cap["headers"]["x-goog-api-key"] == "k" * 10


def test_adaptador_ollama(monkeypatch):
    cap = {}
    monkeypatch.setattr(_http.httpx, "post", _fake_post("/api/chat", {
        "model": "qwen2.5:7b", "message": {"content": "ok"}, "prompt_eval_count": 3,
        "eval_count": 1}, cap))
    p = build_provider(ProviderConfig(kind="ollama", model="qwen2.5:7b"))
    r = p.chat(ChatRequest(messages=[ChatMessage(role="user", content="x")], json_mode=True))
    assert r.text == "ok" and cap["json"]["format"] == "json" and cap["json"]["stream"] is False


def test_adaptador_openai_compat(monkeypatch):
    cap = {}
    monkeypatch.setattr(_http.httpx, "post", _fake_post("/chat/completions", {
        "model": "m", "choices": [{"message": {"content": "resp"}}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 1}}, cap))
    p = build_provider(ProviderConfig(kind="openai_compat", model="m",
                                      base_url="http://vllm:8000/v1", api_key="abc"))
    r = p.chat(ChatRequest(messages=[ChatMessage(role="user", content="x")]))
    assert r.text == "resp" and cap["headers"]["Authorization"] == "Bearer abc"
