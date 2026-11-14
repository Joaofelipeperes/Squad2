"""Contrato JSON do módulo painel (o frontend segue exatamente estes nomes)."""
from datetime import date, datetime

from pydantic import BaseModel

from app.modules.lgpd.schemas import ResumoDadosPessoaisOut


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
    bases_publicadas: int  # "Publicado no prazo" + "Publicado fora do prazo" (só com vínculo)
    bases_publicadas_fora_do_prazo: int = 0  # 1º recurso depois do prazo do plano (ADR-0038)
    # "Em atraso" só entre as bases VINCULADAS (dataset fora do portal e prazo vencido): sem vínculo
    # não há como saber se a base já foi publicada. None = órgão sem nenhuma base vinculada.
    bases_em_atraso: int | None
    bases_proximas_do_prazo: int  # situação "Próximo do prazo" (planejamento; não acusa atraso)
    # Pendentes
    # Atualização de TODOS os datasets publicados do órgão (do PDA ou espontâneos) pela periodicidade
    # do campo "Atualização" do CKAN (ADR-0037), entre os que têm prazo (Atualizado, Próximo do
    # vencimento ou Atrasado); "Sem atualização periódica" fica fora. None = nenhum avaliado
    atualizacao_pct: float | None = None  # % dentro do prazo (Atualizado + Próximo do vencimento)
    atualizacoes_atrasadas: int | None = None
    atualizacoes_avaliadas: int = 0
    periodicidade_nao_informada: int = 0  # datasets com o campo "Atualização" vazio ou inválido
    # Riscos LGPD (módulo lgpd, só com `lgpd.acessar`): recursos com possível dado pessoal
    # aguardando revisão ou confirmado. None = sem acesso ao lgpd ou nenhum recurso do órgão varrido
    riscos_lgpd: int | None = None
    lgpd_recursos_analisados: int = 0  # recursos do órgão com varredura concluída
    lgpd_aguardando_revisao: int = 0  # achados
    lgpd_confirmados: int = 0  # achados confirmados e ainda não tratados
    risco_lgpd_pct: int | None = None  # riscos_lgpd / recursos analisados (0 a 100)
    # Índice de atenção (ADR-0030, PBI-76/84): média ponderada do risco LGPD e do atraso de
    # atualização, com pesos e faixas dos Parâmetros. None = sem nenhum dos dois componentes
    indice_atencao: str | None = None  # Alto | Médio | Baixo
    indice_atencao_valor: int | None = None  # 0 a 100
    atraso_atualizacao_pct: int | None = None  # componente do índice: atrasadas / avaliadas
    indice_atencao_componentes: list[str] = []  # o que entrou na média


class CriterioAtencaoOut(BaseModel):
    """Pesos e faixas do índice de atenção em vigor (parâmetros), para a tela explicar o cálculo."""

    peso_lgpd: int
    peso_atualizacao: int
    limite_medio: int
    limite_alto: int


class OrganizacoesOut(BaseModel):
    plano: PlanoResumoOut | None  # PDA vigente usado nas colunas de bases
    hoje: date
    formatos_abertos: list[str]
    lgpd_visivel: bool  # o usuário vê o módulo lgpd (sem isso, riscos_lgpd vem None)
    criterio_atencao: CriterioAtencaoOut
    organizacoes: list[OrganizacaoOut]


class KpisOut(BaseModel):
    """Cartões da Visão Geral (PBI-56). `None` = indicador ainda não calculável."""

    orgaos_monitorados: int  # organizações do inventário no escopo do usuário
    orgaos_no_pda: int  # órgãos com ao menos uma base no PDA vigente
    bases_previstas: int
    bases_vinculadas: int
    bases_publicadas: int  # no prazo + fora do prazo
    bases_publicadas_fora_do_prazo: int = 0  # 1º recurso depois do prazo do plano (ADR-0038)
    bases_em_atraso: int | None  # só entre as vinculadas; None = nenhuma base vinculada
    bases_prazo_vencido: int  # sem vínculo e com prazo vencido: atraso NÃO confirmado
    datasets_publicados: int  # ativos no portal
    datasets_fora_do_portal: int  # excluídos ou privados depois de coletados
    recursos_monitorados: int  # atuais, sem dicionário, de datasets ativos
    datasets_sem_recurso: int  # PBI-51
    # Entre TODOS os datasets publicados (ADR-0037); None = nenhum dataset no portal
    atualizacoes_em_atraso: int | None = None
    periodicidade_nao_informada: int | None = None  # campo "Atualização" vazio ou inválido
    possiveis_dados_pessoais: int | None = None  # achados aguardando revisão; None sem lgpd.acessar


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


class EspontaneasOut(BaseModel):
    """Bases espontâneas (US7, ADR-0026): datasets ativos no portal que nenhuma base do PDA vigente
    vincula pelo ID. Sem PDA vigente, todos os datasets ativos são espontâneos."""

    datasets_no_portal: int  # datasets ativos (escopo do usuário)
    no_pda: int  # ativos vinculados a alguma base do PDA vigente
    espontaneas: int
    por_orgao: list[ContagemOut]  # órgãos com mais espontâneas (até 10, o resto em "Outros")


class VisaoGeralOut(BaseModel):
    """Tela Visão Geral (Dashboard)."""

    plano: PlanoResumoOut | None  # PDA vigente
    hoje: date
    ultima_coleta: datetime | None  # fim da última coleta concluída (PBI-58)
    kpis: KpisOut
    situacoes_pda: list[ContagemOut]  # bases do PDA vigente por situação (ordem do filtro)
    # TODOS os datasets publicados por situação de atualização (campo "Atualização" do CKAN,
    # ADR-0037), na ordem do filtro
    situacoes_atualizacao: list[ContagemOut]
    atualizacao_por_tipo: list[ContagemOut] = []  # datasets publicados: Prevista no PDA × Espontânea
    atualizacao_estimada: int  # datasets cuja data veio da criação do recurso (sem last_modified)
    alertas: list[AlertaOut]  # os mais prioritários de cada tipo (até 10 por tipo)
    total_alertas: int
    alertas_por_tipo: dict[str, int]  # "PDA" | "Atualização" | "Inventário" → total
    espontaneas: EspontaneasOut
    dados_pessoais: ResumoDadosPessoaisOut | None  # None = usuário sem lgpd.acessar
