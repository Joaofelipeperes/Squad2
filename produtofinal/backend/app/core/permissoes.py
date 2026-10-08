"""CATÁLOGO CENTRAL DE PERMISSÕES — fonte única das regras de acesso da solução.

Toda permissão existe aqui e só aqui. Backend e frontend leem deste arquivo:
- backend: `require(P.X)` em cada rota (app/core/deps.py); rota sem permissão nem sobe;
- frontend: `scripts/gerar_permissoes_ts.py` gera `frontend/src/shared/acesso/permissoes.gen.ts`
  e cada tela declara `permissao` no manifesto (sem ela, o TypeScript não compila).

Modelo: usuário → papéis → permissões. Convenção `<modulo>.<acao>`:
- `<modulo>.acessar` = o módulo aparece no menu e suas telas abrem (permissão de VISUALIZAÇÃO);
- demais ações = o que o usuário pode FAZER dentro do módulo.

Escopo de órgão: usuário com `orgao_id` preenchido enxerga apenas dados do próprio órgão
(ver `filtrar_por_orgao` em deps.py). Papéis com `exige_orgao=True` obrigam esse vínculo.

Ao alterar este arquivo: rode `python scripts/gerar_permissoes_ts.py` e atualize o MODULO.md do
módulo afetado (docs/modulos/). Os testes falham se o arquivo TS estiver desatualizado.
"""
# Mantenha este arquivo sem dependências externas: o hook de pre-commit o importa com python3 puro.
from dataclasses import dataclass
from enum import StrEnum


class P(StrEnum):
    # Visão geral
    PAINEL_ACESSAR = "painel.acessar"
    # Inventário CKAN
    INVENTARIO_ACESSAR = "inventario.acessar"
    INVENTARIO_COLETAR = "inventario.coletar"
    # Eixo 1
    PDA_ACESSAR = "pda.acessar"
    PDA_EDITAR_VINCULOS = "pda.editar_vinculos"
    PDA_GERENCIAR_PLANOS = "pda.gerenciar_planos"
    ATUALIZACOES_ACESSAR = "atualizacoes.acessar"
    RASTREABILIDADE_ACESSAR = "rastreabilidade.acessar"
    # Eixo 2
    LGPD_ACESSAR = "lgpd.acessar"
    LGPD_TRIAR = "lgpd.triar"
    LGPD_APROVAR_CORRECAO = "lgpd.aprovar_correcao"
    METADADOS_ACESSAR = "metadados.acessar"
    # Saídas
    RELATORIOS_ACESSAR = "relatorios.acessar"
    RELATORIOS_EXPORTAR = "relatorios.exportar"
    ASSISTENTE_USAR = "assistente.usar"
    # Órgão publicador
    ENVIO_ACESSAR = "envio.acessar"
    ENVIO_ENVIAR_RECURSO = "envio.enviar_recurso"
    # Administração
    PARAMETROS_ACESSAR = "parametros.acessar"
    PARAMETROS_EDITAR = "parametros.editar"
    IA_CONFIGURAR = "ia.configurar"
    ACESSO_GERENCIAR_USUARIOS = "acesso.gerenciar_usuarios"
    ACESSO_GERENCIAR_PAPEIS = "acesso.gerenciar_papeis"


@dataclass(frozen=True)
class MetaPermissao:
    modulo: str
    rotulo: str
    descricao: str
    sensivel: bool = False  # expõe dado pessoal ou altera o portal → destacar na tela de papéis


META: dict[P, MetaPermissao] = {
    P.PAINEL_ACESSAR: MetaPermissao("painel", "Ver Dashboard e Organizações",
                                    "Indicadores consolidados e situação por órgão."),
    P.INVENTARIO_ACESSAR: MetaPermissao("inventario", "Ver Datasets",
                                        "Inventário de datasets e recursos coletados do CKAN."),
    P.INVENTARIO_COLETAR: MetaPermissao("inventario", "Atualizar dados",
                                        "Forçar nova coleta do portal (botão Atualizar dados)."),
    P.PDA_ACESSAR: MetaPermissao("pda", "Ver Monitoramento do PDA",
                                 "Bases previstas, prazos de abertura e situação."),
    P.PDA_EDITAR_VINCULOS: MetaPermissao("pda", "Editar vínculos do PDA",
                                         "Refazer vínculos pendentes com o CKAN e reclassificar "
                                         "bases PDA × espontâneas."),
    P.PDA_GERENCIAR_PLANOS: MetaPermissao("pda", "Gerenciar PDAs",
                                          "Importar planilhas de PDA, definir o PDA vigente "
                                          "(rege indicadores e relatórios) e excluir PDAs."),
    P.ATUALIZACOES_ACESSAR: MetaPermissao("atualizacoes", "Ver Atualizações",
                                          "Atualização real dos recursos e periodicidade."),
    P.RASTREABILIDADE_ACESSAR: MetaPermissao("rastreabilidade", "Ver Rastreabilidade",
                                             "Linha do tempo de mudanças no portal."),
    P.LGPD_ACESSAR: MetaPermissao("lgpd", "Ver Dados Pessoais (LGPD)",
                                  "Achados de possíveis dados pessoais (localização, tipo, "
                                  "confiança).", sensivel=True),
    P.LGPD_TRIAR: MetaPermissao("lgpd", "Triar achados LGPD",
                                "Marcar achado como confirmado, falso positivo ou tratado.",
                                sensivel=True),
    P.LGPD_APROVAR_CORRECAO: MetaPermissao("lgpd", "Aprovar anonimização",
                                           "Aprovar a publicação do recurso anonimizado no CKAN "
                                           "de produção.", sensivel=True),
    P.METADADOS_ACESSAR: MetaPermissao("metadados", "Ver conformidade de metadados",
                                       "Completude de metadados, datasets sem recurso e formatos "
                                       "fechados."),
    P.RELATORIOS_ACESSAR: MetaPermissao("relatorios", "Ver Relatórios",
                                        "Tela de relatórios consolidados."),
    P.RELATORIOS_EXPORTAR: MetaPermissao("relatorios", "Exportar relatórios",
                                         "Baixar relatórios em XLSX e CSV."),
    P.ASSISTENTE_USAR: MetaPermissao("assistente", "Usar o Assistente GEDA",
                                     "Perguntas em linguagem natural sobre o inventário."),
    P.ENVIO_ACESSAR: MetaPermissao("envio", "Ver área do órgão publicador",
                                   "Datasets do próprio órgão e envios realizados."),
    P.ENVIO_ENVIAR_RECURSO: MetaPermissao("envio", "Enviar recurso",
                                          "Enviar dataset/recurso do próprio órgão.",
                                          sensivel=True),
    P.PARAMETROS_ACESSAR: MetaPermissao("parametros", "Ver parâmetros",
                                        "Janela de alerta, metadados obrigatórios, tipos de dado "
                                        "pessoal e formatos abertos."),
    P.PARAMETROS_EDITAR: MetaPermissao("parametros", "Editar parâmetros",
                                       "Alterar os parâmetros de monitoramento."),
    P.IA_CONFIGURAR: MetaPermissao("ia", "Configurar modelos de IA",
                                   "Cadastrar provedores, chaves e vincular modelos às tarefas.",
                                   sensivel=True),
    P.ACESSO_GERENCIAR_USUARIOS: MetaPermissao("acesso", "Gerenciar usuários",
                                               "Criar usuários, atribuir papéis e órgão."),
    P.ACESSO_GERENCIAR_PAPEIS: MetaPermissao("acesso", "Gerenciar papéis",
                                             "Criar papéis e definir suas permissões.",
                                             sensivel=True),
}


@dataclass(frozen=True)
class PapelPadrao:
    codigo: str
    nome: str
    descricao: str
    permissoes: frozenset[P]
    exige_orgao: bool = False
    todas: bool = False  # recebe automaticamente toda permissão nova do catálogo


_VISUALIZACAO_GEDA = frozenset({
    P.PAINEL_ACESSAR, P.INVENTARIO_ACESSAR, P.PDA_ACESSAR, P.ATUALIZACOES_ACESSAR,
    P.RASTREABILIDADE_ACESSAR, P.LGPD_ACESSAR, P.METADADOS_ACESSAR, P.RELATORIOS_ACESSAR,
    P.ASSISTENTE_USAR, P.PARAMETROS_ACESSAR,
})

# Papéis criados automaticamente (sistema). As permissões de cada um podem ser ajustadas na tela
# Usuários e papéis, exceto o administrador, que sempre tem tudo.
PAPEIS_PADRAO: list[PapelPadrao] = [
    PapelPadrao("administrador", "Administrador",
                "Acesso total, incluindo configuração de IA, usuários e papéis.",
                frozenset(P), todas=True),
    PapelPadrao("gerente_geda", "Gerência de Dados Abertos",
                "Monitoramento completo, triagem LGPD e aprovação de anonimização.",
                _VISUALIZACAO_GEDA | {P.INVENTARIO_COLETAR, P.PDA_EDITAR_VINCULOS,
                                      P.PDA_GERENCIAR_PLANOS, P.LGPD_TRIAR,
                                      P.LGPD_APROVAR_CORRECAO, P.RELATORIOS_EXPORTAR,
                                      P.PARAMETROS_EDITAR, P.ACESSO_GERENCIAR_USUARIOS}),
    PapelPadrao("analista_geda", "Equipe GEDA",
                "Consulta a todas as telas de monitoramento e exportação de relatórios.",
                _VISUALIZACAO_GEDA | {P.RELATORIOS_EXPORTAR}),
    PapelPadrao("superintendencia", "Superintendência de Transparência",
                "Visão consolidada e relatórios para acompanhamento gerencial.",
                frozenset({P.PAINEL_ACESSAR, P.RELATORIOS_ACESSAR, P.RELATORIOS_EXPORTAR,
                           P.ASSISTENTE_USAR})),
    PapelPadrao("orgao_publicador", "Órgão publicador",
                "Servidor de órgão estadual: vê e envia dados apenas do próprio órgão.",
                frozenset({P.ENVIO_ACESSAR, P.ENVIO_ENVIAR_RECURSO}), exige_orgao=True),
]


def por_modulo() -> dict[str, list[P]]:
    grupos: dict[str, list[P]] = {}
    for p in P:
        grupos.setdefault(META[p].modulo, []).append(p)
    return grupos
