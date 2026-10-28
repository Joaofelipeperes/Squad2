"""Contrato JSON do módulo painel (o frontend segue exatamente estes nomes)."""
from datetime import date

from pydantic import BaseModel


class PlanoResumoOut(BaseModel):
    id: int
    nome: str


class OrganizacaoOut(BaseModel):
    """Linha da tela Organizações (US19). Campos `None` = indicador ainda não calculável
    (a tela mostra "aguardando vínculo" / "a definir")."""

    chave: str  # id da organização (texto), ou 'sigla:<SIGLA>' para sigla do PDA sem organização
    organizacao_id: int | None
    nome: str
    siglas: list[str]  # siglas usadas no PDA vigente para este órgão
    # Inventário do portal
    datasets_no_portal: int  # datasets ativos
    recursos_validos: int  # recursos atuais, sem dicionário de dados, de datasets ativos
    recursos_formato_fechado: int  # fora do parâmetro `formatos_abertos` (PBI-53)
    formatos_fechados: dict[str, int]  # formato → quantidade ("" = sem formato informado)
    # PDA vigente
    bases_previstas: int
    bases_vinculadas: int  # com dataset vinculado pelo ID
    bases_publicadas: int  # situação "Publicado" (só existe com vínculo)
    # "Em atraso" só entre as bases VINCULADAS (dataset fora do portal e prazo vencido): sem vínculo
    # não há como saber se a base já foi publicada. None = órgão sem nenhuma base vinculada.
    bases_em_atraso: int | None
    bases_proximas_do_prazo: int  # situação "Próximo do prazo" (planejamento; não acusa atraso)
    # Pendentes
    atualizacao_pct: float | None = None  # regra de atualização por periodicidade (PBI-27/28)
    riscos_lgpd: int | None = None  # módulo lgpd
    indice_atencao: str | None = None  # critério documentado (PBI-76/84)


class OrganizacoesOut(BaseModel):
    plano: PlanoResumoOut | None  # PDA vigente usado nas colunas de bases
    hoje: date
    formatos_abertos: list[str]
    organizacoes: list[OrganizacaoOut]
