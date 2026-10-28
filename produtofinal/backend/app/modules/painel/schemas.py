"""Contrato JSON do módulo painel (o frontend segue exatamente estes nomes)."""
from datetime import date, datetime

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


class KpisOut(BaseModel):
    """Cartões da Visão Geral (PBI-56). `None` = indicador ainda não calculável."""

    orgaos_monitorados: int  # organizações do inventário no escopo do usuário
    orgaos_no_pda: int  # órgãos com ao menos uma base no PDA vigente
    bases_previstas: int
    bases_vinculadas: int
    bases_publicadas: int
    bases_em_atraso: int | None  # só entre as vinculadas; None = nenhuma base vinculada
    bases_prazo_vencido: int  # sem vínculo e com prazo vencido: atraso NÃO confirmado
    datasets_publicados: int  # ativos no portal
    datasets_fora_do_portal: int  # excluídos ou privados depois de coletados
    recursos_monitorados: int  # atuais, sem dicionário, de datasets ativos
    datasets_sem_recurso: int  # PBI-51
    atualizacoes_em_atraso: int | None = None  # entre as vinculadas (ADR-0020); None = nenhuma
    possiveis_dados_pessoais: int | None = None  # módulo lgpd


class ContagemOut(BaseModel):
    rotulo: str
    total: int


class AlertaOut(BaseModel):
    tipo: str  # "PDA" | "Atualização" | "Inventário"
    orgao: str | None
    item: str  # base prevista ou dataset
    situacao: str
    prazo: date | None  # PDA: meta de abertura; Atualização: vencimento pela periodicidade
    destino: str  # rota da tela onde o item é tratado


class VisaoGeralOut(BaseModel):
    """Tela Visão Geral (Dashboard)."""

    plano: PlanoResumoOut | None  # PDA vigente
    hoje: date
    ultima_coleta: datetime | None  # fim da última coleta concluída (PBI-58)
    kpis: KpisOut
    situacoes_pda: list[ContagemOut]  # bases do PDA vigente por situação (ordem do filtro)
    # bases do PDA vigente por situação de atualização (periodicidade do PDA, ADR-0020), mais
    # "Aguardando vínculo" para as bases sem dataset
    situacoes_atualizacao: list[ContagemOut]
    atualizacao_estimada: int  # bases vinculadas cuja data veio da criação (sem last_modified)
    alertas: list[AlertaOut]  # os mais prioritários de cada tipo (até 10 por tipo)
    total_alertas: int
    alertas_por_tipo: dict[str, int]  # "PDA" | "Atualização" | "Inventário" → total
