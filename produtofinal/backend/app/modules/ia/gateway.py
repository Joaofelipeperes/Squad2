"""Ponto ÚNICO de acesso à IA para os módulos de negócio.

    from app.modules.ia.gateway import AIGateway
    resp = AIGateway(db).chat(TarefaIA.ASSISTENTE, ChatRequest(messages=[...]))

O gateway: (1) resolve o perfil vinculado à tarefa, (2) aplica a política de dados sensíveis,
(3) chama o provedor, (4) tenta o perfil de contingência se o principal falhar e
(5) registra a chamada em ia_uso — sem guardar conteúdo.
"""
import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.integrations.ai.base import AIProviderError, ChatRequest, ChatResponse
from app.integrations.ai.policy import TAREFAS, TarefaIA, verificar
from app.integrations.ai.registry import build_provider
from app.modules.ia.models import PerfilProvedorIA, UsoIA, VinculoTarefaIA
from app.modules.ia.service import config_do_perfil

log = logging.getLogger(__name__)


class IANaoConfigurada(RuntimeError):
    pass


class AIGateway:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._permitir_externo = get_settings().ia_permitir_externo_para_sensivel

    def chat(self, tarefa: TarefaIA, request: ChatRequest) -> tuple[ChatResponse, PerfilProvedorIA, bool]:
        """Retorna (resposta, perfil que respondeu, usou_fallback)."""
        principal, reserva = self._perfis(tarefa)
        tentativas = [(principal, False)] + ([(reserva, True)] if reserva else [])
        ultimo_erro: Exception | None = None
        for perfil, is_fallback in tentativas:
            # defesa em profundidade: a política é checada de novo no momento da chamada
            verificar(tarefa, perfil.execucao_local, self._permitir_externo)
            try:
                resp = build_provider(config_do_perfil(perfil)).chat(request)
            except AIProviderError as exc:
                ultimo_erro = exc
                self._registrar(tarefa, perfil, is_fallback, erro=str(exc))
                log.warning("IA: perfil '%s' falhou na tarefa %s: %s", perfil.nome, tarefa, exc)
                continue
            self._registrar(tarefa, perfil, is_fallback, resp=resp)
            return resp, perfil, is_fallback
        raise AIProviderError(
            f"Nenhum modelo respondeu à tarefa '{TAREFAS[tarefa].rotulo}'. Último erro: {ultimo_erro}"
        ) from ultimo_erro

    def _perfis(self, tarefa: TarefaIA):
        v = self.db.get(VinculoTarefaIA, tarefa.value)
        principal = self.db.get(PerfilProvedorIA, v.perfil_id) if v and v.perfil_id else None
        if principal is None or not principal.ativo:
            raise IANaoConfigurada(
                f"Nenhum modelo ativo vinculado à tarefa '{TAREFAS[tarefa].rotulo}'. "
                "Configure em Administração › Modelos de IA.")
        reserva = (self.db.get(PerfilProvedorIA, v.perfil_fallback_id)
                   if v.perfil_fallback_id else None)
        return principal, reserva if reserva and reserva.ativo else None

    def _registrar(self, tarefa, perfil, fallback, resp: ChatResponse | None = None, erro=None):
        self.db.add(UsoIA(
            tarefa=tarefa.value, perfil_id=perfil.id, perfil_nome=perfil.nome,
            modelo=resp.model if resp else perfil.modelo, sucesso=resp is not None,
            usou_fallback=fallback, latencia_ms=resp.latency_ms if resp else None,
            tokens_entrada=resp.input_tokens if resp else None,
            tokens_saida=resp.output_tokens if resp else None,
            erro=(erro or "")[:500] or None,
        ))
        self.db.commit()
