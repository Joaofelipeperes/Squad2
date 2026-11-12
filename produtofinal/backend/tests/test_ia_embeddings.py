"""Embeddings pelo gateway e o raciocínio desligado do Ollama (Qwen3/3.5), sem rede."""
import pytest

from app.core.db import SessionLocal
from app.integrations.ai.base import AIProviderError, ChatMessage, ChatRequest, ProviderConfig
from app.integrations.ai.policy import TarefaIA
from app.integrations.ai.providers import ollama
from app.integrations.ai.registry import build_provider
from app.modules.ia.gateway import AIGateway

QWEN3 = ProviderConfig(kind="ollama", model="qwen3:8b")
QWEN25 = ProviderConfig(kind="ollama", model="qwen2.5:7b-instruct")


@pytest.fixture
def ollama_falso(monkeypatch):
    chamadas: list[dict] = []

    def falso(url, *, json, headers, timeout):
        chamadas.append({"url": url, "json": dict(json)})
        if url.endswith("/api/embed"):
            return {"embeddings": [[1.0, 0.0]] * len(json["input"]), "model": json["model"]}, 5
        if json["model"].startswith("qwen2.5") and "think" in json:
            raise AIProviderError('HTTP 400 em url: {"error":"qwen2.5 does not support thinking"}')
        return {"message": {"content": "<think>hm</think>{\"ok\": true}"}, "model": json["model"]}, 7

    monkeypatch.setattr(ollama, "post_json", falso)
    monkeypatch.setattr(ollama, "_SEM_THINK", set())
    return chamadas


def test_qwen3_recebe_think_false_e_bloco_think_sai(ollama_falso):
    r = build_provider(QWEN3).chat(ChatRequest(messages=[ChatMessage(role="user", content="oi")]))
    assert ollama_falso[0]["json"]["think"] is False and r.text == '{"ok": true}'


def test_modelo_sem_suporte_a_think_refaz_sem_o_parametro(ollama_falso):
    p = build_provider(QWEN25)
    p.chat(ChatRequest(messages=[ChatMessage(role="user", content="oi")]))
    assert "think" in ollama_falso[0]["json"] and "think" not in ollama_falso[1]["json"]
    p.chat(ChatRequest(messages=[ChatMessage(role="user", content="oi")]))
    assert len(ollama_falso) == 3 and "think" not in ollama_falso[2]["json"]   # já lembra


def test_embed_do_ollama(ollama_falso):
    r = build_provider(ProviderConfig(kind="ollama", model="bge-m3")).embed(["a", "b"])
    assert r.vectors == [[1.0, 0.0], [1.0, 0.0]] and ollama_falso[0]["url"].endswith("/api/embed")


def test_gateway_embed_respeita_tipo_da_tarefa_e_politica(client, admin, ollama_falso):
    def perfil(nome, modelo, local=True, tipo="ollama", **kw):
        r = client.post("/api/v1/ia/perfis", headers=admin, json={
            "nome": nome, "tipo": tipo, "modelo": modelo, "execucao_local": local, **kw})
        assert r.status_code == 201, r.text
        return r.json()["id"]

    bge = perfil("BGE", "bge-m3")
    externo = perfil("Claude", "claude-haiku-5-5", local=False, tipo="anthropic", api_key="sk-x")
    r = client.put("/api/v1/ia/tarefas/embeddings_dp", headers=admin, json={"perfil_id": externo})
    assert r.status_code == 422                                   # sensível: só local
    client.put("/api/v1/ia/tarefas/embeddings_dp", headers=admin, json={"perfil_id": bge})
    tarefas = {t["tarefa"]: t for t in client.get("/api/v1/ia/tarefas", headers=admin).json()}
    assert tarefas["embeddings_dp"]["tipo"] == "embeddings" and tarefas["assistente"]["tipo"] == "chat"

    with SessionLocal() as db:
        g = AIGateway(db)
        assert g.configurada(TarefaIA.EMBEDDINGS_DADO_PESSOAL)
        assert not g.configurada(TarefaIA.CLASSIFICACAO_DADO_PESSOAL)
        resp, p, _ = g.embed(TarefaIA.EMBEDDINGS_DADO_PESSOAL, ["Rua 1"])
        assert resp.vectors == [[1.0, 0.0]] and p.nome == "BGE"
        with pytest.raises(AIProviderError, match="embeddings"):
            g.chat(TarefaIA.EMBEDDINGS_DADO_PESSOAL,
                   ChatRequest(messages=[ChatMessage(role="user", content="x")]))

    teste = client.post(f"/api/v1/ia/perfis/{bge}/testar", headers=admin).json()
    assert teste["ok"] and "Embedding gerado (2 dimensões)" in teste["mensagem"]
    r = client.post("/api/v1/ia/playground", headers=admin,
                    json={"tarefa": "embeddings_dp", "mensagem": "x"})
    assert r.status_code == 409
