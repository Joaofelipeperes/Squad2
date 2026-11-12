"""Motor de detecção de dados pessoais — porta do `detector3.py` (Luiza, Eixo 2) para o backend.

Mesma arquitetura (inspirada no Microsoft Presidio) e mesmas regras do detector3:

  Reconhecedor / ReconhecedorPadrao   uma classe por tipo; regex + `validar()` (dígito verificador,
                                      DDD, faixa de CEP). True = validação forte (score 1.0).
  PerfilColuna                        "forma" dos valores de uma coluna; valor de forma rara numa
                                      coluna homogênea é ATÍPICO (indício de dado fora do lugar).
  AprimoradorContexto                 +0.35 com palavra de contexto perto do achado ou valor atípico.
  Analisador                          roda tudo, resolve sobreposições e corta pelo limiar.
  descartar_coincidencias             CPF/CNPJ "válidos por acaso" numa coluna de códigos.
  FiltroEmbeddings + EnderecoLLM      endereço: o modelo local decide; o filtro semântico escolhe
                                      quais células vão a ele.

O que mudou em relação ao script:
- Nada de rede aqui. O filtro recebe `embed_fn` e o reconhecedor de endereço recebe `chat_fn`;
  o service as monta com o `AIGateway` (tarefas sensíveis → só modelo LOCAL, ADR-0002). Assim o
  modelo (qwen2.5:7b-instruct, qwen3, qwen3.5...) é escolhido na tela Modelos de IA.
- Sem pandas: a leitura do arquivo fica em `leitura.py`; aqui só texto.
- Sem anonimizador (US26, etapa posterior) e sem a heurística `--sem-llm` (linha de base do
  avaliar.py, que continua no script).
- Resposta fora do formato recebe o score `max(0.5, limiar)`, para nunca sumir pelo limiar.

Funções puras (sem banco, sem FastAPI): reaproveitáveis numa extensão CKAN (ADR-0004).
"""
from __future__ import annotations

import json
import math
import re
import time
import unicodedata
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field

# =========================================================================== #
# Núcleo (arquitetura Presidio) — igual ao detector3
# =========================================================================== #

def normalizar(texto: str) -> str:
    """minúsculas e sem acento — usado para comparar palavras de contexto."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return sem_acento.lower()


def tokens(texto: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", normalizar(texto))


@dataclass
class Padrao:
    nome: str
    regex: str
    score: float


@dataclass
class Resultado:
    tipo: str
    inicio: int
    fim: int
    score: float
    reconhecedor: str
    explicacao: list[str] = field(default_factory=list)
    validado: bool = False  # validação forte: o contexto não altera o score

    def sobrepoe(self, outro: Resultado) -> bool:
        return self.inicio < outro.fim and outro.inicio < self.fim


class Reconhecedor:
    """Base: subclasses definem `tipo`, `contexto` e `analisar()`."""
    tipo: str = ""
    contexto: list[str] = []

    @property
    def nome(self) -> str:
        return type(self).__name__

    def preparar(self, textos: list[str]) -> None:
        """Opcional: pré-processa em lote os valores de uma coluna antes de
        `analisar()` ser chamado para cada um (ex: calcular embeddings)."""

    def analisar(self, texto: str, atipico: str | None = None) -> list[Resultado]:
        """`atipico`: motivo, se o valor destoa do resto da coluna (ver PerfilColuna)."""
        raise NotImplementedError


class ReconhecedorPadrao(Reconhecedor):
    """Reconhecedor por regex. `grupo` indica qual grupo do regex é o dado."""
    padroes: list[Padrao] = []
    grupo: int = 0

    def __init__(self):
        self._compilados = [(p, re.compile(p.regex, re.IGNORECASE)) for p in self.padroes]

    def validar(self, dado: str, m: re.Match, padrao: Padrao) -> bool | float | None:
        return None

    def analisar(self, texto: str, atipico: str | None = None) -> list[Resultado]:
        resultados = []
        for padrao, rx in self._compilados:
            for m in rx.finditer(texto):
                ini, fim = m.span(self.grupo)
                dado = texto[ini:fim]
                r = Resultado(self.tipo, ini, fim, padrao.score, self.nome,
                              [f"padrão '{padrao.nome}' (score {padrao.score})"])
                v = self.validar(dado, m, padrao)
                if v is False:
                    continue
                if v is True:
                    r.score, r.validado = 1.0, True
                    r.explicacao.append("validação forte -> 1.0")
                elif isinstance(v, float):
                    r.score = v
                    r.explicacao.append(f"validação ajustou score -> {v}")
                resultados.append(r)
        return resultados


class AprimoradorContexto:
    """Sobe o score (+fator, mínimo `minimo`) em dois casos independentes:
      1. uma palavra de contexto aparece perto do achado, no próprio texto
         (até `prefixo` palavras antes / `sufixo` depois);
      2. o valor é atípico na coluna (ex: um número numa coluna de nomes de escola).
    O nome da coluna NÃO é usado: a conclusão vem só dos dados."""

    def __init__(self, fator: float = 0.35, minimo: float = 0.4, prefixo: int = 5, sufixo: int = 2):
        self.fator, self.minimo, self.prefixo, self.sufixo = fator, minimo, prefixo, sufixo

    @staticmethod
    def _casa(palavra_ctx: str, toks: list[str]) -> bool:
        # prefixo: "telefone" casa "telefones"; "tel" casa "tel" e "telefone"
        return any(t.startswith(palavra_ctx) for t in toks)

    def _subir(self, r: Resultado, motivo: str):
        novo = min(1.0, max(self.minimo, r.score + self.fator))
        r.explicacao.append(f"{motivo}: {r.score:.2f} -> {novo:.2f}")
        r.score = novo

    def aprimorar(self, texto: str, resultados: list[Resultado],
                  reconhecedores: dict[str, Reconhecedor], atipico: str | None = None):
        for r in resultados:
            if r.validado:
                continue
            palavras = [normalizar(p) for p in reconhecedores[r.reconhecedor].contexto]
            antes = tokens(texto[:r.inicio])[-self.prefixo:] if self.prefixo else []
            depois = tokens(texto[r.fim:])[:self.sufixo] if self.sufixo else []
            achou = next((p for p in palavras if self._casa(p, antes + depois)), None)
            if achou:
                self._subir(r, f"contexto '{achou}' no texto")
            if atipico:
                self._subir(r, f"valor atípico na coluna ({atipico})")


class Analisador:
    def __init__(self, reconhecedores: list[Reconhecedor], limiar: float = 0.5,
                 aprimorador: AprimoradorContexto | None = None):
        self.reconhecedores = {r.nome: r for r in reconhecedores}
        self.limiar = limiar
        self.aprimorador = aprimorador or AprimoradorContexto()

    def preparar(self, textos: list[str]) -> None:
        for rec in self.reconhecedores.values():
            rec.preparar(textos)

    def analisar(self, texto: str, atipico: str | None = None) -> list[Resultado]:
        resultados = []
        for rec in self.reconhecedores.values():
            resultados.extend(rec.analisar(texto, atipico))
        self.aprimorador.aprimorar(texto, resultados, self.reconhecedores, atipico)
        resultados = self._resolver_conflitos(resultados)
        return [r for r in resultados if r.score >= self.limiar]

    @staticmethod
    def _resolver_conflitos(resultados: list[Resultado]) -> list[Resultado]:
        """Em trechos sobrepostos, fica o maior score; empate -> o trecho mais longo."""
        ordenados = sorted(resultados, key=lambda r: (-r.score, -(r.fim - r.inicio), r.inicio))
        mantidos: list[Resultado] = []
        for r in ordenados:
            if not any(r.sobrepoe(m) for m in mantidos):
                mantidos.append(r)
        return sorted(mantidos, key=lambda r: r.inicio)


def forma(valor: str) -> tuple[str, str]:
    """Forma de um valor em dois níveis: (classe, forma detalhada).
    classe: texto | numero | misto | simbolo
    detalhe: classe + faixa de dígitos + faixa de palavras
    Ex: "Escola Estadual Lyceu" -> ("texto", "texto|0d|3+p")
        "62998765432"           -> ("numero", "numero|9-13d|1p")
        "Av Nápoli, 800"        -> ("misto", "misto|1-4d|3+p")"""
    v = valor.strip()
    dig = sum(c.isdigit() for c in v)
    let = sum(c.isalpha() for c in v)
    classe = ("misto" if dig and let else "numero" if dig else "texto" if let else "simbolo")
    faixa_d = ("0d" if dig == 0 else "1-4d" if dig <= 4 else "5-8d" if dig <= 8
               else "9-13d" if dig <= 13 else "14+d")
    n_pal = len(v.split())
    faixa_p = "1p" if n_pal <= 1 else "2p" if n_pal == 2 else "3+p"
    return classe, f"{classe}|{faixa_d}|{faixa_p}"


class PerfilColuna:
    """Perfil dos valores de UMA coluna, usado para achar valores atípicos.

    Um valor é atípico quando a coluna tem um padrão claro (a forma dominante
    cobre pelo menos `dominancia` dos valores) e a forma do valor é rara
    (menos de `raridade` dos valores). Colunas de texto livre, sem padrão
    dominante, nunca geram atípicos — ali só valem os reconhecedores."""

    def __init__(self, valores, raridade: float = 0.05, dominancia: float = 0.6, minimo: int = 20):
        from collections import Counter
        self.raridade, self.dominancia = raridade, dominancia
        nao_vazios = [v for v in valores if v and v.strip()]
        self.n = len(nao_vazios)
        self.ativo = self.n >= minimo
        formas = [forma(v) for v in nao_vazios]
        self.classes = Counter(c for c, _ in formas)
        self.detalhes = Counter(d for _, d in formas)

    def _checar(self, contagem, chave) -> str | None:
        dominante, n_dom = contagem.most_common(1)[0]
        if n_dom / self.n < self.dominancia:
            return None
        freq = contagem[chave] / self.n
        if freq <= self.raridade:
            return f"forma '{chave}' em {freq:.1%} dos valores; dominante '{dominante}' em {n_dom / self.n:.0%}"
        return None

    def forma_detalhada(self, valor: str) -> str:
        return forma(valor)[1]

    def motivo_atipico(self, valor: str) -> str | None:
        """Motivo (texto) se o valor for atípico; None caso contrário."""
        if not self.ativo:
            return None
        classe, detalhe = forma(valor)
        if classe == "simbolo":  # "-", "/", "..." -> marcador de vazio, nunca sensível
            return None
        motivo = self._checar(self.classes, classe)
        # Nível detalhado só para valores COM dígitos: um número de tamanho incomum
        # é suspeito; um texto com mais ou menos palavras que os outros, não.
        if motivo is None and classe in ("numero", "misto"):
            motivo = self._checar(self.detalhes, detalhe)
        return motivo



# =========================================================================== #
# Reconhecedores brasileiros — iguais ao detector3
# =========================================================================== #

class CpfReconhecedor(ReconhecedorPadrao):
    tipo = "CPF"
    contexto = ["cpf", "documento", "doc", "cadastro", "contribuinte"]
    grupo = 1
    padroes = [Padrao("cpf", r"(?<![0-9A-Za-z])(\d{3}\.?\d{3}\.?\d{3}-?\d{2})(?![0-9A-Za-z])", 0.3)]

    def validar(self, dado, m, padrao):
        d = re.sub(r"\D", "", dado)
        if len(d) != 11 or d == d[0] * 11:
            return False
        for n in (9, 10):
            soma = sum(int(d[i]) * (n + 1 - i) for i in range(n))
            if (soma * 10) % 11 % 10 != int(d[n]):
                return False
        return True


class CnpjReconhecedor(ReconhecedorPadrao):
    tipo = "CNPJ"
    contexto = ["cnpj", "empresa", "razao", "fornecedor"]
    grupo = 1
    padroes = [Padrao(
        "cnpj",
        r"(?<![0-9A-Za-z])([0-9A-Za-z]{2}\.?[0-9A-Za-z]{3}\.?[0-9A-Za-z]{3}/?[0-9A-Za-z]{4}-?\d{2})(?![0-9A-Za-z])",
        0.3,
    )]

    def validar(self, dado, m, padrao):
        """CNPJ numérico e alfanumérico (valor do caractere = ASCII - 48)."""
        d = re.sub(r"[^0-9A-Za-z]", "", dado).upper()
        if len(d) != 14 or not d[12:].isdigit() or d == d[0] * 14:
            return False
        pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        for pesos in (pesos1, [6] + pesos1):
            n = len(pesos)
            resto = sum((ord(d[i]) - 48) * pesos[i] for i in range(n)) % 11
            if (0 if resto < 2 else 11 - resto) != int(d[n]):
                return False
        return True


class EmailReconhecedor(ReconhecedorPadrao):
    tipo = "EMAIL"
    contexto = ["email", "mail", "contato"]
    grupo = 1
    padroes = [Padrao(
        "email",
        r"(?<![\w.+-])([A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,})(?![\w-])",
        0.9,
    )]


DDDS_VALIDOS = {
    11, 12, 13, 14, 15, 16, 17, 18, 19, 21, 22, 24, 27, 28, 31, 32, 33, 34, 35, 37, 38,
    41, 42, 43, 44, 45, 46, 47, 48, 49, 51, 53, 54, 55, 61, 62, 63, 64, 65, 66, 67, 68, 69,
    71, 73, 74, 75, 77, 79, 81, 82, 83, 84, 85, 86, 87, 88, 89,
    91, 92, 93, 94, 95, 96, 97, 98, 99,
}
_ANO = re.compile(r"(19|20)\d\d")


class TelefoneReconhecedor(ReconhecedorPadrao):
    tipo = "TELEFONE"
    contexto = ["tel", "telefone", "fone", "celular", "cel", "whatsapp", "whats", "zap",
                "contato", "ramal", "recado"]
    grupo = 1
    padroes = [
        Padrao(
            "telefone",
            r"(?<![\w+])((\+?55[\s.-]?)?(?:(\()?(\d{2})\)?[\s.-]?)?(\d{4,5})([\s.-]?)(\d{4}))(?![\w])",
            0.4,
        ),
        Padrao("0800", r"(?<!\d)(0[3589]00[\s.-]?\d{3}[\s.-]?\d{4})(?!\d)", 0.6),
    ]

    def validar(self, dado, m, padrao):
        if padrao.nome == "0800":  # 0800/0300: vale o score do padrão
            return None
        pais, parentese, ddd, p1, sep, p2 = m.group(2), m.group(3), m.group(4), m.group(5), m.group(6), m.group(7)
        numero = p1 + p2
        if len(numero) == 9 and numero[0] != "9":          # celular: 9 dígitos começando com 9
            return False
        if len(numero) == 8 and numero[0] not in "2345":   # fixo: começa com 2-5
            return False
        if len(set(numero)) == 1:
            return False
        if ddd is not None:
            if int(ddd) not in DDDS_VALIDOS:
                return False
            formatado = bool(pais or parentese or sep or re.search(r"\d[\s.-]\d", dado))
            return 0.7 if formatado else 0.45   # "62998765432" sozinho é ambíguo
        if _ANO.fullmatch(p1) and _ANO.fullmatch(p2):     # "2024-2025"
            return False
        # Sem DDD: com separador é razoável; sem separador só passa com contexto
        return 0.45 if sep else 0.2


class CepReconhecedor(ReconhecedorPadrao):
    tipo = "CEP"
    contexto = ["cep", "endereco", "logradouro", "bairro", "residencia", "postal"]
    grupo = 1
    padroes = [
        Padrao("cep_formatado", r"(?<![\d.])(\d{2}\.?\d{3}-\d{3})(?![\d-])", 0.5),
        Padrao("cep_8_digitos", r"(?<![\d.])(\d{8})(?!\d)", 0.2),
    ]

    def validar(self, dado, m, padrao):
        d = re.sub(r"\D", "", dado)
        if d.startswith("00") or len(set(d)) == 1:
            return False
        return None



# palavras que, escritas no próprio texto perto do achado, reforçam endereço/CEP
CONTEXTO_ENDERECO = ["endereco", "logradouro", "residencia", "domicilio", "moradia", "cep"]


PROMPT = """Você é um classificador de dados pessoais (LGPD) para textos em português do Brasil.
Decida se o TEXTO contém um ENDEREÇO ou uma REFERÊNCIA DE LOCALIZAÇÃO que permita localizar
um imóvel, terreno ou ponto físico de uma pessoa ou empresa.

CONTA como endereço (mesmo abreviado, sem acento, em maiúsculas, incompleto ou com erros):
- Logradouro com tipo explícito: Rua, Av., Travessa, Alameda, Rodovia, Estrada, Praça,
  Largo, Viela, Beco, Ladeira, Servidão.
- Logradouro SEM tipo explícito só conta se vier acompanhado de complemento de moradia,
  bairro ou cidade ("Estibinita 1045 apto 404", "Mandaguari 1290, Jardim Esperança").
  Um nome seguido apenas de um número pequeno NÃO basta.
- Complementos que indicam moradia: apto, casa, bloco, torre, sala, loja, fundos, lote, quadra.
- Padrões de quadra/lote/setor: "Qd 12 Lt 5 Setor Bueno", "Rua T-63 Qd 140", "Conjunto A Lote 7".
- Endereços de Brasília: "SQS 308 Bloco C", "QNM 34 Conjunto H Casa 12", "SHIN QI 5".
- Condomínios, residenciais e loteamentos com identificação da unidade ou da rua.
- Endereços rurais: Fazenda, Sítio, Chácara, Zona Rural, "Rodovia GO-020 Km 12", "Linha 5 Lote 30".
- CEP (00000-000 ou 00000000), sozinho ou acompanhado.
- Bairro + cidade juntos ("Setor Oeste, Goiânia").
- Caixa Postal.
- Referências de onde a pessoa mora, trabalha ou pode ser encontrada, mesmo vagas:
  "mora perto do shopping", "reside ao lado da igreja matriz", "casa em frente à escola",
  "fica atrás do mercado do Zé", "próximo ao posto da Av. T-9".

NÃO conta como endereço:
- Cidade, estado, país ou região sozinhos ("Goiânia", "GO", "Zona Sul").
- Nomes de cursos, disciplinas, turmas, eventos, projetos ou estilos, mesmo contendo palavras
  como "rua", "avenida", "praça" ou "quadra" ("DANÇA DE RUA", "Teatro de Praça", "Quadra de esportes").
- Nome de curso, oficina, turma, módulo ou edição seguido de número
  ("NOVELO DAS ARTES 4", "PINTURA EM TELA 2", "INGLÊS BÁSICO - TURMA 3", "Módulo 2").
- Códigos e siglas ("TEC-ABF-AV-PADP-N1-2026", "AV1", "BL-03").
- Nome de lugar citado sem relação com onde alguém mora ou fica ("Excursão ao shopping no sábado",
  "Apresentação no Teatro Goiânia", "Escola Basileu França").
- Números soltos, datas, horários, cargas horárias, telefones, e-mails.

Exemplos:
TEXTO: "Estibinita 1045 apto 404 torre 1 goiania goias"
{{"endereco": true, "trecho": "Estibinita 1045 apto 404 torre 1 goiania goias"}}
TEXTO: "Av Nápoli, 800, Residencial Eldorado"
{{"endereco": true, "trecho": "Av Nápoli, 800, Residencial Eldorado"}}
TEXTO: "Mora na R. 15 qd 22 lt 3, St. Marista"
{{"endereco": true, "trecho": "R. 15 qd 22 lt 3, St. Marista"}}
TEXTO: "Fazenda Boa Vista, Rod. GO-060 km 18, zona rural"
{{"endereco": true, "trecho": "Fazenda Boa Vista, Rod. GO-060 km 18, zona rural"}}
TEXTO: "CEP 74115-060"
{{"endereco": true, "trecho": "74115-060"}}
TEXTO: "mora perto do shopping"
{{"endereco": true, "trecho": "mora perto do shopping"}}
TEXTO: "Aluno reside ao lado da igreja matriz, Trindade"
{{"endereco": true, "trecho": "ao lado da igreja matriz, Trindade"}}
TEXTO: "DANÇA DE RUA BASILEU FRANÇA JUVENIL"
{{"endereco": false, "trecho": ""}}
TEXTO: "TEC-ABF-AV-PADP-N1-2026"
{{"endereco": false, "trecho": ""}}
TEXTO: "NOVELO DAS ARTES 4"
{{"endereco": false, "trecho": ""}}
TEXTO: "PINTURA EM TELA 2"
{{"endereco": false, "trecho": ""}}
TEXTO: "Excursão ao shopping no sábado"
{{"endereco": false, "trecho": ""}}
TEXTO: "Apresentação no Teatro Goiânia"
{{"endereco": false, "trecho": ""}}
TEXTO: "Goiânia - GO"
{{"endereco": false, "trecho": ""}}

AMOSTRA DA MESMA COLUNA: outros valores frequentes na coluna de onde o TEXTO veio.
Use para entender que tipo de informação a coluna guarda (o nome da coluna não é informado):
{amostra}

Como usar a amostra:
- Se a amostra mostra que a coluna guarda nomes de município, hospital, unidade de saúde, escola,
  curso, empresa, órgão etc., e o TEXTO é mais um valor desse mesmo tipo, responda false, mesmo que
  ele contenha palavras como "Fazenda", "Sítio", "Casa", "Jardim", "Vila" ou "Centro"
  (ex: "Fazenda Nova" e "Sítio d'Abadia" são nomes de município; "CASA DE APOIO X" é nome de unidade).
- Se o TEXTO destoa da amostra e parece endereço, ou se a própria amostra é de endereços, siga as
  regras acima normalmente.

Responda SOMENTE com JSON, sem texto extra:
{{"endereco": true ou false, "trecho": "parte exata do texto que é o endereço, ou vazio"}}

TEXTO: \"\"\"{texto}\"\"\""""


# Exemplos que definem, para o filtro de embeddings, o que "parece endereço" e o
# que não parece. Para ajustar ao seu domínio, acrescente casos reais aqui
# (principalmente negativos que estejam passando sem necessidade).
PROTOTIPOS_ENDERECO = [
    "Rua 15, número 230, Setor Marista",
    "Av. T-63 qd 140 lt 5, Setor Bueno, Goiânia",
    "Estibinita 1045 apto 404 torre 1",
    "Travessa das Flores 12, Centro",
    "Residencial Eldorado, quadra 4 lote 9",
    "Condomínio Alphaville, casa 32",
    "SQS 308 Bloco C apartamento 201",
    "Jardim Esperança, Londrina PR",
    "Mandaguari 1290 fundos",
    "Fazenda Boa Vista, zona rural, km 18",
    "Chácara Recanto, estrada vicinal",
    "mora perto do shopping",
    "reside ao lado da igreja matriz",
    "terceira casa depois do posto",
    "casa em frente à escola municipal",
    "fica atrás da padaria, portão azul",
    "próximo ao mercado do bairro, rua sem saída",
    "endereço residencial do aluno",
]
PROTOTIPOS_NAO_ENDERECO = [
    "DANÇA DE RUA BASILEU FRANÇA JUVENIL",
    "INGLÊS APLICADO A SERVIÇOS TURÍSTICOS - PRONATEC",
    "Teatro Infantil",
    "Violão Popular",
    "ORATÓRIA",
    "EMPREENDEDORISMO",
    "Escola Estadual Lyceu de Goiânia",
    "Colégio Militar Hugo de Carvalho",
    "Instituto Basileu França",
    "TEC-ABF-AV-PADP-N1-2026",
    "Turma A - noturno",
    "NOVELO DAS ARTES 4",
    "PINTURA EM TELA 2",
    "Oficina de Crochê - Turma 3",
    "Módulo 2 - Informática Básica",
    "faltou à aula",
    "transferido de turno",
    "aguardando documento",
    "aluno desistente",
    "Goiânia",
    "Maria Aparecida da Silva",
    "excursão ao shopping no sábado",
    "apresentação no teatro municipal",
]


# Máscara completa de CPF/CNPJ: número de código não vem escrito assim por acaso.
_MASCARA = {
    "CPF": re.compile(r"\d{3}\.\d{3}\.\d{3}-\d{2}"),
    "CNPJ": re.compile(r"[0-9A-Za-z]{2}\.[0-9A-Za-z]{3}\.[0-9A-Za-z]{3}/[0-9A-Za-z]{4}-\d{2}"),
}


def _com_mascara(tipo: str, valor: str) -> bool:
    m = _MASCARA.get(tipo)
    return bool(m and m.fullmatch(valor.strip()))


def descartar_coincidencias(analisados, perfil: PerfilColuna, limiar: float, minimo: int = 20,
                            taxa_minima: float = 0.5):
    """Dígito verificador também passa por acaso (~1% dos números aleatórios de
    11 dígitos é 'CPF válido'). Se numa coluna só uma minoria dos valores com a
    mesma forma valida como CPF/CNPJ, é coluna de IDs/códigos e os acertos são
    coincidência. Valores atípicos e valores escritos com a máscara completa
    (000.000.000-00, 00.000.000/0000-00) ficam de fora dessa regra."""
    from collections import Counter
    formas = Counter(perfil.forma_detalhada(v) for _, v, _, _ in analisados)
    acertos = Counter()  # (tipo, forma) -> nº de valores típicos validados
    for _, valor, atipico, resultados in analisados:
        if atipico:
            continue
        for r in resultados:
            if (r.validado and r.inicio == 0 and r.fim == len(valor.strip())
                    and not _com_mascara(r.tipo, valor)):
                acertos[(r.tipo, perfil.forma_detalhada(valor))] += 1
    suspeitos = {}
    for (tipo, f), n in acertos.items():
        base = formas[f]
        if base >= minimo and n / base < taxa_minima:
            suspeitos[(tipo, f)] = (f"só {n} de {base} valores de forma '{f}' na coluna validam como {tipo} "
                                    f"({n / base:.0%}): provável coincidência numa coluna de códigos")
    if not suspeitos:
        return analisados
    saida = []
    for idx, valor, atipico, resultados in analisados:
        if not atipico:
            novos = []
            for r in resultados:
                motivo = suspeitos.get((r.tipo, perfil.forma_detalhada(valor)))
                if motivo and r.validado and not _com_mascara(r.tipo, valor):
                    r = Resultado(r.tipo, r.inicio, r.fim, 0.2, r.reconhecedor, r.explicacao + [motivo])
                if r.score >= limiar:
                    novos.append(r)
            resultados = novos
        saida.append((idx, valor, atipico, resultados))
    return saida


# =========================================================================== #
# Endereço: modelo LOCAL (pelo gateway), com filtro semântico (embeddings) antes.
# As funções de IA chegam prontas (`embed_fn`, `chat_fn`): este arquivo não sabe qual modelo,
# servidor ou perfil está por trás. Quem as monta é o service, sempre pelo AIGateway.
# =========================================================================== #

EmbedFn = Callable[[list[str]], list[list[float]]]
ChatFn = Callable[[str], str]


def _normalizar_vetor(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1e-12
    return [x / n for x in v]


def _media_top_k(vetor: list[float], base: list[list[float]], k: int) -> float:
    sims = sorted((sum(a * b for a, b in zip(vetor, p)) for p in base), reverse=True)
    topo = sims[:max(1, min(k, len(sims)))]
    return sum(topo) / len(topo)


class FiltroEmbeddings:
    """Filtro semântico antes do LLM — sem regex, sem palavra-chave (como no detector3).

    Cada texto vira um vetor (embedding). Mede-se a similaridade média com os k protótipos mais
    parecidos de ENDEREÇO e de NÃO-ENDEREÇO; a pontuação é `sim_endereco - sim_nao_endereco`, e o
    texto vai ao LLM se pontuação >= margem. Textos longos (mais de `janela` palavras) também são
    pontuados em janelas deslizantes, e vale a maior pontuação."""

    def __init__(self, embed_fn: EmbedFn, margem: float = 0.0, lote: int = 64, k: int = 3,
                 janela: int = 8, prototipos_extra: list[tuple[str, int]] | None = None):
        self.embed_fn, self.margem, self.lote, self.k, self.janela = embed_fn, margem, lote, k, janela
        self.cache: dict[str, float] = {}  # pedaço de texto -> pontuação
        pos, neg = list(PROTOTIPOS_ENDERECO), list(PROTOTIPOS_NAO_ENDERECO)
        for texto, rotulo in prototipos_extra or []:
            (pos if rotulo else neg).append(texto)
        self._pos = self._embed(pos)  # falha aqui = erro explícito (não há filtro reserva)
        self._neg = self._embed(neg)

    def _embed(self, textos: list[str]) -> list[list[float]]:
        return [_normalizar_vetor(v) for v in self.embed_fn(textos)]

    def _pedacos(self, texto: str) -> list[str]:
        t = texto.strip()[:500]
        palavras = t.split()
        if len(palavras) <= self.janela:
            return [t]
        passo = max(1, self.janela // 2)
        inicios = list(range(0, len(palavras) - self.janela + 1, passo))
        if inicios[-1] != len(palavras) - self.janela:
            inicios.append(len(palavras) - self.janela)
        return list(dict.fromkeys([t] + [" ".join(palavras[i:i + self.janela]) for i in inicios]))

    def _pontuar_pedacos(self, pedacos: list[str]) -> None:
        novos = list(dict.fromkeys(p for p in pedacos if p and p not in self.cache))
        for i in range(0, len(novos), self.lote):
            parte = novos[i:i + self.lote]
            for t, v in zip(parte, self._embed(parte)):
                self.cache[t] = (_media_top_k(v, self._pos, self.k)
                                 - _media_top_k(v, self._neg, self.k))

    def preparar(self, textos: list[str]) -> None:
        self._pontuar_pedacos([p for t in textos for p in self._pedacos(t)])

    def pontuar(self, texto: str) -> float:
        pedacos = self._pedacos(texto)
        self._pontuar_pedacos(pedacos)
        return max(self.cache[p] for p in pedacos)

    def motivo_candidato(self, texto: str) -> str | None:
        s = self.pontuar(texto)
        return f"embeddings: pontuação {s:+.3f} >= margem {self.margem:+.3f}" if s >= self.margem else None


def tem_letras(texto: str) -> bool:
    return any(c.isalpha() for c in texto)


def extrair_json(bruto: str) -> dict | None:
    """Aceita JSON puro, JSON depois de um bloco <think>...</think> ou JSON cercado de texto."""
    texto = bruto
    if "</think>" in texto:
        texto = texto.split("</think>", 1)[1]
    texto = texto.strip()
    candidatos = [texto]
    ini, fim = texto.find("{"), texto.rfind("}")
    if 0 <= ini < fim:
        candidatos.append(texto[ini:fim + 1])
    for c in candidatos:
        try:
            dados = json.loads(c)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(dados, dict) and "endereco" in dados:
            return dados
    return None


def como_bool(v) -> bool:
    # bool("false") é True em Python: trata strings explicitamente
    if isinstance(v, str):
        return v.strip().lower() in ("true", "sim", "yes", "1", "verdadeiro")
    return bool(v)


class EnderecoLLMReconhecedor(Reconhecedor):
    """O modelo local decide se há endereço e extrai o trecho (detector3).

    Quem vai ao modelo (basta uma condição; nada aqui usa regex):
      1. `llm_todas`: toda célula com letras
      2. valor atípico na coluna (PerfilColuna)
      3. filtro de embeddings (FiltroEmbeddings)

    Se o modelo cair, a exceção sobe e a varredura PARA com erro. Resposta fora do formato →
    a célula é marcada como ENDERECO para revisão (na dúvida, marca), com score `score_revisao`."""
    tipo = "ENDERECO"
    contexto = CONTEXTO_ENDERECO

    def __init__(self, chat_fn: ChatFn, llm_todas: bool = False,
                 filtro: FiltroEmbeddings | None = None, score_revisao: float = 0.5,
                 nome_modelo: str = "modelo local"):
        self.chat_fn, self.llm_todas, self.filtro = chat_fn, llm_todas, filtro
        self.score_revisao, self.nome_modelo = score_revisao, nome_modelo
        self.cache: dict[tuple[str, str], tuple[bool, str]] = {}  # (texto, amostra) -> resposta
        self._frequentes: list[str] = []
        self.stats = {"chamadas": 0, "erros_parse": 0, "tempo_llm": 0.0}

    def preparar(self, textos: list[str]) -> None:
        # amostra dos valores mais frequentes da coluna, mostrada ao modelo junto com cada texto
        self._frequentes = [v.strip()[:80] for v, _ in Counter(t.strip() for t in textos).most_common(11)]
        if self.filtro and not self.llm_todas:
            self.filtro.preparar([t for t in textos if tem_letras(t)])

    def _candidato(self, texto: str, atipico: str | None) -> str | None:
        """Motivo pelo qual o texto vai ao modelo, ou None. Células só com números ficam com os
        reconhecedores de CEP/CPF/telefone."""
        if not tem_letras(texto):
            return None
        if self.llm_todas:
            return "todas as células com letras"
        if atipico:
            return "valor atípico na coluna"
        if self.filtro:
            return self.filtro.motivo_candidato(texto)
        return None

    def _amostra(self, texto: str) -> str:
        outros = [v for v in self._frequentes if v != texto.strip()[:80]][:10]
        return "\n".join(f"- {v}" for v in outros) if outros else "(sem amostra)"

    def _perguntar(self, texto: str) -> tuple[bool, str, bool]:
        """(é_endereço, trecho, erro_de_formato). Erros de formato não vão para o cache."""
        chave = texto.strip()[:500]
        amostra = self._amostra(texto)
        if (chave, amostra) in self.cache:
            return (*self.cache[(chave, amostra)], False)
        t0 = time.perf_counter()
        bruto = self.chat_fn(PROMPT.format(texto=chave, amostra=amostra))
        self.stats["tempo_llm"] += time.perf_counter() - t0
        self.stats["chamadas"] += 1
        dados = extrair_json(bruto)
        if dados is None:
            self.stats["erros_parse"] += 1
            return (False, "", True)
        res = (como_bool(dados.get("endereco")), str(dados.get("trecho") or ""))
        self.cache[(chave, amostra)] = res
        return (*res, False)

    def analisar(self, texto, atipico=None):
        porta = self._candidato(texto, atipico)
        if not porta:
            return []
        eh_end, trecho, erro = self._perguntar(texto)  # se o modelo cair, a exceção sobe
        ini0, fim0 = len(texto) - len(texto.lstrip()), len(texto.rstrip())
        if erro:
            return [Resultado(self.tipo, ini0, fim0, self.score_revisao, self.nome,
                              [f"entrou por: {porta}",
                               "modelo respondeu fora do formato: REVISAR manualmente"])]
        if not eh_end:
            return []
        pos = texto.lower().find(trecho.lower()) if trecho else -1
        ini, fim = (pos, pos + len(trecho)) if pos >= 0 else (ini0, fim0)
        return [Resultado(self.tipo, ini, fim, 0.85, self.nome,
                          [f"entrou por: {porta}", f"confirmado por {self.nome_modelo}"])]


def montar_analisador(limiar: float = 0.5, chat_fn: ChatFn | None = None,
                      filtro: FiltroEmbeddings | None = None, llm_todas: bool = False,
                      nome_modelo: str = "modelo local") -> Analisador:
    """Registro de reconhecedores. Sem `chat_fn`, endereço não é verificado (só os tipos com
    regra). Sem `filtro`, só valores atípicos (ou todas, com `llm_todas`) vão ao modelo."""
    reconhecedores: list[Reconhecedor] = [
        CnpjReconhecedor(), CpfReconhecedor(), EmailReconhecedor(), TelefoneReconhecedor(),
        CepReconhecedor(),
    ]
    if chat_fn is not None:
        reconhecedores.append(EnderecoLLMReconhecedor(
            chat_fn, llm_todas=llm_todas, filtro=filtro, score_revisao=max(0.5, limiar),
            nome_modelo=nome_modelo))
    return Analisador(reconhecedores, limiar=limiar)


def analisar_coluna(analisador: Analisador, valores: list[tuple[int, str]], raridade: float = 0.05,
                    cache: dict | None = None, chave_coluna: str = ""):
    """Analisa os valores de UMA coluna (como `varrer()` do detector3 faz por bloco):
    perfil da coluna, preparação em lote, análise célula a célula (com cache por valor) e descarte
    de coincidências de dígito verificador. `valores` = [(linha, texto)].
    Devolve [(linha, texto, atipico, resultados)] só das células com algum resultado ou atípicas."""
    cache = {} if cache is None else cache
    nao_vazios = [(i, v) for i, v in valores if v and v.strip()]
    perfil = PerfilColuna([v for _, v in nao_vazios], raridade=raridade)
    analisador.preparar([v for _, v in nao_vazios])
    analisados = []
    for linha, valor in nao_vazios:
        atipico = perfil.motivo_atipico(valor)
        chave = (chave_coluna, valor, atipico)
        if chave not in cache:
            cache[chave] = analisador.analisar(valor, atipico=atipico)
        analisados.append((linha, valor, atipico, cache[chave]))
    analisados = descartar_coincidencias(analisados, perfil, analisador.limiar)
    return [a for a in analisados if a[3] or a[2]]
