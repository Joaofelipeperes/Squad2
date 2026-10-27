"""Regras puras do módulo lgpd (sem banco, sem FastAPI) — reaproveitáveis numa extensão CKAN.

Transformam o resultado célula a célula do motor (`deteccao.py`) em ACHADOS para revisão humana:
um achado por (recurso, coluna, tipo), com a primeira linha, o número de células e a maior
confiança. Nunca guardam o valor encontrado (PBI-35): só local, tipo e explicação do score.
"""
import hashlib
from dataclasses import dataclass

# tipo do motor → (código do tipo no sistema e no parâmetro `tipos_dado_pessoal`, rótulo na tela)
TIPOS: dict[str, tuple[str, str]] = {
    "CPF": ("cpf", "CPF"),
    "CNPJ": ("cnpj", "CNPJ"),
    "EMAIL": ("email", "E-mail"),
    "TELEFONE": ("telefone", "Telefone"),
    "CEP": ("cep", "CEP"),
    "ENDERECO": ("endereco", "Endereço"),
}
ROTULOS: dict[str, str] = {codigo: rotulo for codigo, rotulo in TIPOS.values()} | {
    "data_nascimento": "Data de nascimento", "nome": "Nome"}

ALTA, MEDIA, BAIXA = "Alta", "Média", "Baixa"
PRIORIDADES = (ALTA, MEDIA, BAIXA)
STATUS = {"revisar": "Revisar", "confirmado": "Confirmado",
          "falso_positivo": "Falso positivo", "tratado": "Tratado"}
# tipos que identificam pessoa jurídica ou só parte de um endereço: no máximo prioridade Média
_TETO_MEDIA = {"cnpj", "cep"}


def rotulo_tipo(codigo: str) -> str:
    return ROTULOS.get(codigo, codigo)


def prioridade(tipo: str, confianca: int) -> str:
    """PBI-36 — proposta até a GEDA validar: CPF é sempre Alta; demais pela confiança
    (≥90 Alta, ≥70 Média, abaixo Baixa); CNPJ e CEP no máximo Média."""
    if tipo == "cpf":
        return ALTA
    p = ALTA if confianca >= 90 else MEDIA if confianca >= 70 else BAIXA
    return MEDIA if p == ALTA and tipo in _TETO_MEDIA else p


def impressao_digital(recurso_id: int, coluna: str, tipo: str) -> str:
    """Identidade estável do achado entre varreduras (PBI-41): decisão já tomada não se perde."""
    return hashlib.sha256(f"{recurso_id}|{coluna}|{tipo}".encode()).hexdigest()


def nome_da_coluna(tabela: str, coluna: str) -> str:
    """Como a coluna aparece no achado: "Aba › coluna" quando o .xlsx tem várias abas."""
    return f"{tabela} › {coluna}" if tabela else coluna


@dataclass
class AchadoColuna:
    tipo: str            # código (cpf, email...)
    coluna: str
    linha: int           # primeira linha em que apareceu
    ocorrencias: int     # células da coluna com esse tipo
    confianca: int       # 0–100, maior score entre as células
    metodo: str          # regra | ia
    explicacao: str      # trilha do score da célula de maior confiança (sem o valor)


def agregar(coluna: str, celulas, tipos_ativos: set[str] | None = None,
            acumulado: dict[str, AchadoColuna] | None = None) -> dict[str, AchadoColuna]:
    """Junta os resultados das células de uma coluna num achado por tipo.

    `celulas` = [(linha, valor, atipico, resultados)] de `deteccao.analisar_coluna`. Uma célula
    com dois CPFs conta uma ocorrência. `tipos_ativos` = parâmetro `tipos_dado_pessoal` (None =
    todos). `acumulado` permite somar vários blocos da mesma coluna."""
    saida = acumulado if acumulado is not None else {}
    for linha, _valor, _atipico, resultados in celulas:
        melhores: dict[str, object] = {}
        for r in resultados:
            codigo = TIPOS.get(r.tipo, (r.tipo.lower(), r.tipo))[0]
            if tipos_ativos is not None and codigo not in tipos_ativos:
                continue
            if codigo not in melhores or r.score > melhores[codigo].score:
                melhores[codigo] = r
        for codigo, r in melhores.items():
            conf = round(r.score * 100)
            metodo = "ia" if r.reconhecedor == "EnderecoLLMReconhecedor" else "regra"
            a = saida.get(codigo)
            if a is None:
                saida[codigo] = AchadoColuna(codigo, coluna, linha, 1, conf, metodo,
                                             "; ".join(r.explicacao))
                continue
            a.ocorrencias += 1
            a.linha = min(a.linha, linha)
            if conf > a.confianca:
                a.confianca, a.metodo, a.explicacao = conf, metodo, "; ".join(r.explicacao)
    return saida
