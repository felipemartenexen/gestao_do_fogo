"""
Resolução de coordenadas para os locais informados pelos pesquisadores.

A tabela `data/locations.json` é o cache versionado no repositório: ela cobre todos os
municípios que vieram do formulário de mapeamento, então a importação roda offline.
Quando alguém cadastra uma cidade nova pelo site, o cache erra e a busca online (Nominatim)
preenche a lacuna - por isso o geocoding fica num comando separado, e não no request.
"""

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
LOCATIONS_PATH = DATA_DIR / "locations.json"

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "gestao-do-fogo/1.0 (contato@mapiaeng.com)"
# a política de uso do Nominatim pede no máximo 1 requisição por segundo
REQUEST_INTERVAL_SECONDS = 1.1


def cache_key(city: str, state: str, country: str) -> str:
    return f"{city}|{state}|{country}"


def load_cache() -> dict:
    if not LOCATIONS_PATH.exists():
        return {}
    return json.loads(LOCATIONS_PATH.read_text(encoding="utf-8"))


def save_cache(cache: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOCATIONS_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


def lookup(city: str, state: str, country: str, cache: dict | None = None) -> tuple[float, float] | None:
    """Consulta só o cache local. Devolve None quando o local ainda não foi geocodificado."""
    cache = load_cache() if cache is None else cache
    hit = cache.get(cache_key(city, state, country))
    return (hit["lat"], hit["lon"]) if hit else None


def build_query(city: str, state: str, country: str) -> str:
    from .models import UF_CHOICES

    state_name = dict(UF_CHOICES).get(state, state)
    return ", ".join(part for part in (city, state_name, country or "Brasil") if part)


def geocode_online(city: str, state: str, country: str) -> tuple[float, float] | None:
    """Consulta o Nominatim. Devolve None quando não há resultado."""
    query = build_query(city, state, country)
    url = f"{NOMINATIM_URL}?{urllib.parse.urlencode({'q': query, 'format': 'json', 'limit': 1})}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        results = json.load(response)
    if not results:
        return None
    return float(results[0]["lat"]), float(results[0]["lon"])


def resolve(city: str, state: str, country: str, *, allow_online: bool = False, cache: dict | None = None):
    """
    Cache primeiro; opcionalmente cai para a busca online e grava o resultado no cache.

    Devolve (coordenadas | None, cache_foi_alterado).
    """
    if not city and not state:
        return None, False
    cache = load_cache() if cache is None else cache
    key = cache_key(city, state, country)
    if key in cache:
        entry = cache[key]
        return (entry["lat"], entry["lon"]), False
    if not allow_online:
        return None, False

    time.sleep(REQUEST_INTERVAL_SECONDS)
    coordinates = geocode_online(city, state, country)
    if coordinates is None:
        return None, False
    cache[key] = {"lat": coordinates[0], "lon": coordinates[1], "query": build_query(city, state, country)}
    return coordinates, True
