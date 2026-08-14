import hashlib
import logging

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from . import gee, stats, territories
from .catalog import BOUNDARY_LAYERS, DATA_LAYERS, LAST_YEAR, LAYERS, LAYERS_BY_ID, MONTHS, years

logger = logging.getLogger("gestao_do_fogo.firemap")


def _int_or_none(value: str | None) -> int | None:
    try:
        return int(value)
    except TypeError, ValueError:
        return None


def _territory(request) -> dict:
    """Recorte territorial pedido. É o mesmo para todas as camadas - só o período é por camada."""
    return {
        "biome": (request.GET.get("bioma") or "").strip(),
        "state": (request.GET.get("uf") or "").strip(),
        "municipality": (request.GET.get("municipio") or "").strip(),
    }


def map_page(request) -> HttpResponse:
    available = gee.is_available()
    context = {
        "page_title": "Mapa do fogo",
        "page_description": "Área queimada, monitor mensal, focos de calor e risco no território brasileiro.",
        "active_tab": "firemap",
        "layers": LAYERS,
        "data_layers": DATA_LAYERS,
        "boundary_layers": BOUNDARY_LAYERS,
        "years": years(),
        "last_year": LAST_YEAR,
        "months": MONTHS,
        "biomes": territories.list_biomes() if available else [],
        "states": territories.list_states() if available else [],
        "gee_available": available,
    }
    return render(request, "firemap/map.html", context)


@require_GET
def layer_tiles(request, layer_id: str) -> JsonResponse:
    """
    URL de tiles de uma camada, já recortada pelos filtros.

    O resultado fica em cache porque `getMapId` leva alguns segundos: sem isso, cada
    troca de ano no seletor faria o usuário esperar de novo pela mesma resposta.
    """
    layer = LAYERS_BY_ID.get(layer_id)
    if layer is None:
        return JsonResponse({"error": "Camada desconhecida."}, status=404)
    if not layer.available:
        return JsonResponse({"error": layer.pending_reason, "pending": True}, status=409)

    territory = _territory(request)
    filters = {
        "year": _int_or_none(request.GET.get("ano")) or years()[0],
        "month": _int_or_none(request.GET.get("mes")),
        "biome": territory["biome"],
        "state": territory["state"],
        "municipality": territory["municipality"],
    }

    # A chave só carrega as dimensões que a camada realmente usa. Um contorno é igual em
    # todo recorte e em todo ano: com as dimensões inteiras na chave, ele seria recalculado
    # a cada mudança de filtro sem que a imagem mudasse.
    dimensoes: list[str] = [layer_id]
    if layer.uses_year:
        dimensoes.append(str(filters["year"]))
    if layer.uses_month:
        dimensoes.append(str(filters["month"]))
    if layer.uses_territory:
        dimensoes.extend([territory["biome"], territory["state"], territory["municipality"]])

    cache_key = f"firemap:tiles:{hashlib.sha1(':'.join(dimensoes).encode()).hexdigest()}"
    cached = cache.get(cache_key)
    if cached:
        return JsonResponse({**cached, "cached": True})

    try:
        geometry = (
            territories.resolve_geometry(
                biome=territory["biome"],
                state=territory["state"],
                municipality=territory["municipality"],
            )
            if layer.uses_territory
            else None
        )
        image, vis_params = layer.build(filters, geometry)
        payload = {
            "id": layer.id,
            "name": layer.name,
            "url": gee.tile_url(image, vis_params),
            "attribution": layer.source,
            "zIndex": layer.z_index,
            "opacity": layer.opacity,
            # limites do recorte, para o mapa enquadrar o território escolhido; uma camada
            # que ignora o recorte manda null e o cliente não mexe no enquadramento
            "bounds": territories.geometry_bounds(geometry) if layer.uses_territory else None,
        }
    except gee.GEEUnavailable as exc:
        logger.warning("Earth Engine indisponível: %s", exc)
        return JsonResponse({"error": "Earth Engine indisponível no momento."}, status=503)
    except Exception as exc:  # noqa: BLE001 - o SDK levanta tipos variados
        logger.exception("Falha ao gerar tiles da camada %s", layer_id)
        return JsonResponse({"error": f"Não foi possível gerar a camada: {exc}"}, status=502)

    cache.set(cache_key, payload, settings.GEE_TILE_CACHE_SECONDS)
    return JsonResponse({**payload, "cached": False})


@require_GET
def layer_stats(request, layer_id: str) -> JsonResponse:
    """
    Estatísticas de uma camada para o recorte atual.

    Vem das planilhas importadas, não do Earth Engine: o mesmo número que a rede publica
    nos relatórios, e em milissegundos em vez de dezenas de segundos.
    """
    calcular = stats.CALCULADORAS.get(layer_id)
    if calcular is None:
        return JsonResponse({"error": "Camada sem estatística."}, status=404)

    territory = _territory(request)
    year = _int_or_none(request.GET.get("ano")) or years()[0]
    try:
        return JsonResponse(calcular(year=year, **territory))
    except Exception:  # noqa: BLE001
        logger.exception("Falha ao calcular estatística da camada %s", layer_id)
        return JsonResponse({"error": "Não foi possível calcular a estatística."}, status=500)


@require_GET
def municipalities(request) -> JsonResponse:
    """Municípios de uma UF, para preencher o segundo select em cascata."""
    state = (request.GET.get("uf") or "").strip()
    if not state:
        return JsonResponse({"municipios": []})
    try:
        return JsonResponse({"municipios": territories.list_municipalities(state)})
    except gee.GEEUnavailable:
        return JsonResponse({"municipios": [], "error": "Earth Engine indisponível."}, status=503)
    except Exception:  # noqa: BLE001
        logger.exception("Falha ao listar municípios da UF %s", state)
        return JsonResponse({"municipios": [], "error": "Não foi possível listar os municípios."}, status=502)
