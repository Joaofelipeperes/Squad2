"""Consultas e gravações do módulo acesso (ADR-0019): usuários, papéis, permissões e log.

Toda leitura passa pelas buscas genéricas do `Dao` (excluídos nunca aparecem) e toda gravação
por `save_generic`/`delete_generic` (auditoria preenchida, exclusão lógica)."""
from datetime import datetime

from sqlalchemy import func, or_, select

from app.core.dao import Dao
from app.modules.acesso.models import LogAcesso, Papel, PapelPermissao, Usuario, UsuarioPapel
from app.modules.inventario.models import Organizacao  # leitura cruzada (ver docs/modulos)


class AcessoDao(Dao):
    # ------------------------------------------------------------------ usuários
    def usuario(self, usuario_id: int) -> Usuario | None:
        return self.obter(Usuario, usuario_id)

    def usuario_por_email(self, email: str) -> Usuario | None:
        return self.buscar_um(select(Usuario).where(Usuario.email == email.lower()))

    def usuarios(self) -> list[Usuario]:
        return self.buscar_lista(select(Usuario).order_by(Usuario.nome))

    def admins_ativos(self) -> int:
        """Usuários ativos com o papel Administrador (`Papel.todas`)."""
        return self.buscar_valor(
            select(func.count(func.distinct(Usuario.id))).select_from(Usuario)
            .join(UsuarioPapel, UsuarioPapel.usuario_id == Usuario.id)
            .join(Papel, Papel.id == UsuarioPapel.papel_id)
            .where(Usuario.ativo, Papel.todas)) or 0

    def definir_papeis(self, usuario: Usuario, papeis: list[Papel]) -> None:
        """Vínculos usuário ↔ papel: exclui (logicamente) os que saíram e cria os novos."""
        atuais = self.buscar_lista(select(UsuarioPapel)
                                   .where(UsuarioPapel.usuario_id == usuario.id))
        novos = {p.id for p in papeis}
        saem = [v for v in atuais if v.papel_id not in novos]
        if saem:
            self.delete_generic(*saem)
        existentes = {v.papel_id for v in atuais}
        entram = [UsuarioPapel(usuario_id=usuario.id, papel_id=pid)
                  for pid in sorted(novos - existentes)]
        if entram:
            self.save_generic(*entram)
        self.expirar()  # `usuario.papeis` (só leitura) é recarregado com os vínculos atuais

    # ------------------------------------------------------------------ papéis
    def papel(self, papel_id: int) -> Papel | None:
        return self.obter(Papel, papel_id)

    def papel_por_codigo(self, codigo: str) -> Papel | None:
        return self.buscar_um(select(Papel).where(Papel.codigo == codigo))

    def papeis(self) -> list[Papel]:
        return self.buscar_lista(select(Papel).order_by(Papel.id))

    def papeis_por_ids(self, ids: list[int]) -> list[Papel]:
        return self.buscar_lista(select(Papel).where(Papel.id.in_(ids))) if ids else []

    def ids_de_papeis(self, codigos: list[str]) -> list[int]:
        return self.buscar_lista(select(Papel.id).where(Papel.codigo.in_(codigos)))

    def total_usuarios_do_papel(self, papel_id: int) -> int:
        return self.buscar_valor(
            select(func.count()).select_from(UsuarioPapel)
            .join(Usuario, Usuario.id == UsuarioPapel.usuario_id)
            .where(UsuarioPapel.papel_id == papel_id)) or 0

    def definir_permissoes(self, papel: Papel, codigos: list[str]) -> None:
        """Permissões do papel: exclui (logicamente) as que saíram e cria as novas."""
        atuais = self.buscar_lista(select(PapelPermissao)
                                   .where(PapelPermissao.papel_id == papel.id))
        novas = set(codigos)
        saem = [pp for pp in atuais if pp.permissao not in novas]
        if saem:
            self.delete_generic(*saem)
        existentes = {pp.permissao for pp in atuais}
        entram = [PapelPermissao(papel_id=papel.id, permissao=c)
                  for c in sorted(novas - existentes)]
        if entram:
            self.save_generic(*entram)
        self.expirar()  # `papel.permissoes` (só leitura) é recarregado

    def excluir_permissoes_fora_do_catalogo(self, validas: set[str]) -> int:
        return self.delete_generic_lote(PapelPermissao, PapelPermissao.permissao.not_in(validas))

    def excluir_papel(self, papel: Papel) -> None:
        """Exclusão lógica do papel e dos vínculos dele (usuários e permissões)."""
        self.delete_generic_lote(UsuarioPapel, UsuarioPapel.papel_id == papel.id)
        self.delete_generic_lote(PapelPermissao, PapelPermissao.papel_id == papel.id)
        self.delete_generic(papel)

    # ------------------------------------------------------------------ órgãos (inventário)
    def orgao(self, orgao_id: int | None) -> Organizacao | None:
        return self.obter(Organizacao, orgao_id)

    def orgaos(self) -> list[Organizacao]:
        return self.buscar_lista(select(Organizacao).order_by(Organizacao.titulo))

    def orgao_por_referencia(self, referencia: str) -> Organizacao | None:
        """Organização pelo `id_ckan` ou pelo `name` (CLI)."""
        return self.buscar_um(select(Organizacao).where(or_(
            Organizacao.id_ckan == referencia, Organizacao.name == referencia)))

    # ------------------------------------------------------------------ log de acesso
    def registrar_log(self, **campos) -> None:
        self.save_generic(LogAcesso(**campos))
        self.commit()

    def logs(self, usuario: str | None, desde: datetime | None, ate: datetime | None,
             limite: int) -> list[LogAcesso]:
        stmt = select(LogAcesso).order_by(LogAcesso.id.desc()).limit(limite)
        if usuario:
            stmt = stmt.where(LogAcesso.usuario.contains(usuario.lower()))
        if desde:
            stmt = stmt.where(LogAcesso.ocorrido_em >= desde)
        if ate:
            stmt = stmt.where(LogAcesso.ocorrido_em <= ate)
        return self.buscar_lista(stmt)
