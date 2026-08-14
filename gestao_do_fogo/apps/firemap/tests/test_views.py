"""
Testes do mapa do fogo.

O Earth Engine é sempre simulado: os testes precisam rodar sem rede e sem credencial,
e o que interessa aqui é o comportamento da aplicação (filtros, cache, degradação),
não a resposta do GEE.
"""

from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.firemap import catalog

TILE_URL = "https://earthengine.googleapis.com/v1/.../tiles/{z}/{x}/{y}"


def patch_gee(**overrides):
    """Simula a camada de acesso ao GEE usada pelas views."""
    defaults = {
        "apps.firemap.gee.is_available": mock.DEFAULT,
        "apps.firemap.gee.tile_url": mock.DEFAULT,
        "apps.firemap.territories.resolve_geometry": mock.DEFAULT,
        "apps.firemap.territories.geometry_bounds": mock.DEFAULT,
        "apps.firemap.territories.list_states": mock.DEFAULT,
        "apps.firemap.territories.list_biomes": mock.DEFAULT,
    }
    defaults.update(overrides)
    return defaults


class MapPageTest(TestCase):
    @mock.patch("apps.firemap.territories.list_biomes", return_value=[])
    @mock.patch("apps.firemap.territories.list_states", return_value=[{"code": "15", "uf": "PA", "name": "Pará"}])
    @mock.patch("apps.firemap.gee.is_available", return_value=True)
    def test_renders_filters_and_layers(self, *_):
        response = self.client.get(reverse("firemap:map"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mapa do fogo")
        self.assertContains(response, "Pará")
        for layer in catalog.LAYERS:
            self.assertContains(response, layer.name)

    @mock.patch("apps.firemap.gee.is_available", return_value=False)
    def test_warns_when_earth_engine_is_down(self, _):
        """Sem GEE a página ainda abre - com aviso, em vez de erro 500."""
        response = self.client.get(reverse("firemap:map"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Não foi possível conectar ao Google Earth Engine")

    @mock.patch("apps.firemap.territories.list_biomes", return_value=[])
    @mock.patch("apps.firemap.territories.list_states", return_value=[])
    @mock.patch("apps.firemap.gee.is_available", return_value=True)
    def test_biome_filter_disabled_without_asset(self, *_):
        response = self.client.get(reverse("firemap:map"))
        self.assertContains(response, "Disponível assim que o vetor de biomas")

    @mock.patch("apps.firemap.territories.list_biomes", return_value=[])
    @mock.patch("apps.firemap.territories.list_states", return_value=[])
    @mock.patch("apps.firemap.gee.is_available", return_value=True)
    def test_keeps_the_dom_contract_the_javascript_depends_on(self, *_):
        """
        O JS encontra tudo por seletor. Se um destes nomes sumir do template a página
        continua abrindo, mas o mapa fica mudo - por isso o contrato é testado aqui.
        """
        response = self.client.get(reverse("firemap:map"))
        for marker in ('id="firemap"', 'id="firemap-canvas"', "mapa-palco", "mapa-progresso", "data-legenda"):
            self.assertContains(response, marker)
        # só o recorte territorial tem `name`: o período é lido por data-ano/data-mes
        for name in ("bioma", "uf", "municipio"):
            self.assertContains(response, f'name="{name}" data-filter')
        for layer in catalog.LAYERS:
            self.assertContains(response, f'data-layer="{layer.id}"')
            self.assertContains(response, f'data-layer-status="{layer.id}"')

    @mock.patch("apps.firemap.territories.list_biomes", return_value=[])
    @mock.patch("apps.firemap.territories.list_states", return_value=[])
    @mock.patch("apps.firemap.gee.is_available", return_value=True)
    def test_period_lives_with_each_layer_not_in_the_filters_tab(self, *_):
        response = self.client.get(reverse("firemap:map"))
        html = response.content.decode()

        for layer in catalog.DATA_LAYERS:
            if layer.uses_year:
                self.assertContains(response, f'data-ano="{layer.id}"')
            if layer.uses_month:
                self.assertContains(response, f'data-mes="{layer.id}"')
        for layer in catalog.BOUNDARY_LAYERS:
            self.assertNotIn(f'data-ano="{layer.id}"', html)

        # o slider não pode ganhar `name`: o leitor de recorte usaria `.options[...]` nele
        self.assertNotIn('name="ano"', html)
        self.assertNotIn('name="mes"', html)

    @mock.patch("apps.firemap.territories.list_biomes", return_value=[])
    @mock.patch("apps.firemap.territories.list_states", return_value=[])
    @mock.patch("apps.firemap.gee.is_available", return_value=True)
    def test_right_panel_has_one_tab_per_data_layer(self, *_):
        response = self.client.get(reverse("firemap:map"))
        for layer in catalog.DATA_LAYERS:
            self.assertContains(response, f'data-stats="{layer.id}"')
        for layer in catalog.BOUNDARY_LAYERS:
            self.assertNotIn(f'data-stats="{layer.id}"', response.content.decode())


class BoundaryLayerTest(TestCase):
    def test_boundaries_ignore_territory_and_period(self):
        """
        Um contorno é igual em todo recorte e em todo ano. Se seguisse os filtros, cada
        mudança geraria um getMapId novo para uma imagem idêntica.
        """
        for layer in catalog.BOUNDARY_LAYERS:
            self.assertFalse(layer.uses_territory, layer.id)
            self.assertFalse(layer.uses_year, layer.id)
            self.assertFalse(layer.uses_month, layer.id)

    def test_boundaries_are_drawn_above_the_data(self):
        maior_dado = max(layer.z_index for layer in catalog.DATA_LAYERS)
        for layer in catalog.BOUNDARY_LAYERS:
            self.assertGreater(layer.z_index, maior_dado, layer.id)

    def test_hotspots_start_when_firms_starts(self):
        """Oferecer 1985 no slider do FIRMS renderia imagem vazia sem explicação."""
        self.assertEqual(catalog.LAYERS_BY_ID["focos_calor"].first_year, 2000)
        self.assertEqual(catalog.LAYERS_BY_ID["area_queimada"].first_year, catalog.FIRST_YEAR)


# `ee` também é simulado: montar uma ee.Image exige o cliente inicializado, e os testes
# não podem depender de rede nem de credencial.
@mock.patch("apps.firemap.catalog.ee")
@mock.patch("apps.firemap.territories.geometry_bounds", return_value=None)
@mock.patch("apps.firemap.territories.resolve_geometry", return_value=None)
@mock.patch("apps.firemap.gee.tile_url", return_value=TILE_URL)
class LayerTilesTest(TestCase):
    def test_returns_tile_url(self, tile_url, *_):
        response = self.client.get(reverse("firemap:layer_tiles", args=["area_queimada"]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["url"], TILE_URL)
        self.assertTrue(tile_url.called)

    def test_unknown_layer_is_404(self, *_):
        response = self.client.get(reverse("firemap:layer_tiles", args=["nao-existe"]))
        self.assertEqual(response.status_code, 404)

    def test_pending_layer_reports_why(self, *_):
        response = self.client.get(reverse("firemap:layer_tiles", args=["risco_potencial"]))
        self.assertEqual(response.status_code, 409)
        self.assertTrue(response.json()["pending"])

    @override_settings(GEE_FIRE_RISK_ASSET="projects/exemplo/assets/risco")
    def test_risk_layer_works_once_asset_is_set(self, *_):
        response = self.client.get(reverse("firemap:layer_tiles", args=["risco_potencial"]))
        self.assertEqual(response.status_code, 200)

    def test_filters_reach_the_geometry_resolver(self, _tile_url, resolve_geometry, _bounds, _ee):
        self.client.get(
            reverse("firemap:layer_tiles", args=["area_queimada"]),
            {"ano": "2020", "uf": "15", "municipio": "1500602", "bioma": "Amazônia"},
        )
        resolve_geometry.assert_called_with(biome="Amazônia", state="15", municipality="1500602")

    def test_invalid_year_falls_back_to_the_most_recent(self, tile_url, *_):
        response = self.client.get(reverse("firemap:layer_tiles", args=["area_queimada"]), {"ano": "banana"})
        self.assertEqual(response.status_code, 200)

    def test_gee_failure_returns_502_not_500(self, tile_url, *_):
        tile_url.side_effect = RuntimeError("band not found")
        response = self.client.get(reverse("firemap:layer_tiles", args=["area_queimada"]), {"ano": "1999"})
        self.assertEqual(response.status_code, 502)
        self.assertIn("band not found", response.json()["error"])

    def test_boundary_skips_the_geometry_and_sends_no_bounds(self, _tile_url, resolve_geometry, _bounds, _ee):
        """
        Um contorno não pode reenquadrar o mapa nem pagar por uma geometria que não usa.
        `bounds: null` é o que impede o cliente de desfazer o zoom do usuário.
        """
        response = self.client.get(reverse("firemap:layer_tiles", args=["limite_estado"]), {"uf": "15"})

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["bounds"])
        self.assertFalse(resolve_geometry.called)

    def test_payload_carries_the_stacking_decided_in_the_catalog(self, *_):
        response = self.client.get(reverse("firemap:layer_tiles", args=["limite_municipio"]))
        payload = response.json()
        self.assertEqual(payload["zIndex"], catalog.LAYERS_BY_ID["limite_municipio"].z_index)
        self.assertEqual(payload["opacity"], 1.0)


class MunicipalitiesTest(TestCase):
    @mock.patch("apps.firemap.territories.list_municipalities")
    def test_requires_a_state(self, list_municipalities):
        response = self.client.get(reverse("firemap:municipalities"))
        self.assertEqual(response.json()["municipios"], [])
        self.assertFalse(list_municipalities.called)

    @mock.patch(
        "apps.firemap.territories.list_municipalities",
        return_value=[{"code": "1500602", "name": "Altamira"}],
    )
    def test_lists_municipalities_of_a_state(self, _):
        response = self.client.get(reverse("firemap:municipalities"), {"uf": "15"})
        self.assertEqual(response.json()["municipios"][0]["name"], "Altamira")


class CatalogTest(TestCase):
    def test_year_range_matches_collection5(self):
        self.assertEqual(catalog.years()[0], catalog.LAST_YEAR)
        self.assertEqual(catalog.years()[-1], catalog.FIRST_YEAR)
        self.assertEqual(len(catalog.years()), 41)

    def test_risk_layer_is_pending_by_default(self):
        self.assertFalse(catalog.LAYERS_BY_ID["risco_potencial"].available)

    def test_other_layers_are_always_available(self):
        for layer_id in ("area_queimada", "monitor_fogo", "focos_calor"):
            self.assertTrue(catalog.LAYERS_BY_ID[layer_id].available, layer_id)
