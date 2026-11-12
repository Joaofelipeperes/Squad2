"""Adaptador Anthropic Claude: formato da requisição e da resposta, sem rede."""
import pytest

from app.integrations.ai.base import AIProviderError, ChatMessage, ChatRequest, ProviderConfig
from app.integrations.ai.providers import anthropic
from app.integrations.ai.registry import build_provider

CFG = ProviderConfig(kind="anthropic", model="claude-haiku-5-5", api_key="sk-ant-FAKE",
                     temperature=0.2, max_tokens=700)
RESPOSTA = {"model": "claude-haiku-5-5", "stop_reason": "end_turn",
            "content": [{"type": "thinking", "thinking": ""}, {"type": "text", "text": "Olá"},
                        {"type": "text", "text": "!"}],
            "usage": {"input_tokens": 120, "output_tokens": 4}}


class _Chamadas(list):
    """Requisições feitas (itens) + respostas/erros a devolver em ordem (`respostas`)."""

    def __init__(self):
        super().__init__()
        self.respostas: list = []


@pytest.fixture
def chamadas(monkeypatch):
    feitas = _Chamadas()
    respostas = feitas.respostas

    def falso(url, *, json, headers, timeout):
        feitas.append({"url": url, "json": json, "headers": headers})
        r = respostas.pop(0) if respostas else RESPOSTA
        if isinstance(r, Exception):
            raise r
        return r, 42

    monkeypatch.setattr(anthropic, "post_json", falso)
    monkeypatch.setattr(anthropic, "_SEM_TEMPERATURA", set())
    return feitas


def test_requisicao_e_resposta(chamadas):
    req = ChatRequest(messages=[
        ChatMessage(role="system", content="Seja breve."),
        ChatMessage(role="assistant", content="Olá! Sou o assistente."),  # saudação descartada
        ChatMessage(role="user", content="Pergunta 1"),
        ChatMessage(role="assistant", content="Resposta 1"),
        ChatMessage(role="user", content="Contexto"),
        ChatMessage(role="user", content="Pergunta 2"),                   # juntada à anterior
    ])
    resp = build_provider(CFG).chat(req)
    corpo = chamadas[0]["json"]
    assert chamadas[0]["url"] == "https://api.anthropic.com/v1/messages"
    assert chamadas[0]["headers"] == {"x-api-key": "sk-ant-FAKE", "anthropic-version": "2023-06-01"}
    assert corpo["system"] == "Seja breve."
    assert [m["role"] for m in corpo["messages"]] == ["user", "assistant", "user"]
    assert corpo["messages"][-1]["content"] == "Contexto\n\nPergunta 2"
    assert corpo["thinking"] == {"type": "disabled"} and corpo["max_tokens"] == 700
    assert corpo["temperature"] == 0.2
    assert (resp.text, resp.input_tokens, resp.output_tokens, resp.latency_ms) == ("Olá!", 120, 4, 42)


def test_modelo_que_recusa_temperatura(chamadas):
    chamadas.respostas.append(AIProviderError(
        'HTTP 400 em url: {"error":{"message":"temperature is not supported"}}'))
    p = build_provider(CFG)
    assert p.chat(ChatRequest(messages=[ChatMessage(role="user", content="oi")])).text == "Olá!"
    assert "temperature" in chamadas[0]["json"] and "temperature" not in chamadas[1]["json"]
    p.chat(ChatRequest(messages=[ChatMessage(role="user", content="oi")]))  # já lembra
    assert len(chamadas) == 3 and "temperature" not in chamadas[2]["json"]


def test_outros_erros_sobem(chamadas):
    chamadas.respostas.append(AIProviderError("HTTP 401 em url: invalid x-api-key"))
    with pytest.raises(AIProviderError, match="401"):
        build_provider(CFG).chat(ChatRequest(messages=[ChatMessage(role="user", content="oi")]))
    assert len(chamadas) == 1


def test_sem_mensagem_do_usuario(chamadas):
    with pytest.raises(AIProviderError):
        build_provider(CFG).chat(ChatRequest(messages=[ChatMessage(role="system", content="x")]))


def test_exige_chave_e_aparece_na_tela(client, admin):
    with pytest.raises(AIProviderError):
        build_provider(CFG.model_copy(update={"api_key": None}))
    tipos = {t["tipo"]: t for t in client.get("/api/v1/ia/tipos-provedor", headers=admin).json()}
    assert tipos["anthropic"]["exige_chave"] and not tipos["anthropic"]["local_por_padrao"]
    assert "claude-haiku-5-5" in tipos["anthropic"]["modelos_sugeridos"]


def test_politica_nao_deixa_claude_em_tarefa_sensivel(client, admin):
    p = client.post("/api/v1/ia/perfis", headers=admin, json={
        "nome": "Claude Haiku", "tipo": "anthropic", "modelo": "claude-haiku-5-5",
        "api_key": "sk-ant-FAKE-1234", "execucao_local": False}).json()
    r = client.put("/api/v1/ia/tarefas/classificacao_dp", json={"perfil_id": p["id"]}, headers=admin)
    assert r.status_code == 422
    r = client.put("/api/v1/ia/tarefas/assistente", json={"perfil_id": p["id"]}, headers=admin)
    assert r.status_code == 200


def test_workspace_vai_no_cabecalho(chamadas):
    cfg = CFG.model_copy(update={"extra": {"workspace_id": " wrkspc_123 "}})
    build_provider(cfg).chat(ChatRequest(messages=[ChatMessage(role="user", content="oi")]))
    assert chamadas[0]["headers"]["anthropic-workspace-id"] == "wrkspc_123"
    build_provider(CFG).chat(ChatRequest(messages=[ChatMessage(role="user", content="oi")]))
    assert "anthropic-workspace-id" not in chamadas[1]["headers"]


def test_perfil_guarda_workspace_e_ignora_campo_desconhecido(client, admin, monkeypatch):
    body = {"nome": "Claude WS", "tipo": "anthropic", "modelo": "claude-haiku-5-5",
            "api_key": "sk-ant-FAKE-1234", "execucao_local": False,
            "extra": {"workspace_id": "wrkspc_abc", "outro": "x"}}
    p = client.post("/api/v1/ia/perfis", headers=admin, json=body).json()
    assert p["extra"] == {"workspace_id": "wrkspc_abc"}
    body.pop("api_key")
    r = client.put(f"/api/v1/ia/perfis/{p['id']}", headers=admin, json={**body, "extra": {}})
    assert r.json()["extra"] == {} and r.json()["tem_chave"]
    campos = {t["tipo"]: [c["name"] for c in t["campos"]]
              for t in client.get("/api/v1/ia/tipos-provedor", headers=admin).json()}
    assert "workspace_id" in campos["anthropic"] and "workspace_id" not in campos["gemini"]

    vistos = {}

    def falso(url, *, headers, timeout):
        vistos.update(headers)
        return {"data": [{"id": "claude-haiku-5-5"}]}

    monkeypatch.setattr(anthropic, "get_json", falso)
    r = client.post("/api/v1/ia/testar-conexao", headers=admin, json={
        "tipo": "anthropic", "modelo": "claude-haiku-5-5", "perfil_id": p["id"],
        "extra": {"workspace_id": "wrkspc_xyz"}}).json()
    assert r["ok"] and vistos["anthropic-workspace-id"] == "wrkspc_xyz"
    assert vistos["x-api-key"] == "sk-ant-FAKE-1234"   # chave salva reaproveitada
