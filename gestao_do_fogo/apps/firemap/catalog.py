"""
Catálogo das camadas do mapa do fogo.

Cada camada sabe construir sua própria imagem no Earth Engine a partir dos filtros
(ano, mês e recorte territorial). Manter isso como dado - e não espalhado em ifs nas
views - deixa claro de onde vem cada número e permite ligar uma camada nova mexendo
só neste arquivo.

Paleta: a rampa de fogo do design system (assets/styles/app/tailwind/design-system.css).
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import ee
from django.conf import settings

# rampa sequencial de fogo do design system
FOGO_1 = "FDEBD7"
FOGO_2 = "F6C288"
FOGO_3 = "EE8F3B"
FOGO_4 = "D95B1E"
FOGO_5 = "A32B1B"
FOGO_6 = "6E1212"

RAMPA_FOGO = [FOGO_1, FOGO_2, FOGO_3, FOGO_4, FOGO_5, FOGO_6]

# Coleção 5 do MapBiomas Fogo: uma banda por ano, burned_area_YYYY
COLLECTION5_ANNUAL = (
    "projects/mapbiomas-public/assets/brazil/fire/collection5/mapbiomas_fire_collection5_annual_burned_v1"
)
COLLECTION5_FREQUENCY = (
    "projects/mapbiomas-public/assets/brazil/fire/collection5/mapbiomas_fire_collection5_fire_frequency_v1"
)
FIRE_MONITOR = "projects/mapbiomas-public/assets/brazil/fire/monitor/mapbiomas_fire_monthly_burned_v1"
FIRMS = "FIRMS"

# limites da série anual da Coleção 5 (conferidos no asset: 41 bandas)
FIRST_YEAR = 1985
LAST_YEAR = 2025

MONTHS = [
    (1, "Janeiro"),
    (2, "Fevereiro"),
    (3, "Março"),
    (4, "Abril"),
    (5, "Maio"),
    (6, "Junho"),
    (7, "Julho"),
    (8, "Agosto"),
    (9, "Setembro"),
    (10, "Outubro"),
    (11, "Novembro"),
    (12, "Dezembro"),
]


@dataclass(frozen=True)
class Legend:
    """Legenda exibida na interface. `items` são pares (cor, rótulo)."""

    items: list[tuple[str, str]]
    note: str = ""


@dataclass(frozen=True)
class Layer:
    id: str
    name: str
    summary: str
    source: str
    build: Callable[[dict, ee.Geometry | None], tuple[Any, dict]]
    legend: Legend
    kind: str = "dado"  # "dado" (fogo, tem estatística) | "limite" (contorno de referência)
    short_name: str = ""  # rótulo curto do rail de 64px; vazio cai no `name`
    uses_year: bool = True
    uses_month: bool = False
    # Um contorno é igual em qualquer recorte. Recortá-lo geraria um getMapId por combinação
    # de filtro e jogaria fora o cache de tiles do GEE, que é o que o torna barato.
    uses_territory: bool = True
    first_year: int = FIRST_YEAR
    z_index: int = 20
    opacity: float = 0.85
    setting_asset: str = ""  # quando preenchido, a camada só existe se o setting tiver valor
    extra: dict = field(default_factory=dict)

    @property
    def available(self) -> bool:
        return not self.setting_asset or bool(getattr(settings, self.setting_asset, ""))

    @property
    def pending_reason(self) -> str:
        # derivado do campo: com mais de uma camada condicional, um texto fixo mentiria
        if self.available:
            return ""
        return f"Aguardando o asset ser informado em {self.setting_asset}."

    @property
    def label(self) -> str:
        return self.short_name or self.name

    @property
    def years(self) -> list[int]:
        return list(range(LAST_YEAR, self.first_year - 1, -1))


# --- construtores de imagem ---------------------------------------------------


def _clip(image, geometry: ee.Geometry | None):
    return image.clip(geometry) if geometry is not None else image


def build_annual_burned(filters: dict, geometry) -> tuple[Any, dict]:
    """Área queimada anual da Coleção 5. A banda é 0/1, então basta mascarar o zero."""
    year = filters["year"]
    image = ee.Image(COLLECTION5_ANNUAL).select(f"burned_area_{year}").selfMask()
    return _clip(image, geometry), {"min": 1, "max": 1, "palette": [FOGO_5]}


def build_fire_monitor(filters: dict, geometry) -> tuple[Any, dict]:
    """
    Monitor mensal do fogo.

    Sem mês escolhido, mostra o acumulado do ano (mosaico de todos os meses disponíveis);
    com mês, mostra só aquele mês. A banda FireMonth guarda o mês da queima.
    """
    year, month = filters["year"], filters.get("month")
    collection = ee.ImageCollection(FIRE_MONITOR).filter(ee.Filter.calendarRange(year, year, "year"))
    if month:
        collection = collection.filter(ee.Filter.calendarRange(month, month, "month"))
    image = collection.select("FireMonth").max().selfMask()
    return _clip(image, geometry), {"min": 1, "max": 12, "palette": RAMPA_FOGO}


def build_hotspots(filters: dict, geometry) -> tuple[Any, dict]:
    """
    Focos de calor do FIRMS (VIIRS/MODIS, NASA).

    Sem mês, cobre o ano inteiro; com mês, só aquele mês. T21 é a temperatura de brilho -
    quanto maior, mais intenso o foco.
    """
    year, month = filters["year"], filters.get("month")
    if month:
        start = ee.Date.fromYMD(year, month, 1)
        end = start.advance(1, "month")
    else:
        start = ee.Date.fromYMD(year, 1, 1)
        end = ee.Date.fromYMD(year, 12, 31)
    image = ee.ImageCollection(FIRMS).filterDate(start, end).select("T21").max().selfMask()
    return _clip(image, geometry), {"min": 325, "max": 400, "palette": RAMPA_FOGO}


def build_fire_risk(filters: dict, geometry) -> tuple[Any, dict]:
    """Risco potencial, a partir do asset informado em GEE_FIRE_RISK_ASSET."""
    asset = settings.GEE_FIRE_RISK_ASSET
    image = ee.Image(asset).selfMask()
    return _clip(image, geometry), {"min": 0, "max": 5, "palette": RAMPA_FOGO}


# --- limites territoriais ------------------------------------------------------
# Só tokens estáveis nos dois temas: o contorno é desenhado sobre o mapa base, que não
# muda com o tema, então uma cor que vira no escuro trocaria de tom sem o fundo mudar.
LIMITE_BIOMA = "0F3B26"  # verde-900
LIMITE_ESTADO = "1B5E3C"  # verde-700
LIMITE_MUNICIPIO = "64615C"  # tinta neutra: no adensamento municipal, verde vira mancha


def _contorno(collection, color: str, width: int) -> tuple[Any, dict]:
    """
    Contorno vetorial como tiles.

    `style()` em vez de `paint()`: o Earth Engine guarda o resultado de `style()` em cache
    (o segundo pedido do mesmo tile cai de ~18s para menos de 1s), e devolve RGBA pronto -
    por isso `vis_params` vai vazio.
    """
    return collection.style(color=f"{color}FF", fillColor="00000000", width=width), {}


def build_limite_bioma(filters: dict, geometry) -> tuple[Any, dict]:
    return _contorno(ee.FeatureCollection(settings.GEE_BIOMAS_ASSET), LIMITE_BIOMA, 2)


def build_limite_estado(filters: dict, geometry) -> tuple[Any, dict]:
    return _contorno(ee.FeatureCollection(settings.GEE_UF_ASSET), LIMITE_ESTADO, 2)


def build_limite_municipio(filters: dict, geometry) -> tuple[Any, dict]:
    return _contorno(ee.FeatureCollection(settings.GEE_MUNICIPIOS_ASSET), LIMITE_MUNICIPIO, 1)


# --- catálogo ------------------------------------------------------------------

LAYERS: list[Layer] = [
    Layer(
        id="area_queimada",
        name="Área queimada · Coleção 5",
        short_name="Área queimada",
        summary="Cicatrizes de fogo mapeadas por ano, de 1985 a 2025.",
        source="MapBiomas Fogo, Coleção 5",
        build=build_annual_burned,
        z_index=20,
        legend=Legend(items=[(FOGO_5, "Área queimada no ano")]),
    ),
    Layer(
        id="monitor_fogo",
        name="Monitor do fogo",
        short_name="Monitor",
        summary="Acompanhamento mensal das áreas queimadas, atualizado ao longo do ano.",
        source="MapBiomas Fogo · Monitor mensal",
        build=build_fire_monitor,
        uses_month=True,
        z_index=30,
        legend=Legend(
            items=[(FOGO_1, "Início do ano"), (FOGO_3, "Meio do ano"), (FOGO_6, "Fim do ano")],
            note="A cor indica o mês em que a área queimou.",
        ),
    ),
    Layer(
        id="focos_calor",
        name="Focos de calor",
        short_name="Focos",
        summary="Detecções de fogo ativo por satélite, com a temperatura de brilho.",
        source="NASA FIRMS (VIIRS/MODIS)",
        build=build_hotspots,
        uses_month=True,
        # o FIRMS no Earth Engine começa em novembro de 2000; oferecer 1985 daria imagem vazia
        first_year=2000,
        z_index=40,
        legend=Legend(
            items=[(FOGO_2, "325 K"), (FOGO_4, "360 K"), (FOGO_6, "400 K ou mais")],
            note="Temperatura de brilho do foco: quanto maior, mais intenso.",
        ),
    ),
    Layer(
        id="risco_potencial",
        name="Risco potencial",
        short_name="Risco",
        summary="Risco potencial de fogo no território.",
        source="A definir",
        build=build_fire_risk,
        uses_year=False,
        z_index=10,
        setting_asset="GEE_FIRE_RISK_ASSET",
        legend=Legend(items=[(FOGO_1, "Baixo"), (FOGO_3, "Médio"), (FOGO_6, "Alto")]),
    ),
    Layer(
        id="limite_bioma",
        name="Biomas",
        summary="Divisa dos seis biomas brasileiros.",
        source="IBGE · Biomas 1:250.000",
        build=build_limite_bioma,
        kind="limite",
        uses_year=False,
        uses_territory=False,
        z_index=60,
        opacity=1.0,
        legend=Legend(items=[(LIMITE_BIOMA, "Divisa de bioma")]),
    ),
    Layer(
        id="limite_estado",
        name="Estados",
        summary="Divisa das 27 unidades da federação.",
        source="IBGE · Malha municipal 2025",
        build=build_limite_estado,
        kind="limite",
        uses_year=False,
        uses_territory=False,
        z_index=70,
        opacity=1.0,
        legend=Legend(items=[(LIMITE_ESTADO, "Divisa estadual")]),
    ),
    Layer(
        id="limite_municipio",
        name="Municípios",
        summary="Divisa dos 5.573 municípios. Legível a partir do zoom estadual.",
        source="IBGE · Malha municipal 2025",
        build=build_limite_municipio,
        kind="limite",
        uses_year=False,
        uses_territory=False,
        z_index=80,
        opacity=1.0,
        legend=Legend(items=[(LIMITE_MUNICIPIO, "Divisa municipal")]),
    ),
]

LAYERS_BY_ID = {layer.id: layer for layer in LAYERS}
DATA_LAYERS = [layer for layer in LAYERS if layer.kind == "dado"]
BOUNDARY_LAYERS = [layer for layer in LAYERS if layer.kind == "limite"]


def years() -> list[int]:
    return list(range(LAST_YEAR, FIRST_YEAR - 1, -1))
