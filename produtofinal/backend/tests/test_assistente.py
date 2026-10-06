def test_assistente_usa_modelo_vinculado(client, admin, analista):
    m = client.post("/api/v1/ia/perfis", headers=admin, json={
        "nome": "Simulado", "tipo": "mock", "modelo": "eco", "execucao_local": True}).json()
    client.put("/api/v1/ia/tarefas/assistente", json={"perfil_id": m["id"]}, headers=admin)
    r = client.post("/api/v1/assistente/perguntar", json={"pergunta": "Como está a SES?"},
                    headers=analista)
    assert r.status_code == 200 and r.json()["modelo"] == "eco"


def test_assistente_sem_modelo(client, analista):
    r = client.post("/api/v1/assistente/perguntar", json={"pergunta": "Oi?"}, headers=analista)
    assert r.status_code == 503


def test_orgao_nao_usa_assistente(client, orgao):
    r = client.post("/api/v1/assistente/perguntar", json={"pergunta": "Oi?"}, headers=orgao)
    assert r.status_code == 403


def test_contexto_respeita_escopo_de_orgao():
    from app.core.db import SessionLocal
    from app.core.deps import UsuarioAtual
    from app.modules.assistente.service import montar_contexto
    from app.modules.inventario.models import Coleta

    with SessionLocal() as db:
        db.add(Coleta(status="ok", total_organizacoes=2, total_datasets=10, total_recursos=30))
        db.commit()
        restrito = UsuarioAtual(id=0, email="x", nome="x", orgao_id="org-seduc", papeis=[],
                                permissoes=frozenset({"assistente.usar"}))
        ctx = montar_contexto(db, "Como está a Secretaria da Saúde?", restrito)
        assert "Saúde" not in ctx and "Totais" not in ctx and "Educação" in ctx
