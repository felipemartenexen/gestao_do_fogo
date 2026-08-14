"""
Leitura das planilhas de estatística de fogo.

Cada planilha é reconhecida pelas colunas que traz, não pelo nome do arquivo: assim o
usuário pode renomear ou reexportar sem quebrar a importação.

Duas decisões que valem explicação:

1. A UF verdadeira do município vem do sufixo de `Municipio` ("Barreiras (BA)"), não da
   coluna `UF`. A exportação do MapBiomas cruza bioma × UF × município, e municípios de
   fronteira aparecem sob a UF vizinha por imprecisão de borda - Boca do Acre (AM) aparece
   sob AC, por exemplo. Somar essas lascas no município certo mantém o total nacional e
   deixa o total por município completo.

2. `Cod_municipio` não é o código do IBGE (vem 35, 36, 37...), é um id interno do MapBiomas.
   O cruzamento é por (UF, nome normalizado), com uma tabela de apelidos para as sete
   grafias em que IBGE e MapBiomas divergem.
"""

import csv
import re
import unicodedata
from collections.abc import Iterator
from pathlib import Path

from apps.firemap.models import BurnedAreaAnnual, BurnedAreaMonthly, FireRisk

from . import territories

DATA_DIR = Path(__file__).resolve().parent / "data"

SUFIXO_UF = re.compile(r"\s*\(([A-Z]{2})\)\s*$")

# Grafias em que o MapBiomas/IPAM diverge da malha do IBGE. Chave: (UF, nome na planilha).
APELIDOS = {
    ("MG", "Barão de Monte Alto"): "Barão do Monte Alto",
    ("MT", "Santo Antônio do Leverger"): "Santo Antônio de Leverger",
    ("RN", "Açu"): "Assú",
    ("RN", "Arês"): "Arez",
    ("RR", "São Luiz"): "São Luiz do Anauá",
    ("RS", "Lagoa dos Patos"): 'Área Operacional "Lagoa dos Patos"',
    ("SE", "Gracho Cardoso"): "Graccho Cardoso",
}


def chave(nome: str) -> str:
    """Nome sem acento, sem pontuação e em minúsculas - IBGE e MapBiomas divergem nesses detalhes."""
    sem_acento = "".join(c for c in unicodedata.normalize("NFD", nome) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "", sem_acento.lower())


class Referencia:
    """Malha do IBGE em memória, para traduzir nome em código uma única vez por importação."""

    def __init__(self) -> None:
        self.uf_por_sigla: dict[str, str] = {}
        self.municipios: dict[tuple[str, str], tuple[str, str]] = {}
        for estado in territories.list_states():
            self.uf_por_sigla[estado["uf"]] = estado["code"]
            for municipio in territories.list_municipalities(estado["code"]):
                self.municipios[(estado["uf"], chave(municipio["name"]))] = (municipio["code"], municipio["name"])

    def municipio(self, sigla: str, nome: str) -> tuple[str, str] | None:
        nome = APELIDOS.get((sigla, nome), nome)
        return self.municipios.get((sigla, chave(nome)))


def _numero(valor: str) -> float:
    """Converte '11854.54143' e '8.81E-04'. Vírgula decimal também aparece em reexportações."""
    valor = (valor or "").strip().replace(" ", "")
    if not valor:
        return 0.0
    if "," in valor and "." not in valor:
        valor = valor.replace(",", ".")
    try:
        return float(valor)
    except ValueError:
        return 0.0


# --- leitores por planilha -----------------------------------------------------


def ler_area_anual(caminho: Path, ref: Referencia, avisos: list[str]) -> Iterator[BurnedAreaAnnual]:
    with caminho.open(encoding="utf-8-sig", newline="") as fh:
        for linha in csv.DictReader(fh):
            bruto = linha["Municipio"].strip()
            achado = SUFIXO_UF.search(bruto)
            if not achado:
                avisos.append(f"município sem sufixo de UF: {bruto!r}")
                continue
            sigla = achado.group(1)
            nome = SUFIXO_UF.sub("", bruto)
            municipio = ref.municipio(sigla, nome)
            if municipio is None:
                avisos.append(f"município fora da malha do IBGE: {sigla} {nome!r}")
                continue
            yield BurnedAreaAnnual(
                year=int(linha["Ano"]),
                biome=linha["Bioma"].strip(),
                state_code=ref.uf_por_sigla[sigla],
                state_uf=sigla,
                municipality_code=municipio[0],
                municipality_name=municipio[1],
                area_ha=_numero(linha["Área ha"]),
            )


def ler_area_mensal(caminho: Path, ref: Referencia, avisos: list[str]) -> Iterator[BurnedAreaMonthly]:
    with caminho.open(encoding="utf-8-sig", newline="") as fh:
        for linha in csv.DictReader(fh):
            sigla = linha["UF"].strip()
            if sigla not in ref.uf_por_sigla:
                avisos.append(f"UF desconhecida na planilha mensal: {sigla!r}")
                continue
            yield BurnedAreaMonthly(
                year=int(linha["Ano"]),
                month=int(linha["Mês"]),
                biome=linha["Bioma"].strip(),
                state_code=ref.uf_por_sigla[sigla],
                state_uf=sigla,
                cover_origin=linha["Nível 0"].strip(),
                cover_class=linha["Nível 1"].strip(),
                cover_detail=linha["Nível 2"].strip(),
                area_ha=_numero(linha["Área ha"]),
            )


def ler_risco(caminho: Path, ref: Referencia, avisos: list[str]) -> Iterator[FireRisk]:
    # a planilha não tem coluna de ano; a temporada vem do nome do arquivo ("...-2026.csv")
    achado = re.search(r"(20\d{2})", caminho.stem)
    temporada = int(achado.group(1)) if achado else 0
    if not temporada:
        avisos.append(f"não foi possível ler a temporada do nome do arquivo: {caminho.name}")

    with caminho.open(encoding="utf-8-sig", newline="") as fh:
        for linha in csv.DictReader(fh):
            sigla = linha["UF"].strip()
            nome = linha["Município"].strip()
            municipio = ref.municipio(sigla, nome)
            if municipio is None:
                avisos.append(f"município fora da malha do IBGE: {sigla} {nome!r}")
                continue
            yield FireRisk(
                season=temporada,
                biome=linha["Bioma"].strip(),
                state_code=ref.uf_por_sigla[sigla],
                state_uf=sigla,
                municipality_code=municipio[0],
                municipality_name=municipio[1],
                tenure=linha["Fundiaria n1"].strip(),
                jurisdiction=linha["Fundiaria Jurisdição"].strip(),
                risk_class=linha["Classes de risco de fogo"].strip(),
                area_ha=_numero(linha["Área ha"]),
            )


# --- reconhecimento das planilhas ----------------------------------------------


class Planilha:
    def __init__(self, nome: str, modelo, colunas: set[str], leitor) -> None:
        self.nome = nome
        self.modelo = modelo
        self.colunas = colunas
        self.leitor = leitor


PLANILHAS = [
    Planilha(
        "área queimada anual",
        BurnedAreaAnnual,
        {"Ano", "Bioma", "Municipio", "Área ha"},
        ler_area_anual,
    ),
    Planilha(
        "área queimada mensal por cobertura",
        BurnedAreaMonthly,
        {"Ano", "Mês", "Bioma", "UF", "Nível 1", "Área ha"},
        ler_area_mensal,
    ),
    Planilha(
        "risco de fogo",
        FireRisk,
        {"Bioma", "UF", "Município", "Classes de risco de fogo", "Área ha"},
        ler_risco,
    ),
]


def reconhecer(caminho: Path) -> Planilha | None:
    """Casa o arquivo com uma planilha conhecida pelo cabeçalho, não pelo nome."""
    with caminho.open(encoding="utf-8-sig", newline="") as fh:
        cabecalho = next(csv.reader(fh), [])
    presentes = {c.strip() for c in cabecalho}
    for planilha in PLANILHAS:
        if planilha.colunas <= presentes:
            return planilha
    return None
