"""Parâmetros de negócio editáveis pela GEDA, com valor padrão. Valores marcados 'provisório'
aguardam insumo formal da GEDA (ver PGP v2, premissas)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class DefParametro:
    chave: str
    rotulo: str
    descricao: str
    padrao: object
    pbi: str
    minimo: float | None = None  # números: faixa aceita na edição (None = sem limite)
    maximo: float | None = None


CATALOGO: dict[str, DefParametro] = {d.chave: d for d in [
    DefParametro("janela_alerta_prazo_dias", "Janela de alerta de prazo (dias)",
                 "Bases do PDA a vencer dentro desta janela aparecem como 'Próximo do prazo'.",
                 30, "PBI-22"),
    DefParametro("metadados_obrigatorios", "Metadados obrigatórios",
                 "Campos verificados na completude de metadados. Provisório até lista da GEDA.",
                 ["notes", "license_id", "author", "author_email", "periodicidade"], "PBI-48"),
    DefParametro("tipos_dado_pessoal", "Tipos de dado pessoal detectados",
                 "Provisório até a lista objetiva da CGE-GO.",
                 ["cpf", "email", "telefone", "endereco", "data_nascimento", "nome"], "PBI-31"),
    DefParametro("formatos_abertos", "Formatos considerados abertos",
                 "Recursos fora desta lista são sinalizados como formato fechado.",
                 ["CSV", "JSON", "XML", "ODS", "GEOJSON", "TXT"], "PBI-52"),
    DefParametro("confianca_minima_lgpd", "Confiança mínima para alerta LGPD (%)",
                 "Achados abaixo deste score não geram alerta.", 60, "PBI-86"),
    DefParametro("margem_embeddings_lgpd", "Margem do filtro semântico (endereço)",
                 "Texto vai ao modelo de endereço se a pontuação de embeddings for maior ou igual a "
                 "esta margem. Menor = mais textos ao modelo (mais lento, deixa passar menos). "
                 "Calibrar com o gabarito (avaliar.py --calibrar).", 0.0, "PBI-33"),
    DefParametro("tamanho_maximo_recurso_lgpd_mb", "Tamanho máximo de recurso varrido (MB)",
                 "Recursos maiores não são baixados pela varredura LGPD e ficam sinalizados.",
                 50, "PBI-32"),
    # Índice de atenção por órgão (tela Organizações, ADR-0030): média ponderada do risco LGPD e do
    # atraso de atualização. Pesos relativos (não precisam somar 100). Provisórios até a GEDA validar.
    DefParametro("peso_lgpd_indice_atencao", "Índice de atenção: peso do risco LGPD",
                 "Peso (0 a 100) do risco LGPD — % dos recursos varridos do órgão com possível dado "
                 "pessoal aguardando revisão ou confirmado — na média ponderada. Provisório.",
                 70, "PBI-84", minimo=0, maximo=100),
    DefParametro("peso_atualizacao_indice_atencao", "Índice de atenção: peso da atualização",
                 "Peso (0 a 100) do atraso de atualização — % das bases vinculadas com prazo que "
                 "estão atrasadas pela periodicidade do PDA — na média ponderada. Provisório.",
                 30, "PBI-84", minimo=0, maximo=100),
    DefParametro("indice_atencao_limite_medio", "Índice de atenção: início da faixa Média",
                 "Índice (0 a 100) a partir do qual o órgão fica com atenção Média.",
                 25, "PBI-84", minimo=0, maximo=100),
    DefParametro("indice_atencao_limite_alto", "Índice de atenção: início da faixa Alta",
                 "Índice (0 a 100) a partir do qual o órgão fica com atenção Alta.",
                 50, "PBI-84", minimo=0, maximo=100),
]}
