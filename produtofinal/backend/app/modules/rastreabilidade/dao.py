"""Acesso ao banco do módulo rastreabilidade (ADR-0019): eventos, sincronizações e fotografias dos
órgãos, mais as leituras do inventário que a sincronização usa.

A sincronização é ação do sistema (`usuario_id` None). Os eventos guardam dataset, órgão e recurso
pelo ID do CKAN (`*_id_ckan`); o escopo de órgão do usuário (`organizacao.id`) é aplicado
traduzindo o `organizacao_id_ckan` do evento para o `id` do órgão no inventário.
"""
from datetime import datetime

from sqlalchemy import func, or_, select

from app.core.dao import Dao
from app.core.deps import UsuarioAtual, filtrar_por_orgao
from app.modules.inventario.models import Coleta, Dataset, DatasetSnapshot, Organizacao, Recurso
from app.modules.rastreabilidade.models import (
    EventoRastreabilidade,
    OrgaoSnapshot,
    SincronizacaoRastreabilidade,
)

Ev = EventoRastreabilidade


def _orgao_do_evento():
    """`organizacao.id` do órgão do evento (subconsulta correlacionada pelo ID do CKAN)."""
    return (select(Organizacao.id).where(Organizacao.id_ckan == Ev.organizacao_id_ckan)
            .scalar_subquery())


class RastreabilidadeDao(Dao):
    # ------------------------------------------------------------------ sincronização
    def criar_sincronizacao(self) -> SincronizacaoRastreabilidade:
        sinc = self.save_generic(SincronizacaoRastreabilidade())
        self.commit()
        return sinc

    def obter_sincronizacao(self, sinc_id: int) -> SincronizacaoRastreabilidade | None:
        return self.obter(SincronizacaoRastreabilidade, sinc_id)

    def ultima_sincronizacao(self) -> SincronizacaoRastreabilidade | None:
        return self.buscar_um(select(SincronizacaoRastreabilidade)
                              .order_by(SincronizacaoRastreabilidade.id.desc()).limit(1))

    def marca_atividades_nativas(self) -> datetime | None:
        return self.buscar_valor(select(func.max(SincronizacaoRastreabilidade.atividades_nativas_ate)))

    # ------------------------------------------------------------------ inventário (leitura)
    def datasets_para_auditoria(self) -> list[tuple[str, str, str | None]]:
        """(id_ckan, título, id_ckan do órgão) de todos os datasets do inventário, inclusive os
        que saíram do portal."""
        return self.buscar_linhas(
            select(Dataset.id_ckan, Dataset.titulo, Organizacao.id_ckan)
            .outerjoin(Organizacao, Organizacao.id == Dataset.organizacao_id)
            .where(Dataset.id_ckan.is_not(None)).order_by(Dataset.id_ckan))

    def nomes_recursos(self) -> dict[str, str | None]:
        return dict(self.buscar_linhas(select(Recurso.id_ckan, Recurso.nome)
                                       .where(Recurso.id_ckan.is_not(None))))

    def ultima_coleta_ok_ate(self, quando: datetime) -> int | None:
        return self.buscar_valor(select(Coleta.id).where(Coleta.status == "ok",
                                                         Coleta.finalizada_em <= quando)
                                 .order_by(Coleta.finalizada_em.desc()).limit(1))

    def dataset_na_coleta(self, coleta_id: int, dataset_id_ckan: str) -> bool:
        """O dataset tem fotografia na coleta (estava na busca pública dela)."""
        return bool(self.buscar_valor(
            select(func.count()).select_from(DatasetSnapshot)
            .join(Dataset, Dataset.id == DatasetSnapshot.dataset_id)
            .where(DatasetSnapshot.coleta_id == coleta_id, Dataset.id_ckan == dataset_id_ckan)))

    def organizacoes(self) -> list[Organizacao]:
        return self.buscar_lista(select(Organizacao).where(Organizacao.id_ckan.is_not(None)))

    def ids_ckan_datasets_com_texto(self, busca: str, contem) -> list[str]:
        return [i for i, titulo, name in self.buscar_linhas(
                select(Dataset.id_ckan, Dataset.titulo, Dataset.name)
                .where(Dataset.id_ckan.is_not(None)))
                if contem(busca, titulo, name)]

    # ------------------------------------------------------------------ eventos (gravação)
    def salvar(self, *objs) -> None:
        self.save_generic(*objs)

    def atividades_conhecidas(self) -> set[str]:
        return set(self.buscar_lista(select(Ev.ckan_activity_id)
                                     .where(Ev.ckan_activity_id.is_not(None))))

    def inicio_auditoria(self, origem: str) -> datetime | None:
        return self.buscar_valor(select(func.min(Ev.ocorrido_em)).where(Ev.origem == origem))

    def datas_eventos(self, dataset_id_ckan: str, origem: str) -> list[datetime]:
        return self.buscar_lista(select(Ev.ocorrido_em).where(Ev.dataset_id_ckan == dataset_id_ckan,
                                                              Ev.origem == origem))

    def detalhes_eventos(self, dataset_id_ckan: str) -> list[tuple[datetime, list]]:
        return self.buscar_linhas(select(Ev.ocorrido_em, Ev.detalhes)
                                  .where(Ev.dataset_id_ckan == dataset_id_ckan))

    def ultimas_fotografias_orgaos(self) -> dict[str, OrgaoSnapshot]:
        ultimos_ids = (select(func.max(OrgaoSnapshot.id))
                       .group_by(OrgaoSnapshot.organizacao_id_ckan))
        return {s.organizacao_id_ckan: s for s in
                self.buscar_lista(select(OrgaoSnapshot).where(OrgaoSnapshot.id.in_(ultimos_ids)))}

    # ------------------------------------------------------------------ tela (PBI-85)
    @staticmethod
    def _no_escopo(stmt, user: UsuarioAtual):
        return filtrar_por_orgao(stmt, _orgao_do_evento(), user)

    def orgaos_com_eventos(self, user: UsuarioAtual) -> set[str]:
        return {o for o in self.buscar_lista(
            self._no_escopo(select(Ev.organizacao_id_ckan).distinct(), user)) if o}

    def eventos(self, user: UsuarioAtual, *, tipo: str | None, orgao: int | None,
                dataset: str | None, condicao_busca, desde: datetime | None,
                ate: datetime | None, antigos: bool, limite: int) -> tuple[int, list[Ev]]:
        """(total que atende aos filtros, eventos até o limite, ordenados por data)."""
        stmt = self._no_escopo(select(Ev), user)
        if tipo:
            stmt = stmt.where(Ev.tipo == tipo)
        if orgao is not None:
            stmt = stmt.where(_orgao_do_evento() == orgao)
        if dataset:
            stmt = stmt.where(Ev.dataset_id_ckan == dataset)
        if condicao_busca is not None:
            stmt = stmt.where(condicao_busca)
        if desde:
            stmt = stmt.where(Ev.ocorrido_em >= desde)
        if ate:
            stmt = stmt.where(Ev.ocorrido_em <= ate)
        total = self.buscar_valor(select(func.count()).select_from(stmt.subquery())) or 0
        if antigos:
            ordenacao = (Ev.ocorrido_em.asc(), Ev.id.asc())
        else:
            ordenacao = (Ev.ocorrido_em.desc(), Ev.id.desc())
        return total, self.buscar_lista(stmt.order_by(*ordenacao).limit(limite))

    @staticmethod
    def condicao_busca(texto: str, datasets_id_ckan: list[str], orgaos_id_ckan: list[str],
                       origem_orgao: str):
        """Evento de dataset cujo ID do CKAN está na lista ou é o texto, ou cujo título na data do
        evento contém o texto; evento do cadastro de órgão cujo órgão está na lista."""
        return or_(Ev.dataset_id_ckan.in_(datasets_id_ckan),
                   Ev.dataset_id_ckan == texto,
                   Ev.dataset_titulo.icontains(texto, autoescape=True),
                   (Ev.origem == origem_orgao) & Ev.organizacao_id_ckan.in_(orgaos_id_ckan))

    def evento_visivel(self, user: UsuarioAtual, evento_id: int) -> Ev | None:
        return self.buscar_um(self._no_escopo(select(Ev), user).where(Ev.id == evento_id))
