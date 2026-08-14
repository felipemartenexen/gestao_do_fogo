"""
Testes das estatísticas lidas das planilhas.

Os dados são montados à mão: as planilhas reais têm 425 mil linhas e não podem entrar no
teste, mas as regras que importam - recorte mais específico primeiro, média que exclui o
ano analisado, mensal que cai para o estado - são independentes do volume.
"""

from django.test import TestCase
from django.urls import reverse

from apps.firemap import stats
from apps.firemap.models import BurnedAreaAnnual, BurnedAreaMonthly, FireRisk


def area(**kwargs) -> BurnedAreaAnnual:
    padrao = {
        "year": 2024,
        "biome": "Amazônia",
        "state_code": "15",
        "state_uf": "PA",
        "municipality_code": "1500602",
        "municipality_name": "Altamira",
        "area_ha": 100.0,
    }
    return BurnedAreaAnnual.objects.create(**{**padrao, **kwargs})


class AreaQueimadaTest(TestCase):
    def test_soma_o_recorte_mais_especifico(self):
        area(area_ha=10)
        area(area_ha=5)  # mesma chave: a planilha traz várias linhas por município/ano
        area(municipality_code="1501402", municipality_name="Belém", area_ha=90)

        municipio = stats.area_queimada(biome="", state="15", municipality="1500602", year=2024)
        estado = stats.area_queimada(biome="", state="15", municipality="", year=2024)

        self.assertEqual(municipio["total_ha"], 15)
        self.assertEqual(municipio["escopo"], "municipio")
        self.assertEqual(estado["total_ha"], 105)

    def test_municipio_vence_estado_e_bioma(self):
        """Mesma regra do mapa: o recorte mais específico manda, sem cruzar os três."""
        area(area_ha=10)
        resultado = stats.area_queimada(biome="Cerrado", state="52", municipality="1500602", year=2024)
        self.assertEqual(resultado["total_ha"], 10)

    def test_media_historica_ignora_o_ano_analisado(self):
        """Incluir o ano na própria média achataria a anomalia justamente nos anos extremos."""
        area(year=2022, area_ha=100)
        area(year=2023, area_ha=100)
        area(year=2024, area_ha=300)

        resultado = stats.area_queimada(biome="", state="15", municipality="", year=2024)

        self.assertEqual(resultado["media_ha"], 100)
        self.assertAlmostEqual(resultado["anomalia_pct"], 200)

    def test_ranking_compara_municipios_do_mesmo_estado(self):
        area(municipality_code="1500602", municipality_name="Altamira", area_ha=10)
        area(municipality_code="1501402", municipality_name="Belém", area_ha=90)

        resultado = stats.area_queimada(biome="", state="15", municipality="1500602", year=2024)

        self.assertEqual(resultado["ranking"], {"posicao": 2, "de": 2})

    def test_recorte_sem_dado_avisa_em_vez_de_zerar(self):
        resultado = stats.area_queimada(biome="", state="99", municipality="", year=2024)
        self.assertFalse(resultado["disponivel"])
        self.assertIn("Sem dado", resultado["motivo"])


class MonitorTest(TestCase):
    def setUp(self):
        BurnedAreaMonthly.objects.create(
            year=2024,
            month=9,
            biome="Amazônia",
            state_code="15",
            state_uf="PA",
            cover_origin="Natural",
            cover_class="Floresta",
            cover_detail="Formação Florestal",
            area_ha=80.0,
        )
        BurnedAreaMonthly.objects.create(
            year=2024,
            month=10,
            biome="Amazônia",
            state_code="15",
            state_uf="PA",
            cover_origin="Antrópico",
            cover_class="Agropecuária",
            cover_detail="Pastagem",
            area_ha=20.0,
        )

    def test_municipio_cai_para_o_estado_e_avisa(self):
        """A planilha mensal para na UF. Devolver vazio esconderia a sazonalidade estadual."""
        resultado = stats.monitor_fogo(biome="", state="15", municipality="1500602", year=2024)

        self.assertTrue(resultado["disponivel"])
        self.assertEqual(resultado["escopo"], "estado")
        self.assertTrue(resultado["rebaixado"])
        self.assertEqual(resultado["total_ha"], 100)

    def test_devolve_os_doze_meses_mesmo_sem_dado(self):
        resultado = stats.monitor_fogo(biome="", state="15", municipality="", year=2024)
        self.assertEqual(len(resultado["meses"]), 12)
        self.assertEqual(resultado["meses"][0]["ha"], 0.0)

    def test_cobertura_ordenada_da_maior_para_a_menor(self):
        resultado = stats.monitor_fogo(biome="", state="15", municipality="", year=2024)
        self.assertEqual([c["classe"] for c in resultado["cobertura"]], ["Floresta", "Agropecuária"])


class RiscoTest(TestCase):
    def setUp(self):
        FireRisk.objects.create(
            season=2026,
            biome="Amazônia",
            state_code="15",
            state_uf="PA",
            municipality_code="1500602",
            municipality_name="Altamira",
            tenure="Terra Indígena",
            jurisdiction="Federal",
            risk_class="VQ",
            area_ha=40.0,
        )

    def test_traz_a_temporada_e_a_malha_fundiaria(self):
        resultado = stats.risco_potencial(biome="", state="15", municipality="")
        self.assertEqual(resultado["temporada"], 2026)
        self.assertEqual(resultado["fundiaria"][0]["categoria"], "Terra Indígena")

    def test_fora_da_cobertura_do_ipam_explica_o_motivo(self):
        resultado = stats.risco_potencial(biome="", state="35", municipality="")
        self.assertFalse(resultado["disponivel"])
        self.assertIn("IPAM", resultado["motivo"])


class FocosTest(TestCase):
    def test_sem_planilha_consolidada(self):
        self.assertFalse(stats.focos_calor()["disponivel"])


class LayerStatsViewTest(TestCase):
    def test_responde_json_do_recorte(self):
        area(area_ha=42)
        resposta = self.client.get(reverse("firemap:layer_stats", args=["area_queimada"]), {"uf": "15", "ano": "2024"})
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()["total_ha"], 42)

    def test_camada_sem_estatistica_e_404(self):
        resposta = self.client.get(reverse("firemap:layer_stats", args=["limite_estado"]))
        self.assertEqual(resposta.status_code, 404)
