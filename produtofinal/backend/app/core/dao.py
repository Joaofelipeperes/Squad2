"""DAO genérico (ADR-0019): a ÚNICA porta de acesso ao banco.

Cada módulo cria `app/modules/<id>/dao.py` com uma classe que herda de `Dao` e define as consultas
do módulo; services, routers e jobs nunca chamam a sessão direto (guarda em
`tests/test_guardas_do_projeto.py`). As consultas do módulo montam o `select` e o entregam às
funções genéricas desta classe, que:

- **leitura** (`buscar*`, `obter`): acrescentam `deleted = false` a TODA tabela da consulta —
  inclusive joins, subconsultas e relacionamentos carregados a partir dela;
- **gravação** (`save_generic`): preenchem `created`/`created_id` na criação e
  `changed`/`changed_id` em toda gravação, com o usuário do DAO;
- **exclusão** (`delete_generic`): exclusão lógica (`deleted = true` + `changed`/`changed_id`).
  Nada é apagado fisicamente.
"""
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, TypeVar

from sqlalchemy import Executable, Result, Select, inspect, select, update
from sqlalchemy.orm import Session, with_loader_criteria

from app.core.db import Base, utcnow

M = TypeVar("M", bound=Base)


def _so_ativos(cls):
    return cls.deleted.is_(False)


class Dao:
    """Base de todos os DAOs. `usuario_id` = quem está agindo (vai para `created_id` e
    `changed_id`); None = sistema (coleta agendada, CLI, migração)."""

    def __init__(self, db: Session, usuario_id: int | None = None) -> None:
        self.db = db
        self.usuario_id = usuario_id

    @classmethod
    def de(cls, db: Session, user: Any = None):
        """Atalho a partir do usuário da requisição (`UsuarioAtual` ou `Usuario`; None = sistema)."""
        return cls(db, getattr(user, "id", None))

    # ------------------------------------------------------------------ leitura
    def _sem_excluidos(self, stmt: Executable) -> Executable:
        return stmt.options(with_loader_criteria(Base, _so_ativos, include_aliases=True))

    def buscar(self, stmt: Executable) -> Result:
        """Executa a consulta (select ou update) sem os registros excluídos de nenhuma tabela."""
        return self.db.execute(self._sem_excluidos(stmt))

    def buscar_lista(self, stmt: Select) -> list:
        """Primeira coluna de cada linha (ex.: `select(Modelo)` → lista de objetos)."""
        return list(self.buscar(stmt).scalars().all())

    def buscar_um(self, stmt: Select):
        """Primeira coluna da primeira linha, ou None."""
        return self.buscar(stmt).scalars().first()

    def buscar_valor(self, stmt: Select):
        """Valor único (ex.: `select(func.count())…`), ou None."""
        return self.buscar(stmt).scalar()

    def buscar_linhas(self, stmt: Select) -> list:
        """Linhas completas (tuplas), para consultas com várias colunas."""
        return list(self.buscar(stmt).all())

    def obter(self, modelo: type[M], id_: int | None) -> M | None:
        """Registro ativo pelo `id`; excluído ou inexistente → None."""
        if id_ is None:
            return None
        return self.buscar_um(select(modelo).where(modelo.id == id_))

    # ------------------------------------------------------------------ gravação
    def save_generic(self, *objs: Base) -> Base:
        """Cria ou atualiza registros com a auditoria preenchida. Retorna o primeiro."""
        agora = utcnow()
        for obj in objs:
            if not inspect(obj).has_identity:  # novo
                obj.created, obj.created_id = agora, self.usuario_id
            obj.changed, obj.changed_id = agora, self.usuario_id
            self.db.add(obj)
        self.db.flush()
        return objs[0] if objs else None

    def delete_generic(self, *objs: Base) -> None:
        """Exclusão lógica: marca `deleted` e registra quem e quando (`changed`/`changed_id`)."""
        for obj in objs:
            obj.deleted = True
        self.save_generic(*objs)

    def update_generic(self, modelo: type[M], *condicoes, **valores) -> int:
        """Atualização em lote dos registros ATIVOS que atendem `condicoes`, com auditoria.
        Retorna quantos registros foram alterados."""
        valores.setdefault("changed", utcnow())
        valores.setdefault("changed_id", self.usuario_id)
        stmt = update(modelo).where(*condicoes).values(**valores)
        return self.buscar(stmt.execution_options(synchronize_session="fetch")).rowcount

    def delete_generic_lote(self, modelo: type[M], *condicoes) -> int:
        """Exclusão lógica em lote dos registros ativos que atendem `condicoes`."""
        return self.update_generic(modelo, *condicoes, deleted=True)

    # ------------------------------------------------------------------ transação
    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

    def flush(self) -> None:
        self.db.flush()

    def expirar(self) -> None:
        """Descarta o estado em memória (próxima leitura vem do banco)."""
        self.db.expire_all()

    def recarregar(self, obj: Base) -> None:
        self.db.refresh(obj)

    @contextmanager
    def transacao(self) -> Iterator[None]:
        """Commit ao final; qualquer erro → rollback e propaga."""
        try:
            yield
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
