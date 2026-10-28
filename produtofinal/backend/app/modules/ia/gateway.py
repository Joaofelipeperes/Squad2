"""Ponto ÚNICO de acesso à IA para os módulos de negócio.

    from app.modules.ia.gateway import AIGateway
    resp = AIGateway(db).chat(TarefaIA.ASSISTENTE, ChatRequest(messages=[...]))

O gateway: (1) resolve o perfil vinculado à tarefa, (2) aplica a política de dados sensíveis,
(3) chama o provedor, (4) tenta o perfil de contingência se o principal falhar e
(5) registra a chamada em ia_uso — sem guardar conteúdo.
"""
import logging
from collections.abc import Callable
from typing import TypeVar

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.integrations.ai.base import AIProviderError, ChatRequest, ChatResponse, EmbedResponse
from app.integrations.ai.policy import TAREFAS, TarefaIA, verificar
from app.integrations.ai.registry import build_provider
from app.modules.ia.dao import IaDao
from app.modules.ia.models import PerfilProvedorIA, UsoIA
from app.modules.ia.service import config_do_perfil

log = logging.getLogger(__name__)
R = TypeVar("R", ChatResponse, EmbedResponse)


class IANaoConfigurada(RuntimeError):
    pass


class AIGateway:
    def __init__(self, db: Session) -> None:
        self.dao = IaDao(db)
        self._permitir_externo = get_settings().ia_permitir_externo_para_sensivel

    def chat(self, tarefa: TarefaIA, request: ChatRequest) -> tuple[ChatResponse, PerfilProvedorIA, bool]:
        """Retorna (resposta, perfil que respondeu, usou_fallback)."""
        self._exigir_tipo(tarefa, "chat")
        return self._executar(tarefa, lambda prov: prov.chat(request))

    def embed(self, tarefa: TarefaIA, textos: list[str]
              ) -> tuple[EmbedResponse, PerfilProvedorIA, bool]:
        """Embeddings pelo perfil vinculado a uma tarefa do tipo `embeddings`."""
        self._exigir_tipo(tarefa, "embeddings")
        return self._executar(tarefa, lambda prov: prov.embed(textos))

    def configurada(self, tarefa: TarefaIA) -> bool:
        """Há perfil ativo vinculado à tarefa? (para etapas opcionais, ex.: filtro semântico)"""
        try:
            self._perfis(tarefa)
        except IANaoConfigurada:
            return False
        return True

    @staticmethod
    def _exigir_tipo(tarefa: TarefaIA, tipo: str) -> None:
        if TAREFAS[tarefa].tipo != tipo:
            raise AIProviderError(f"A tarefa '{TAREFAS[tarefa].rotulo}' é do tipo "
                                  f"{TAREFAS[tarefa].tipo}, não {tipo}.")

    def _executar(self, tarefa: TarefaIA, chamar: Callable[..., R]
                  ) -> tuple[R, PerfilProvedorIA, bool]:
        principal, reserva = self._perfis(tarefa)
        tentativas = [(principal, False)] + ([(reserva, True)] if reserva else [])
        ultimo_erro: Exception | None = None
        for perfil, is_fallback in tentativas:
            # defesa em profundidade: a política é checada de novo no momento da chamada
            verificar(tarefa, perfil.execucao_local, self._permitir_externo)
            try:
                resp = chamar(build_provider(config_do_perfil(perfil)))
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
        v = self.dao.vinculo(tarefa.value)
        principal = self.dao.perfil(v.perfil_id) if v and v.perfil_id else None
        if principal is None or not principal.ativo:
            raise IANaoConfigurada(
                f"Nenhum modelo ativo vinculado à tarefa '{TAREFAS[tarefa].rotulo}'. "
                "Configure em Administração › Modelos de IA.")
        reserva = self.dao.perfil(v.perfil_fallback_id) if v.perfil_fallback_id else None
        return principal, reserva if reserva and reserva.ativo else None

    def _registrar(self, tarefa, perfil, fallback, resp: ChatResponse | EmbedResponse | None = None,
                   erro=None):
        self.dao.registrar_uso(UsoIA(
            tarefa=tarefa.value, perfil_id=perfil.id, perfil_nome=perfil.nome,
            modelo=resp.model if resp else perfil.modelo, sucesso=resp is not None,
            usou_fallback=fallback, latencia_ms=resp.latency_ms if resp else None,
            tokens_entrada=resp.input_tokens if resp else None,
            tokens_saida=getattr(resp, "output_tokens", None) if resp else None,
            erro=(erro or "")[:500] or None,
        ))
