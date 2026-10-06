"""Contratos do módulo envio (órgão publicador). Implementar somente após decisão de escopo."""


def datasets_do_orgao(db, user):
    """Lista datasets do órgão do usuário (filtrar_por_orgao sobre inventario.Dataset)."""
    raise NotImplementedError


def enviar_recurso(db, user, dataset_id: str, arquivo) -> None:
    """Exige envio.enviar_recurso + exigir_mesmo_orgao(user, dataset.organizacao_id).
    Escreve no CKAN — depende de credencial, autorização e alteração de escopo do PGP."""
    raise NotImplementedError
