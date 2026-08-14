"""
Recortes territoriais do mapa: bioma, estado e município.

As listas de UF e município mudam muito pouco, mas cada consulta ao GEE custa segundos -
por isso ficam em cache. O recorte em si é resolvido do mais específico para o mais amplo
(município > estado > bioma): não faz sentido cruzar os três, já que o município já está
contido no estado.
"""

import ee
from django.conf import settings
from django.core.cache import cache

from . import gee

CACHE_TTL = 60 * 60 * 24  # as malhas do IBGE são anuais; um dia de cache é conservador


def _uf_collection() -> ee.FeatureCollection:
    return ee.FeatureCollection(settings.GEE_UF_ASSET)


def _municipio_collection() -> ee.FeatureCollection:
    return ee.FeatureCollection(settings.GEE_MUNICIPIOS_ASSET)


def list_states() -> list[dict]:
    """[{'code': '15', 'uf': 'PA', 'name': 'Pará'}, ...] ordenado por nome."""
    cached = cache.get("firemap:states")
    if cached is not None:
        return cached

    gee.initialize()
    rows = _uf_collection().select(["CD_UF", "SIGLA_UF", "NM_UF"], None, False).getInfo()["features"]
    states = sorted(
        (
            {
                "code": str(f["properties"]["CD_UF"]),
                "uf": f["properties"]["SIGLA_UF"],
                "name": f["properties"]["NM_UF"],
            }
            for f in rows
        ),
        key=lambda s: s["name"],
    )
    cache.set("firemap:states", states, CACHE_TTL)
    return states


def list_municipalities(state_code: str) -> list[dict]:
    """Municípios de uma UF. Sem UF devolve vazio - 5.573 itens não cabem num select."""
    if not state_code:
        return []
    key = f"firemap:municipios:{state_code}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    gee.initialize()
    rows = (
        _municipio_collection()
        .filter(ee.Filter.eq("CD_UF", str(state_code)))
        .select(["CD_MUN", "NM_MUN"], None, False)
        .getInfo()["features"]
    )
    municipalities = sorted(
        ({"code": str(f["properties"]["CD_MUN"]), "name": f["properties"]["NM_MUN"]} for f in rows),
        key=lambda m: m["name"],
    )
    cache.set(key, municipalities, CACHE_TTL)
    return municipalities


def list_biomes() -> list[dict]:
    """Biomas, quando o asset estiver configurado. Vazio desabilita o filtro na interface."""
    asset = settings.GEE_BIOMAS_ASSET
    if not asset:
        return []
    cached = cache.get("firemap:biomes")
    if cached is not None:
        return cached

    gee.initialize()
    collection = ee.FeatureCollection(asset)
    name_field = settings.GEE_BIOMAS_NAME_FIELD
    rows = collection.select([name_field], None, False).getInfo()["features"]
    biomes = sorted({str(f["properties"][name_field]) for f in rows if f["properties"].get(name_field)})
    result = [{"code": b, "name": b} for b in biomes]
    cache.set("firemap:biomes", result, CACHE_TTL)
    return result


def geometry_bounds(geometry: ee.Geometry | None) -> list[list[float]] | None:
    """
    Caixa envolvente como [[sul, oeste], [norte, leste]], no formato que o Leaflet espera.

    Devolve None sem recorte - aí o mapa mantém o enquadramento do Brasil.
    """
    if geometry is None:
        return None
    ring = geometry.bounds().coordinates().get(0).getInfo()
    lons = [point[0] for point in ring]
    lats = [point[1] for point in ring]
    return [[min(lats), min(lons)], [max(lats), max(lons)]]


def resolve_geometry(*, biome: str = "", state: str = "", municipality: str = "") -> ee.Geometry | None:
    """
    Geometria de recorte para os filtros ativos, ou None para o Brasil inteiro.

    Do mais específico para o mais amplo - município já está dentro do estado, então
    não há por que interseccionar os dois.
    """
    if municipality:
        feature = _municipio_collection().filter(ee.Filter.eq("CD_MUN", str(municipality)))
        return feature.geometry()
    if state:
        feature = _uf_collection().filter(ee.Filter.eq("CD_UF", str(state)))
        return feature.geometry()
    if biome and settings.GEE_BIOMAS_ASSET:
        feature = ee.FeatureCollection(settings.GEE_BIOMAS_ASSET).filter(
            ee.Filter.eq(settings.GEE_BIOMAS_NAME_FIELD, biome)
        )
        return feature.geometry()
    return None
