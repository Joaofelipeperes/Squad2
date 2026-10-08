from datetime import UTC, datetime
from types import SimpleNamespace

from app.modules.atualizacoes import service
from app.modules.atualizacoes.regras import UltimaAtualizacao, ultima_atualizacao_real


def _r(last_modified=None, created=None, dicionario=False):
    return SimpleNamespace(last_modified=last_modified, created=created,
                           eh_dicionario_dados=dicionario)


def test_maior_last_modified_ignorando_dicionario():
    recursos = [
        _r(datetime(2026, 8, 1, tzinfo=UTC)),
        _r(datetime(2026, 9, 15, tzinfo=UTC)),
        _r(datetime(2026, 10, 1, tzinfo=UTC), dicionario=True),  # nunca conta
    ]
    assert ultima_atualizacao_real(recursos) == UltimaAtualizacao(
        datetime(2026, 9, 15, tzinfo=UTC), False)


def test_sem_last_modified_usa_created_e_marca_estimada():
    recursos = [_r(created=datetime(2026, 5, 1, tzinfo=UTC)),
                _r(created=datetime(2026, 6, 1, tzinfo=UTC)),
                _r(datetime(2026, 9, 1, tzinfo=UTC), dicionario=True)]
    r = ultima_atualizacao_real(recursos)
    assert r.data == datetime(2026, 6, 1, tzinfo=UTC) and r.estimada is True


def test_sem_recurso_valido():
    assert ultima_atualizacao_real([]) == UltimaAtualizacao(None, False)
    assert ultima_atualizacao_real(None) == UltimaAtualizacao(None, False)
    assert ultima_atualizacao_real(
        [_r(datetime(2026, 9, 1, tzinfo=UTC), dicionario=True)]) == UltimaAtualizacao(None, False)
    assert ultima_atualizacao_real([_r()]) == UltimaAtualizacao(None, False)


def test_aceita_dict_iso_e_datetime_sem_fuso():
    recursos = [
        {"last_modified": "2026-09-01T08:00:00", "eh_dicionario_dados": False},
        {"last_modified": datetime(2026, 9, 2, 8, 0), "created": None},  # noqa: DTZ001 (→ UTC)
        {"last_modified": "2026-12-31T00:00:00", "eh_dicionario_dados": True},
        # metadata_modified do dataset nunca entra, mesmo se vier junto
        {"metadata_modified": "2027-01-01T00:00:00", "created": "2020-01-01T00:00:00"},
    ]
    assert ultima_atualizacao_real(recursos) == UltimaAtualizacao(
        datetime(2026, 9, 2, 8, 0, tzinfo=UTC), False)


def test_service_delega_para_regras():
    r = service.ultima_atualizacao_real([_r(datetime(2026, 9, 1, tzinfo=UTC))])
    assert isinstance(r, UltimaAtualizacao) and r.data == datetime(2026, 9, 1, tzinfo=UTC)
