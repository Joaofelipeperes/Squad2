"""Teste de capacidade da varredura LGPD (Eixo 2) — responde, com o volume real do portal:

1. Quanto tempo leva por recurso (e por MB/linha)? Quantas chamadas à IA local cada um faz?
2. Uma varredura do portal inteiro leva horas ou dias? (projeção a partir da amostra)
3. A varredura noturna incremental termina antes do expediente?
4. Qual o pico de memória do worker e do Ollama com um arquivo grande? Algum processo cai?
5. A API continua respondendo com a CPU ocupada pela IA? (usuários simulados nas telas)
6. A fila se recupera de cancelamento e de worker reiniciado, sem travar nem repetir trabalho?

Roda no computador onde está o Docker do projeto, contra a API local, a partir da raiz do
repositório, com um Python 3.11+ que tenha o httpx (o ambiente do backend serve):

    python testes/capacidade_lgpd/teste_capacidade_lgpd.py \\
        --email voce@cge.go.gov.br            (senha em GDA_TESTE_SENHA ou perguntada; ou --token)

Só lê dados públicos do portal e não guarda valor de dado pessoal: a varredura grava apenas
local e tipo dos achados, e este script lê só tempos, contagens e uso de máquina. Ver README.md.
"""
from __future__ import annotations

import argparse
import csv
import getpass
import json
import os
import random
import statistics
import subprocess
import sys
import threading
import time
import traceback
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

# Pasta do sistema, onde está o docker-compose.yml dele. O teste fica na raiz do repositório,
# fora de produtofinal/, para não entrar no pacote de entrega (deploy/empacotar.ps1).
RAIZ = Path(__file__).resolve().parents[2] / "produtofinal"
FINAIS = {"ok", "erro", "ignorado", "cancelada"}
# Mesma regra de app.modules.lgpd.leitura (FORMATOS_SUPORTADOS / formato_do_recurso)
SUPORTADOS = {"CSV", "TSV", "TXT", "XLSX"}
FAIXAS = (("pequeno", 0, 1), ("medio", 1, 10), ("grande", 10, float("inf")))
# Telas mais usadas pela GEDA (GETs que a tela faz ao abrir)
TELAS = ["/painel/visao-geral", "/painel/organizacoes", "/inventario/datasets",
         "/atualizacoes/datasets", "/pda/bases", "/lgpd/achados", "/relatorios"]
INTERROMPIDA = "worker foi reiniciado"  # trecho da mensagem de lgpd.service.INTERROMPIDA


def agora() -> datetime:
    return datetime.now(UTC)


def data(iso: str | None) -> datetime | None:
    if not iso:
        return None
    d = datetime.fromisoformat(iso)
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def formato_do_recurso(formato: str | None, url: str | None) -> str | None:
    f = (formato or "").strip().upper().lstrip(".").removeprefix("TEXT/")
    if f:
        return f
    nome = (url or "").split("?")[0].lower()
    return nome.rsplit(".", 1)[-1].upper() if "." in nome.rsplit("/", 1)[-1] else None


def faixa(mb: float | None) -> str:
    if mb is None:
        return "desconhecido"
    return next(nome for nome, de, ate in FAIXAS if de <= mb < ate)


def pct(valores: list[float], p: float) -> float | None:
    if not valores:
        return None
    v = sorted(valores)
    return v[min(len(v) - 1, round(p / 100 * (len(v) - 1)))]


def med(valores: list[float]) -> float | None:
    return statistics.median(valores) if valores else None


def duracao(seg: float | None) -> str:
    if seg is None:
        return "—"
    if seg < 90:
        return f"{seg:.1f} s"
    if seg < 5400:
        return f"{seg / 60:.1f} min"
    if seg < 172800:
        return f"{seg / 3600:.1f} h"
    return f"{seg / 86400:.1f} dias"


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


# ------------------------------------------------------------------ API e Docker
class Api:
    def __init__(self, base: str, email: str | None, senha: str | None, token: str | None = None):
        self.c = httpx.Client(base_url=base, timeout=120)
        if not token:
            r = self.c.post("/acesso/login", json={"email": email, "senha": senha})
            r.raise_for_status()
            token = r.json()["access_token"]
        self.c.headers["Authorization"] = f"Bearer {token}"

    def get(self, caminho: str, **params):
        r = self.c.get(caminho, params=params or None)
        r.raise_for_status()
        return r.json()

    def post(self, caminho: str, corpo: dict | None = None):
        r = self.c.post(caminho, json=corpo)
        r.raise_for_status()
        return r.json()


def docker(*args: str, timeout: int = 120) -> str:
    r = subprocess.run(["docker", *args], check=False, capture_output=True, text=True, timeout=timeout,
                       cwd=RAIZ, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"docker {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout.strip()


def containers() -> dict[str, str]:
    """serviço do compose → nome do container (api, worker, ollama...)."""
    saida = docker("compose", "ps", "--format", "{{.Service}}|{{.Name}}")
    return dict(linha.split("|", 1) for linha in saida.splitlines() if "|" in linha)


def estado_containers(nomes: dict[str, str]) -> dict[str, dict]:
    """Reinícios e OOM de cada container (para saber se algum processo caiu)."""
    estado = {}
    for servico, nome in nomes.items():
        bruto = docker("inspect", "-f", "{{.RestartCount}}|{{.State.OOMKilled}}|{{.State.StartedAt}}"
                       "|{{.State.Status}}", nome)
        reinicios, oom, inicio, status = bruto.split("|")
        estado[servico] = {"reinicios": int(reinicios), "oom": oom == "true", "inicio": inicio,
                           "rodando": status == "running"}
    return estado


def mib(texto: str) -> float:
    numero = float("".join(ch for ch in texto if ch.isdigit() or ch == ".") or 0)
    unidade = texto.strip().lstrip("0123456789.").strip().lower()
    return numero * {"b": 1 / 1048576, "kib": 1 / 1024, "kb": 1 / 1000, "mib": 1, "mb": 1,
                     "gib": 1024, "gb": 1000}.get(unidade, 1)


@dataclass
class Amostra:
    t: datetime
    servico: str
    cpu: float
    mem_mib: float


class Monitor(threading.Thread):
    """`docker stats` a cada `intervalo` segundos: CPU e memória de api, worker, db e ollama."""

    def __init__(self, nomes: dict[str, str], intervalo: float):
        super().__init__(daemon=True)
        self.servico_de = {v: k for k, v in nomes.items()}
        self.intervalo, self.parar, self.amostras = intervalo, threading.Event(), []

    def run(self):
        while not self.parar.is_set():
            try:
                saida = docker("stats", "--no-stream", "--format",
                               "{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}", timeout=60)
                t = agora()
                for linha in saida.splitlines():
                    nome, cpu, mem = linha.split("|")
                    if nome in self.servico_de:
                        self.amostras.append(Amostra(t, self.servico_de[nome],
                                                     float(cpu.strip("%") or 0),
                                                     mib(mem.split("/")[0])))
            except Exception as exc:  # noqa: BLE001 — o monitor não derruba o teste
                log(f"monitor: {exc}")
            self.parar.wait(self.intervalo)

    def pico(self, servico: str, de: datetime | None = None, ate: datetime | None = None):
        v = [a for a in self.amostras if a.servico == servico
             and (de is None or a.t >= de) and (ate is None or a.t <= ate)]
        return (max((a.mem_mib for a in v), default=None), max((a.cpu for a in v), default=None))


class Usuarios:
    """`n` usuários navegando nas telas (GETs com pausa de 1 a 3 s), medindo o tempo de resposta."""

    def __init__(self, api: Api, n: int):
        self.api, self.n, self.parar, self.medidas = api, n, threading.Event(), []
        self.fase = ""

    def _usuario(self):
        cliente = httpx.Client(base_url=self.api.c.base_url, headers=self.api.c.headers, timeout=60)
        while not self.parar.is_set():
            tela = random.choice(TELAS)
            inicio = time.perf_counter()
            try:
                codigo = cliente.get(tela).status_code
            except httpx.HTTPError:
                codigo = 0
            self.medidas.append((self.fase, tela, time.perf_counter() - inicio, codigo))
            self.parar.wait(random.uniform(1, 3))

    def rodar(self, fase: str):
        self.fase = fase
        self.parar.clear()
        self.threads = [threading.Thread(target=self._usuario, daemon=True) for _ in range(self.n)]
        for t in self.threads:
            t.start()

    def encerrar(self):
        self.parar.set()
        for t in self.threads:
            t.join(timeout=70)


# ------------------------------------------------------------------ inventário e amostra
@dataclass
class Recurso:
    id: int
    nome: str | None
    dataset: str
    orgao: str | None
    formato: str
    url: str
    alterado: datetime | None
    mb: float | None = None
    faixa: str = "desconhecido"


def inventario(api: Api) -> list[Recurso]:
    """Recursos varríveis (CSV/TSV/TXT/XLSX, fora do dicionário) dos datasets ativos."""
    datasets = [d for d in api.get("/inventario/datasets")["datasets"]
                if d["situacao"] != "Fora do portal"]
    saida = []
    for i, d in enumerate(datasets, 1):
        if i % 50 == 0:
            log(f"  inventário: {i}/{len(datasets)} datasets")
        for r in api.get(f"/inventario/datasets/{d['id']}")["recursos"]:
            fmt = formato_do_recurso(r["formato"], r["url"])
            if r["eh_dicionario_dados"] or not r["url"] or fmt not in SUPORTADOS:
                continue
            saida.append(Recurso(r["id"], r["nome"], d["titulo"], d["orgao_nome"], fmt, r["url"],
                                 data(r["last_modified"]) or data(r["created"])))
    return saida


def medir_tamanhos(recursos: list[Recurso], intervalo: float) -> None:
    """Tamanho pelo Content-Length (só o cabeçalho; o corpo não é baixado), com pausa entre os
    pedidos para não esbarrar no limite do portal (HTTP 429)."""
    with httpx.Client(timeout=30, follow_redirects=True) as c:
        for i, r in enumerate(recursos, 1):
            try:
                with c.stream("GET", r.url) as resp:
                    tamanho = resp.headers.get("content-length")
                    r.mb = int(tamanho) / 1048576 if resp.status_code == 200 and tamanho else None
            except httpx.HTTPError:
                r.mb = None
            r.faixa = faixa(r.mb)
            if i % 20 == 0:
                log(f"  tamanhos: {i}/{len(recursos)}")
            time.sleep(intervalo)


def escolher_amostra(candidatos: list[Recurso], n: int, limite_mb: float) -> list[Recurso]:
    """~40% pequenos, ~35% médios, ~25% grandes; sempre o maior abaixo do limite (pergunta 4)."""
    dentro = [r for r in candidatos if r.mb is None or r.mb <= limite_mb]
    por_faixa = {f: [r for r in dentro if r.faixa == f] for f, *_ in FAIXAS}
    cota = {"pequeno": round(n * .40), "medio": round(n * .35), "grande": n - round(n * .40)
            - round(n * .35)}
    escolhidos = []
    maiores = sorted((r for r in dentro if r.mb is not None), key=lambda r: -r.mb)
    if maiores:
        escolhidos.append(maiores[0])
    for f, q in cota.items():
        livres = [r for r in por_faixa[f] if r not in escolhidos]
        escolhidos += random.sample(livres, min(q, len(livres)))
    sobra = [r for r in dentro if r not in escolhidos]
    escolhidos += random.sample(sobra, max(0, min(n - len(escolhidos), len(sobra))))
    return escolhidos[:n]


def ordenar_amostra(amostra: list[Recurso], com_teto: bool) -> list[Recurso]:
    """Ordem dos pedidos (o worker varre um por vez, nessa ordem): do menor para o maior, para o
    tempo do teste render o máximo de medições antes de chegar aos arquivos lentos. Com teto por
    recurso, o maior vai primeiro: a medição de memória do arquivo grande (pergunta 4) fica
    garantida e custa no máximo o teto."""
    crescente = sorted(amostra, key=lambda r: r.mb if r.mb is not None else 5.0)
    if com_teto and crescente and crescente[-1].mb is not None:
        return [crescente[-1], *crescente[:-1]]
    return crescente


# ------------------------------------------------------------------ fila
def enfileirar(api: Api, recursos: list[Recurso]) -> dict[int, int]:
    """recurso → id da varredura criada (um pedido por recurso, escopo `recurso`)."""
    ids = {}
    for r in recursos:
        pedido = api.post("/lgpd/varreduras", {"escopo": "recurso", "id": r.id})
        if pedido["varreduras"]:
            ids[r.id] = pedido["varreduras"][0]["id"]
    return ids


def varreduras(api: Api) -> dict[int, dict]:
    return {v["id"]: v for v in api.get("/lgpd/varreduras", limite=200)["varreduras"]}


def esperar(api: Api, ids: set[int], tempo_maximo: float, rotulo: str,
            teto_s: float | None = None, ao_passar_do_teto=None) -> dict[int, dict]:
    """Acompanha as varreduras até todas terminarem ou o tempo acabar. Uma consulta que falha
    (rede, API reiniciando, login vencido) não derruba o teste depois de horas de medição: a espera
    tenta de novo e, no fim do tempo, devolve a última leitura boa.

    Com `teto_s`, a varredura que estiver em execução há mais tempo que isso é entregue uma vez a
    `ao_passar_do_teto` (que a interrompe, para a fila seguir)."""
    limite = time.monotonic() + tempo_maximo
    nossas: dict[int, dict] = {}
    avisadas: set[int] = set()
    registro = (-1, 0.0)  # (concluídas, quando) do último registro: não repete a mesma linha por horas
    while True:
        try:
            todas = varreduras(api)
        except httpx.HTTPError as exc:
            log(f"  {rotulo}: falha ao consultar a fila ({type(exc).__name__}: {exc}); "
                "tentando de novo")
            if time.monotonic() > limite:
                return nossas
            time.sleep(30)
            continue
        nossas = {i: todas[i] for i in ids if i in todas}
        feitas = sum(1 for v in nossas.values() if v["status"] in FINAIS)
        if feitas != registro[0] or time.monotonic() - registro[1] >= 300:
            atual = next((v for v in nossas.values() if v["status"] == "executando"), None)
            ini = data(atual["iniciada_em"]) if atual else None
            log(f"  {rotulo}: {feitas}/{len(ids)} concluída(s)" + (
                f"; em execução: recurso {atual['recurso_id']} há "
                f"{duracao((agora() - ini).total_seconds())}" if ini else ""))
            registro = (feitas, time.monotonic())
        if feitas == len(ids) or time.monotonic() > limite:
            return nossas
        if teto_s and ao_passar_do_teto:
            for v in nossas.values():
                ini = data(v["iniciada_em"])
                if (v["status"] == "executando" and v["id"] not in avisadas and ini
                        and (agora() - ini).total_seconds() > teto_s):
                    avisadas.add(v["id"])
                    try:
                        ao_passar_do_teto(v)
                    except Exception as exc:  # noqa: BLE001 — a medição continua sem o teto
                        log(f"  {rotulo}: não deu para interromper a varredura {v['id']}: {exc}")
        time.sleep(10)


# ------------------------------------------------------------------ teste
@dataclass
class Resultado:
    inicio: str = ""
    maquina: dict = field(default_factory=dict)
    ia: dict = field(default_factory=dict)
    inventario: dict = field(default_factory=dict)
    amostra: list = field(default_factory=list)
    memoria: dict = field(default_factory=dict)
    containers_antes: dict = field(default_factory=dict)
    containers_depois: dict = field(default_factory=dict)
    telas: dict = field(default_factory=dict)
    fila: dict = field(default_factory=dict)
    teto_s: float | None = None  # teto de tempo por recurso usado na amostra
    reinicios_do_teste: int = 0  # worker reiniciado pelo próprio teste (teto, fila, limpeza)
    avisos: list = field(default_factory=list)  # o que saiu do roteiro (tempo, fase pulada, erro)


def reiniciar_worker(res: Resultado, motivo: str, na_hora: bool = False) -> None:
    """`na_hora` mata o processo sem os 10 s de espera do `restart`: nesse intervalo a varredura
    poderia terminar e o worker pegar o pedido seguinte, que seria interrompido no lugar dela."""
    log(f"  reiniciando o worker ({motivo})...")
    if na_hora:
        docker("compose", "kill", "worker", timeout=60)
        try:
            docker("compose", "start", "worker", timeout=120)
        except RuntimeError:
            docker("compose", "up", "-d", "worker", timeout=180)
    else:
        docker("compose", "restart", "worker", timeout=180)
    res.reinicios_do_teste += 1


def esvaziar_fila(api: Api, res: Resultado, motivo: str) -> bool:
    """Deixa a fila vazia para a fase seguinte: cancela os pedidos pendentes e, se sobrar uma
    varredura em execução (o cancelamento não a alcança), reinicia o worker. Ela vira erro de
    interrupção; se o recurso voltar à fila, a volta seguinte interrompe de novo — a retomada
    automática é uma só por recurso. Devolve se a fila ficou vazia."""
    for _ in range(4):
        api.post("/lgpd/varreduras/cancelar")
        if not api.get("/lgpd/varreduras", limite=1)["em_andamento"]:
            return True
        rodando = {i for i, v in varreduras(api).items() if v["status"] == "executando"}
        reiniciar_worker(res, motivo, na_hora=True)
        limite = time.monotonic() + 180  # o worker marca a interrompida no ciclo seguinte (~1 min)
        while time.monotonic() < limite:
            time.sleep(5)
            if not rodando & {i for i, v in varreduras(api).items() if v["status"] == "executando"}:
                break
    api.post("/lgpd/varreduras/cancelar")
    return not api.get("/lgpd/varreduras", limite=1)["em_andamento"]


def verificar_ia(api: Api) -> dict:
    perfis = {p["id"]: p for p in api.get("/ia/perfis")}
    info = {}
    for t in api.get("/ia/tarefas"):
        if t["tarefa"] in ("classificacao_dp", "embeddings_dp"):
            p = perfis.get(t["perfil_id"])
            info[t["tarefa"]] = (f"{p['nome']} ({p['tipo']}, {p['modelo']})" if p
                                 else "sem perfil vinculado")
    info["simulada"] = any("(mock" in v or "sem perfil" in v for v in info.values())
    return info


def fase_amostra(api, args, res, monitor, usuarios, nomes):
    log("Inventário do portal (recursos varríveis)...")
    todos = inventario(api)
    hoje = agora()
    alterados = {d: sum(1 for r in todos if r.alterado and r.alterado >= hoje - timedelta(days=d))
                 for d in (1, 7, 30)}
    res.inventario = {"varriveis": len(todos), "alterados_ultimos": alterados,
                      "por_formato": {f: sum(1 for r in todos if r.formato == f)
                                      for f in sorted({r.formato for r in todos})}}
    log(f"  {len(todos)} recursos varríveis; alterados nos últimos 30 dias: {alterados[30]}")

    candidatos = random.sample(todos, min(args.candidatos, len(todos)))
    log(f"Tamanho de {len(candidatos)} candidatos (sorteados)...")
    medir_tamanhos(candidatos, args.intervalo_portal)
    res.inventario["faixas_candidatos"] = {
        f: sum(1 for r in candidatos if r.faixa == f) for f in ("pequeno", "medio", "grande",
                                                                 "desconhecido")}
    teto_s = args.teto_recurso_min * 60 if args.teto_recurso_min else None
    res.teto_s = teto_s
    amostra = ordenar_amostra(escolher_amostra(candidatos, args.amostra, args.limite_mb),
                              bool(teto_s))
    log(f"Amostra: {len(amostra)} recursos — " + ", ".join(
        f"{f}: {sum(1 for r in amostra if r.faixa == f)}" for f in ("pequeno", "medio", "grande",
                                                                   "desconhecido")))

    if args.usuarios:
        log(f"Linha de base: {args.usuarios} usuário(s) nas telas por {args.base_s} s, sem varredura")
        usuarios.rodar("sem varredura")
        time.sleep(args.base_s)
        usuarios.encerrar()

    res.containers_antes = estado_containers(nomes)
    log("Enfileirando a amostra e acompanhando (usuários nas telas ao mesmo tempo)...")
    if args.usuarios:
        usuarios.rodar("durante a varredura")
    ids = enfileirar(api, amostra)
    passaram: set[int] = set()  # varreduras interrompidas pelo teste ao passar do teto

    def passou_do_teto(v: dict) -> None:
        passaram.add(v["id"])
        log(f"  recurso {v['recurso_id']} passou do teto de {args.teto_recurso_min:g} min: "
            "interrompido para a fila seguir")
        reiniciar_worker(res, "teto de tempo por recurso", na_hora=True)

    meus = set(ids.values())
    try:
        feitas = esperar(api, meus, args.tempo_maximo_h * 3600, "amostra", teto_s, passou_do_teto)
    except Exception as exc:  # noqa: BLE001 — o que já foi varrido não se perde
        log(f"  amostra: a espera falhou ({type(exc).__name__}: {exc}); lendo o que já terminou")
        res.avisos.append(f"A espera pela amostra falhou ({type(exc).__name__}: {exc}); o "
                          "relatório usa o que tinha terminado até ali.")
        todas = varreduras(api)
        feitas = {i: todas[i] for i in meus if i in todas}
    if args.usuarios:
        usuarios.encerrar()

    for r in amostra:
        v = feitas.get(ids.get(r.id, -1))
        if v is None:
            continue
        ini, fim = data(v["iniciada_em"]), data(v["finalizada_em"])
        ate = fim or agora()  # sem fim = ainda em execução quando o tempo do teste acabou
        mem_w, cpu_w = monitor.pico("worker", ini, ate) if ini else (None, None)
        mem_o, cpu_o = monitor.pico("ollama", ini, ate) if ini else (None, None)
        # "teto" = interrompida pelo teste; a duração dela é um piso (levaria mais).
        # "ao_lado" = começou bem na hora em que o worker foi reiniciado por causa de outro recurso
        if v["id"] in passaram and v["status"] != "ok":
            status = "teto"
        elif v["status"] == "erro" and INTERROMPIDA in (v["erro"] or ""):
            status = "ao_lado"
        else:
            status = v["status"]
        res.amostra.append({
            **asdict(r), "alterado": None, "url": None, "status": status,
            "segundos": (ate - ini).total_seconds() if ini else None,
            "espera_fila_s": (ini - data(v["solicitada_em"])).total_seconds() if ini else None,
            "linhas": v["linhas_analisadas"], "chamadas_ia": v["chamadas_ia"],
            "achados": v["achados"], "modelo": v["modelo"], "aviso": v["aviso"], "erro": v["erro"],
            "pico_mem_worker_mib": mem_w, "pico_cpu_worker": cpu_w,
            "pico_mem_ollama_mib": mem_o, "pico_cpu_ollama": cpu_o})
    faltam = sum(1 for a in res.amostra if a["status"] in ("pendente", "executando"))
    if faltam:
        res.avisos.append(f"O tempo máximo da amostra ({args.tempo_maximo_h:g} h) acabou com "
                          f"{faltam} recurso(s) sem terminar; os pedidos que sobraram foram "
                          "cancelados.")
    try:  # pedidos que sobraram e retomadas dos recursos interrompidos no teto
        if not esvaziar_fila(api, res, "limpeza da fila depois da amostra"):
            res.avisos.append("A fila não esvaziou depois da amostra.")
    except Exception as exc:  # noqa: BLE001
        res.avisos.append(f"Não deu para esvaziar a fila depois da amostra: {exc}")
    return {r.id for r in amostra}, todos


def fase_fila(api, args, res, nomes, todos, usados):
    """Pergunta 6: worker reiniciado no meio, cancelamento e retomada."""
    if api.get("/lgpd/varreduras", limite=1)["em_andamento"]:
        res.avisos.append("Teste da fila (pergunta 6) não executado: a fila não estava vazia "
                          "depois da amostra.")
        return
    livres = [r for r in todos if r.id not in usados]
    if len(livres) < args.fila:
        log("Fila: recursos insuficientes; fase pulada.")
        return
    # Com a IA local uma varredura pode levar horas. Os primeiros pedidos são recursos da amostra
    # com duração já conhecida (30 s a 10 min): o 1º demora o bastante para ser pego em execução
    # ao reiniciar o worker, e o que estiver rodando na hora do cancelamento termina em minutos.
    por_id = {r.id: r for r in todos}
    conhecidos = sorted((a for a in res.amostra if a["status"] == "ok" and a["id"] in por_id
                         and 30 <= (a["segundos"] or 0) <= 600),
                        key=lambda a: abs(a["segundos"] - 180))
    if len(conhecidos) >= 2:
        seguintes = [por_id[a["id"]] for a in sorted(conhecidos[1:], key=lambda a: -a["segundos"])]
        resto = random.sample(livres, max(0, args.fila - 1 - len(seguintes)))
        lote = [por_id[conhecidos[0]["id"]], *seguintes, *resto][:args.fila]
        curto = por_id[min(conhecidos, key=lambda a: a["segundos"])["id"]]
    else:
        lote = random.sample(livres, args.fila)
        # o maior primeiro: dá tempo de reiniciar o worker com ele em execução
        lote.sort(key=lambda r: -(r.mb or 0))
        curto = min(livres, key=lambda r: r.mb if r.mb is not None else 1e9)
        res.avisos.append("Teste da fila: a amostra não teve dois recursos com duração entre 30 s "
                          "e 10 min, então os pedidos foram sorteados; uma varredura longa pode "
                          "ter atrapalhado as checagens da pergunta 6.")
    log(f"Fila: {len(lote)} pedidos; o worker será reiniciado durante a primeira varredura")
    ids = enfileirar(api, lote)
    primeiro = ids.get(lote[0].id)
    limite = time.monotonic() + 600
    while time.monotonic() < limite:
        v = varreduras(api).get(primeiro)
        # terminou antes de ser pega em execução (arquivo pequeno ou IA simulada): não adianta
        # esperar; as checagens do reinício ficam "não verificado"
        if v and v["status"] in FINAIS | {"executando"}:
            break
        time.sleep(1)
    time.sleep(3)
    rodando = varreduras(api).get(primeiro, {}).get("status") == "executando"
    reiniciar_worker(res, "teste da fila: docker compose restart worker")
    log("  esperando o worker retomar (até 3 min)...")
    if rodando:  # o worker marca a interrompida no primeiro ciclo depois de subir (~1 min)
        limite = time.monotonic() + 180
        while (time.monotonic() < limite
               and varreduras(api).get(primeiro, {}).get("status") == "executando"):
            time.sleep(5)
        time.sleep(15)  # o mesmo ciclo recoloca o recurso na fila e pega o pedido seguinte
    else:
        time.sleep(90)
    todas = varreduras(api)
    interrompida = todas.get(primeiro, {})
    retomada = [v for v in todas.values() if v["recurso_id"] == lote[0].id and v["id"] > primeiro]
    log("  cancelando o que ainda está na fila...")
    pendentes_antes = sum(1 for i in ids.values() if todas.get(i, {}).get("status") == "pendente")
    canceladas = api.post("/lgpd/varreduras/cancelar")["canceladas"]
    limite = time.monotonic() + 1800
    while api.get("/lgpd/varreduras", limite=1)["em_andamento"] and time.monotonic() < limite:
        time.sleep(10)
    em_andamento = api.get("/lgpd/varreduras", limite=1)["em_andamento"]
    log("  pedido novo depois do cancelamento (a fila não pode ter travado)...")
    novo = enfileirar(api, [curto])
    depois = esperar(api, set(novo.values()), 900, "pedido novo") if novo else {}
    todas = varreduras(api)
    nossas = [v for v in todas.values() if v["recurso_id"] in {r.id for r in lote}
              and v["id"] >= min(ids.values()) and v["id"] not in novo.values()]
    oks: dict[int, int] = {}
    for v in nossas:
        if v["status"] == "ok":
            oks[v["recurso_id"]] = oks.get(v["recurso_id"], 0) + 1
    sobrou = [i for i in ids.values() if todas.get(i, {}).get("status") == "pendente"]
    # None = não deu para verificar (a varredura terminou antes do reinício)
    res.fila = {"pedidos": len(ids), "checagens": [
        ("A varredura em execução virou erro de interrupção ao reiniciar o worker",
         (interrompida.get("status") == "erro" and INTERROMPIDA in (interrompida.get("erro") or ""))
         if rodando else None),
        ("O recurso interrompido voltou à fila uma única vez",
         len(retomada) == 1 if rodando else None),
        ("O cancelamento tirou da fila todos os pendentes", not sobrou and
         canceladas >= pendentes_antes - 1),
        ("Depois do cancelamento, nada ficou preso em execução", em_andamento == 0),
        ("Nenhum recurso foi varrido com sucesso mais de uma vez", all(n == 1 for n in oks.values())),
        ("Um pedido novo depois disso foi executado (a fila não travou)",
         bool(depois) and all(v["status"] in FINAIS for v in depois.values())),
    ], "canceladas": canceladas, "pendentes_antes_de_cancelar": pendentes_antes}
    try:
        esvaziar_fila(api, res, "limpeza da fila no fim do teste")
    except Exception as exc:  # noqa: BLE001
        res.avisos.append(f"Não deu para esvaziar a fila no fim do teste: {exc}")


# ------------------------------------------------------------------ relatório
SITUACAO = {"ok": "concluído", "teto": "interrompido ao passar do teto", "erro": "erro",
            "ao_lado": "interrompido por um reinício do worker feito para outro recurso",
            "ignorado": "ignorado", "pendente": "não chegou a começar",
            "executando": "em execução quando o tempo do teste acabou", "cancelada": "cancelado"}


def relatorio(res: Resultado, args, usuarios: Usuarios) -> str:
    """Texto do `resultado.md`: as seis respostas."""
    am = [a for a in res.amostra if a["status"] == "ok" and a["segundos"] is not None]
    # interrompidos (teto por recurso ou fim do tempo do teste): a duração medida é um piso
    cortados = [a for a in res.amostra if a["status"] in ("teto", "executando")
                and a["segundos"] is not None]
    medidos = am + cortados
    seg = [a["segundos"] for a in medidos]
    media = statistics.fmean(seg) if seg else None
    teto_min = (res.teto_s or 0) / 60
    piso = "pelo menos " if cortados else ""

    def com_piso(grupo: list[dict], valor: float | None) -> str:
        """Duração, com "≥" quando o valor cai num recurso interrompido (o tempo real é maior)."""
        if valor is None:
            return "—"
        cortes = [a["segundos"] for a in grupo if a["status"] in ("teto", "executando")]
        return ("≥ " if cortes and valor >= min(cortes) else "") + duracao(valor)

    def quantos(status: str) -> int:
        return sum(1 for a in res.amostra if a["status"] == status)

    linhas = []
    w = linhas.append
    w(f"# Teste de capacidade da varredura LGPD — {res.inicio[:16].replace('T', ' ')} UTC\n")
    w(f"**Máquina:** {res.maquina.get('cpus')} CPUs, {res.maquina.get('ram_gib')} GiB de RAM "
      f"para o Docker ({res.maquina.get('so')}). **IA da varredura:** "
      f"{res.ia.get('classificacao_dp')}; embeddings: {res.ia.get('embeddings_dp')}.\n")
    if res.ia.get("simulada"):
        w("> **Atenção: IA simulada.** Os tempos abaixo medem download e regras, não o modelo "
          "local. Não use para dimensionar o servidor; ver README (IA local de verdade).\n")
    if res.avisos:
        w("> **O que saiu do roteiro**")
        for aviso in res.avisos:
            w(f"> - {aviso}")
        w("")

    # 1
    w("## 1. Tempo por recurso\n")
    partes = [f"{len(am)} concluídos com sucesso"]
    if quantos("teto"):
        partes.append(f"{quantos('teto')} interrompidos pelo teste ao passar do teto de "
                      f"{teto_min:g} min")
    partes += [f"{quantos('ignorado')} ignorados (limite de tamanho ou formato)",
               f"{quantos('erro')} com erro"]
    if quantos("ao_lado"):
        partes.append(f"{quantos('ao_lado')} não medidos (começaram bem na hora de um reinício do "
                      "worker feito pelo teste)")
    faltam = quantos("pendente") + quantos("executando") + quantos("cancelada")
    if faltam:
        partes.append(f"{faltam} sem terminar no tempo máximo do teste")
    w(f"Amostra: {len(res.amostra)} recursos; " + "; ".join(partes) + ".\n")
    if res.teto_s:
        w(f"Teto por recurso: {teto_min:g} min. A varredura que passa disso é interrompida pelo "
          "teste (reinício do worker), para um arquivo lento não segurar a fila. O tempo dela "
          "entra nas contas como piso (\"≥\"): a varredura completa levaria mais.\n")
    w("| Faixa | Concluídos | Interrompidos | Mediana | p90 | s por MB (mediana) | Linhas (mediana) "
      "| Chamadas à IA (mediana) |")
    w("|---|---|---|---|---|---|---|---|")
    por_faixa = {}
    for f in ("pequeno", "medio", "grande", "desconhecido"):
        g = [a for a in medidos if a["faixa"] == f]
        ok = [a for a in g if a["status"] == "ok"]
        por_faixa[f] = [a["segundos"] for a in g]
        # abaixo de 0,1 MB o tempo fixo (baixar, carregar o modelo) domina e "s por MB" não diz nada
        spm = med([a["segundos"] / a["mb"] for a in ok if a["mb"] and a["mb"] >= 0.1])
        lin = med([a["linhas"] for a in ok if a["linhas"] is not None])
        ia = med([a["chamadas_ia"] for a in ok if a["chamadas_ia"] is not None])
        w(f"| {f} | {len(ok)} | {len(g) - len(ok)} | {com_piso(g, med(por_faixa[f]))} | "
          f"{com_piso(g, pct(por_faixa[f], 90))} | {f'{spm:.1f}' if spm is not None else '—'} | "
          f"{lin if lin is not None else '—'} | {ia if ia is not None else '—'} |")
    w(f"\n**Geral:** mediana {com_piso(medidos, med(seg))}, p90 {com_piso(medidos, pct(seg, 90))}, "
      f"máximo {com_piso(medidos, max(seg, default=None))}, média "
      f"{('≥ ' if cortados else '') + duracao(media) if media is not None else '—'}. "
      "Detalhe por recurso em `amostra.csv`.\n")
    com_ia = [a for a in am if a["chamadas_ia"]]
    if com_ia:
        chamadas = sum(a["chamadas_ia"] for a in com_ia)
        w(f"**IA local:** {chamadas} chamadas em {len(com_ia)} recurso(s) concluídos que usaram o "
          f"modelo — {sum(a['segundos'] for a in com_ia) / chamadas:.1f} s de varredura por "
          "chamada.\n")

    # 2
    w("## 2. Portal inteiro\n")
    total = res.inventario.get("varriveis", 0)
    fr = res.inventario.get("faixas_candidatos") or {}
    n_cand = sum(fr.values()) or 1
    limite_txt = f"{args.limite_mb:g} MB" if args.limite_mb is not None else "tamanho"

    def media_de(valores: list[float]) -> float | None:
        return statistics.fmean(valores) if valores else None

    def projecao(estatistica, padrao: float | None, grupos: dict | None = None) -> float:
        """Soma, por faixa de tamanho, de (recursos estimados na faixa) x (tempo da faixa)."""
        grupos = por_faixa if grupos is None else grupos
        return sum(total * fr[f] / n_cand * (estatistica(grupos.get(f) or []) or padrao or 0)
                   for f in fr)

    w(f"{total} recursos varríveis no portal (CSV/TSV/TXT/XLSX). Proporção por tamanho estimada "
      f"pelos {n_cand} candidatos sorteados: " + ", ".join(f"{f} {fr[f]}" for f in fr) + ".\n")
    if seg:
        w("**Projeção da varredura completa (um recurso por vez, como o worker faz):** "
          f"**{piso}{duracao(projecao(media_de, media))}** "
          f"pela média da amostra (de {duracao(projecao(med, med(seg)))} pela mediana a "
          f"{duracao(projecao(lambda v: pct(v, 90), pct(seg, 90)))} pelo p90), sem contar os "
          f"recursos acima do limite de {limite_txt}, que são ignorados."
          + (f" É um piso: {len(cortados)} recurso(s) da amostra foram interrompidos antes do fim "
             "e levariam mais." if cortados else "") + "\n")
        # A conta acima supõe que todo recurso do portal é varrido. Os que a varredura ignora ou
        # não consegue ler (ZIP, link quebrado...) terminam em segundos e também existem no portal.
        terminados = [a for a in res.amostra if a["segundos"] is not None
                      and a["status"] in ("ok", "teto", "executando", "ignorado", "erro")]
        nao_varridos = len(terminados) - len(medidos)
        if nao_varridos:
            todos_por_faixa = {f: [a["segundos"] for a in terminados if a["faixa"] == f] for f in fr}
            geral = media_de([a["segundos"] for a in terminados])
            w(f"Na amostra, {nao_varridos} de {len(terminados)} recursos não chegaram a ser varridos "
              "(ignorados ou com erro). Se o portal inteiro tiver a mesma proporção, a varredura "
              f"completa cai para **{piso}{duracao(projecao(media_de, geral, todos_por_faixa))}**.\n")
        poucas = [f"{f} ({len(por_faixa.get(f) or [])})" for f in fr
                  if fr[f] and len(por_faixa.get(f) or []) < 5]
        if poucas:
            w("Faixas com menos de 5 recursos medidos: " + ", ".join(poucas) + ". Nelas a projeção "
              "é só uma ordem de grandeza; faixa sem nenhuma medição usa o tempo geral da amostra.\n")
    else:
        w("Nenhuma varredura da amostra foi medida: não dá para projetar.\n")

    # 3
    w("## 3. Varredura noturna incremental\n")
    alt = res.inventario.get("alterados_ultimos") or {1: 0, 7: 0, 30: 0}
    por_dia = alt[30] / 30
    w(f"Recursos varríveis alterados (last_modified): {alt[1]} no último dia, {alt[7]} em 7 dias, "
      f"{alt[30]} em 30 dias — média de **{por_dia:.1f} por dia**.\n")
    if media is not None:
        noite = por_dia * media
        cabe = "Cabe na janela." if noite <= args.janela_h * 3600 else "**Não cabe na janela.**"
        acumula = (" — **o volume diário passa desse teto e a fila acumularia**"
                   if por_dia > args.max_por_execucao else "")
        w(f"Tempo estimado por noite: **{piso}{duracao(noite)}** pela média da amostra "
          f"({duracao(por_dia * (med(seg) or 0))} pela mediana; no ritmo dos últimos 7 dias: "
          f"{duracao(alt[7] / 7 * media)} por noite). Janela considerada: {args.janela_h:g} h "
          f"(varredura às 05:00, expediente às 08:00). {cabe} Cada execução varre no máximo "
          f"{args.max_por_execucao} recursos{acumula}.\n")
    else:
        w("Nenhuma varredura da amostra foi medida: não dá para estimar o tempo por noite.\n")

    # 4
    w("## 4. Arquivo grande e memória\n")
    # Só entre os que a varredura leu de fato: um arquivo ignorado ou com erro não ocupa memória.
    # O portal nem sempre informa o tamanho, então também sai o arquivo com mais linhas.
    varridos = [a for a in res.amostra if a["status"] in ("ok", "teto", "executando")]

    def pico(valor: float | None) -> str:
        return f"{valor:.0f} MiB" if valor else "sem medição"

    def arquivo(rotulo: str, a: dict) -> None:
        tam = ("tamanho não informado pelo portal" if a["mb"] is None
               else f"{a['mb']:.1f} MB" if a["mb"] >= 1 else f"{a['mb'] * 1024:.0f} KB")
        lin = (f"{a['linhas']} linhas" if a["status"] == "ok"
               else "linhas não contadas: a varredura não terminou")
        w(f"{rotulo}: `{a['nome']}` — **{tam}** ({a['formato']}, {lin}), "
          f"{SITUACAO.get(a['status'], a['status'])}, {com_piso([a], a['segundos'])}. Pico durante "
          f"ele: worker {pico(a['pico_mem_worker_mib'])}, Ollama {pico(a['pico_mem_ollama_mib'])}.\n")

    maior = max((a for a in varridos if a["mb"]), key=lambda a: a["mb"], default=None)
    mais_linhas = max((a for a in varridos if a["status"] == "ok" and a["linhas"]),
                      key=lambda a: a["linhas"], default=None)
    if maior:
        arquivo("Maior arquivo varrido, pelo tamanho que o portal informa", maior)
    if mais_linhas and mais_linhas is not maior:
        arquivo("Arquivo varrido com mais linhas", mais_linhas)
    w("| Container | Pico de memória (MiB) | Pico de CPU (%) | Reiniciou no teste "
      "| Morto por falta de memória |")
    w("|---|---|---|---|---|")
    for s, m in res.memoria.items():
        a, d = res.containers_antes.get(s, {}), res.containers_depois.get(s, {})
        if d and not d.get("rodando", True):
            reiniciou = "**caiu e não voltou**"
        elif s == "worker" and res.reinicios_do_teste:
            reiniciou = f"{res.reinicios_do_teste} vez(es), pelo próprio teste"
        elif a and d and (d["reinicios"] != a["reinicios"] or d["inicio"] != a["inicio"]):
            reiniciou = "**sim**"
        else:
            reiniciou = "não"
        w(f"| {s} | {m['pico_mem_mib'] or 0:.0f} | {m['pico_cpu'] or 0:.0f} | {reiniciou} | "
          f"{'**sim**' if d.get('oom') else 'não'} |")
    soma = sum(m["pico_mem_mib"] or 0 for m in res.memoria.values())
    if soma:
        w(f"\nSoma dos picos: **{soma / 1024:.1f} GiB** (o Docker tinha "
          f"{res.maquina.get('ram_gib')} GiB). Os picos não acontecem todos ao mesmo tempo, então "
          "a soma é uma margem segura de memória para o servidor, fora o sistema operacional.")
    if res.reinicios_do_teste:
        w("\nOs reinícios do worker foram feitos pelo teste (teto por recurso, teste da fila e "
          "limpeza da fila); não são quedas.")
    w("")

    # 5
    w("## 5. Telas durante a varredura\n")
    if usuarios.medidas:
        w(f"{args.usuarios} usuários simulados abrindo as telas (pausa de 1 a 3 s entre cliques).\n")
        w("| Tela | p50 sem varredura | p95 sem varredura | p50 durante | p95 durante | Máximo durante | Erros durante |")
        w("|---|---|---|---|---|---|---|")
        pior = 0.0
        for tela in TELAS:
            b = [m[2] for m in usuarios.medidas if m[0] == "sem varredura" and m[1] == tela]
            d = [m for m in usuarios.medidas if m[0] == "durante a varredura" and m[1] == tela]
            dt = [m[2] for m in d]
            erros = sum(1 for m in d if m[3] >= 500 or m[3] == 0)
            pior = max(pior, pct(dt, 95) or 0)
            w(f"| `{tela}` | {duracao(med(b))} | {duracao(pct(b, 95))} | {duracao(med(dt))} | "
              f"{duracao(pct(dt, 95))} | {duracao(max(dt, default=None))} | {erros} |")
        w(f"\n**{'OK' if pior <= args.limite_p95_s else 'Atenção'}:** pior p95 durante a varredura "
          f"{duracao(pior)} (limite usado: {args.limite_p95_s:g} s).\n")
    else:
        w("Fase não executada.\n")

    # 6
    w("## 6. Fila: reinício, cancelamento e retomada\n")
    if res.fila:
        w(f"{res.fila['pedidos']} pedidos; {res.fila['canceladas']} cancelados (havia "
          f"{res.fila['pendentes_antes_de_cancelar']} pendentes).\n")
        for texto, ok in res.fila["checagens"]:
            marca = "⚪ não verificado —" if ok is None else "✅" if ok else "❌"
            w(f"- {marca} {texto}")
        w("")
    else:
        w("Fase não executada.\n")
    return "\n".join(linhas)


def gravar(res: Resultado, args, monitor: Monitor, usuarios: Usuarios, pasta: Path) -> Path:
    """Grava primeiro as medições (`bruto.json`, `amostra.csv`) e depois o `resultado.md`. Se a
    montagem do relatório falhar, sai um relatório mínimo com o erro: as medições não se perdem."""
    bruto = asdict(res) | {"recursos_monitor": [asdict(a) | {"t": a.t.isoformat()}
                                                for a in list(monitor.amostras)],
                           "telas_medidas": list(usuarios.medidas)}
    (pasta / "bruto.json").write_text(json.dumps(bruto, ensure_ascii=False, default=str, indent=1),
                                      encoding="utf-8")
    with (pasta / "amostra.csv").open("w", newline="", encoding="utf-8-sig") as f:
        if res.amostra:
            c = csv.DictWriter(f, fieldnames=list(res.amostra[0]), delimiter=";")
            c.writeheader()
            c.writerows(res.amostra)
    try:
        texto = relatorio(res, args, usuarios)
    except Exception:  # noqa: BLE001 — sempre sai um resultado.md
        texto = ("# Teste de capacidade da varredura LGPD — relatório incompleto\n\n"
                 "A montagem do relatório falhou. As medições estão em `bruto.json` e "
                 "`amostra.csv`, na mesma pasta.\n\n"
                 + "".join(f"- {a}\n" for a in res.avisos)
                 + "\n```\n" + traceback.format_exc() + "```\n")
    arquivo = pasta / "resultado.md"
    arquivo.write_text(texto, encoding="utf-8")
    return arquivo


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--api", default="http://localhost:8000/api/v1")
    p.add_argument("--email", help="usuário com lgpd.varrer, ia.configurar e parametros.acessar")
    p.add_argument("--token", default=os.environ.get("GDA_TESTE_TOKEN"),
                   help="token de acesso pronto (no lugar de e-mail e senha); ou GDA_TESTE_TOKEN")
    p.add_argument("--amostra", type=int, default=30, help="recursos varridos na medição (padrão 30)")
    p.add_argument("--candidatos", type=int, default=90,
                   help="recursos sorteados para medir tamanho e escolher a amostra (padrão 90)")
    p.add_argument("--usuarios", type=int, default=7, help="usuários simulados nas telas (0 = pula)")
    p.add_argument("--base-s", type=int, default=90, help="segundos da linha de base sem varredura")
    p.add_argument("--fila", type=int, default=20, help="pedidos no teste de fila (0 = pula)")
    p.add_argument("--limite-mb", type=float, default=None,
                   help="limite de tamanho da varredura (padrão: parâmetro tamanho_maximo_recurso_lgpd_mb)")
    p.add_argument("--janela-h", type=float, default=3, help="horas entre a varredura noturna e o expediente")
    p.add_argument("--max-por-execucao", type=int, default=200, help="GDA_LGPD_VARREDURA_MAX_RECURSOS")
    p.add_argument("--limite-p95-s", type=float, default=2.0, help="p95 aceitável das telas (s)")
    p.add_argument("--intervalo-portal", type=float, default=1.0, help="pausa entre leituras de tamanho (s)")
    p.add_argument("--intervalo-monitor", type=float, default=3.0, help="intervalo do docker stats (s)")
    p.add_argument("--tempo-maximo-h", type=float, default=8, help="desiste da amostra depois disso")
    p.add_argument("--teto-recurso-min", type=float, default=0,
                   help="interrompe (reiniciando o worker) a varredura da amostra que passar disso, "
                        "para um arquivo lento não segurar a fila; 0 = sem teto (padrão)")
    p.add_argument("--aceitar-ia-simulada", action="store_true",
                   help="roda mesmo com a IA simulada (resultado só para ensaiar o teste)")
    p.add_argument("--semente", type=int, default=None, help="sorteio reproduzível")
    args = p.parse_args()
    random.seed(args.semente)
    if not (RAIZ / "docker-compose.yml").is_file():
        # na raiz do repositório há outro docker-compose.yml (CKAN local): nunca rodar nele
        sys.exit(f"Não achei o docker-compose.yml do sistema em {RAIZ}. O teste roda de dentro do "
                 "repositório, em testes/capacidade_lgpd/.")

    if not args.token and not args.email:
        p.error("informe --email (e a senha) ou --token")
    senha = None if args.token else (os.environ.get("GDA_TESTE_SENHA")
                                     or getpass.getpass(f"Senha de {args.email}: "))
    api = Api(args.api, args.email, senha, args.token)
    res = Resultado(inicio=agora().isoformat())

    cpus, mem, so = docker("info", "--format", "{{.NCPU}}|{{.MemTotal}}|{{.OperatingSystem}}").split("|")
    res.maquina = {"cpus": int(cpus), "ram_gib": round(int(mem) / 1024 ** 3, 1), "so": so}
    res.ia = verificar_ia(api)
    log(f"Máquina: {res.maquina}; IA: {res.ia}")
    if res.ia["simulada"] and not args.aceitar_ia_simulada:
        sys.exit("A varredura está com a IA simulada: os tempos não valeriam para o servidor. "
                 "Ligue o Ollama (README) ou rode com --aceitar-ia-simulada para ensaiar.")
    if args.limite_mb is None:
        params = {x["chave"]: x["valor"] for x in api.get("/parametros")}
        args.limite_mb = float(params.get("tamanho_maximo_recurso_lgpd_mb", 50))
    if api.get("/lgpd/varreduras", limite=1)["em_andamento"]:
        sys.exit("Há varreduras na fila ou em execução: espere terminar (ou cancele) antes do teste.")

    # a partir daqui o teste sempre deixa um relatório, mesmo se parar no meio
    pasta = Path(__file__).parent / "resultados" / datetime.now().strftime("%Y-%m-%d_%H%M")
    pasta.mkdir(parents=True, exist_ok=True)
    nomes = containers()
    monitor = Monitor({s: n for s, n in nomes.items() if s in ("api", "worker", "db", "ollama")},
                      args.intervalo_monitor)
    monitor.start()
    usuarios = Usuarios(api, args.usuarios)
    try:
        usados, todos = fase_amostra(api, args, res, monitor, usuarios, nomes)
        if args.fila:
            fase_fila(api, args, res, nomes, todos, usados)
    except BaseException as exc:
        res.avisos.append(f"O teste parou antes do fim: {type(exc).__name__}: {exc}")
        raise
    finally:
        usuarios.parar.set()
        monitor.parar.set()
        monitor.join(timeout=70)
        try:
            res.containers_depois = estado_containers(nomes)
        except Exception as exc:  # noqa: BLE001
            res.avisos.append(f"Não deu para ler o estado final dos containers: {exc}")
        res.memoria = {s: dict(zip(("pico_mem_mib", "pico_cpu"), monitor.pico(s), strict=True))
                       for s in monitor.servico_de.values()}
        arquivo = gravar(res, args, monitor, usuarios, pasta)
        log(f"Resultado: {arquivo}")


if __name__ == "__main__":
    main()
