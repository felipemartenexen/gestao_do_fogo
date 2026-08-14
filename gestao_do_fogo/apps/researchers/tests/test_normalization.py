from django.test import SimpleTestCase

from apps.researchers import normalization as N
from apps.researchers.models import EducationLevel, Sector


class NormalizeUfTest(SimpleTestCase):
    def test_accepts_code_and_name(self):
        self.assertEqual(N.normalize_uf("SP"), "SP")
        self.assertEqual(N.normalize_uf("São Paulo"), "SP")
        self.assertEqual(N.normalize_uf("sao paulo"), "SP")

    def test_brasilia_maps_to_df(self):
        for value in ("DF", "Distrito Federal", "DISTRITO FEDERAL", "Brasília"):
            self.assertEqual(N.normalize_uf(value), "DF", value)

    def test_multi_state_answer_keeps_the_first(self):
        self.assertEqual(N.normalize_uf("Mato Grosso, Mato Grosso do Sul"), "MT")
        self.assertEqual(N.normalize_uf("SP; MG"), "SP")
        self.assertEqual(N.normalize_uf("Acre e SP"), "AC")

    def test_state_embedded_in_longer_text(self):
        self.assertEqual(N.normalize_uf("Todos os estados do Brasil mas sou lotado em Goiás"), "GO")

    def test_non_brazilian_answers_return_empty(self):
        for value in ("Norfolk, UK", "Ohio", "Itália", "nacional", "-", "NA", ""):
            self.assertEqual(N.normalize_uf(value), "", value)


class NormalizeCountryTest(SimpleTestCase):
    def test_variants_collapse_to_brasil(self):
        for value in ("Brasil", "BRASIL", "brasil", "Brazil", "Brasil/SP", "Bras", "Brasil⁷", ""):
            self.assertEqual(N.normalize_country(value), "Brasil", value)

    def test_state_typed_into_country_field_is_brasil(self):
        self.assertEqual(N.normalize_country("São Paulo"), "Brasil")

    def test_foreign_countries(self):
        self.assertEqual(N.normalize_country("United Kingdom"), "Reino Unido")
        self.assertEqual(N.normalize_country("Inglaterra"), "Reino Unido")
        self.assertEqual(N.normalize_country("EUA"), "Estados Unidos")


class NormalizeCityTest(SimpleTestCase):
    def test_fixes_accents(self):
        self.assertEqual(N.normalize_city("Brasilia"), "Brasília")
        self.assertEqual(N.normalize_city("Belem"), "Belém")

    def test_strips_uf_suffix(self):
        self.assertEqual(N.normalize_city("Brasília - DF"), "Brasília")

    def test_keeps_first_of_several(self):
        self.assertEqual(N.normalize_city("São Paulo, Lorena"), "São Paulo")

    def test_placeholders_return_empty(self):
        for value in ("Vários", "-", "NA", ""):
            self.assertEqual(N.normalize_city(value), "", value)


class NormalizeYearsTest(SimpleTestCase):
    def test_plain_durations(self):
        self.assertEqual(N.normalize_years("3 anos", 2025), 3)
        self.assertEqual(N.normalize_years("08 anos", 2025), 8)
        self.assertEqual(N.normalize_years("15", 2025), 15)

    def test_written_numbers(self):
        self.assertEqual(N.normalize_years("Dois anos", 2025), 2)
        self.assertEqual(N.normalize_years("Seis anos", 2025), 6)

    def test_start_year_becomes_duration(self):
        self.assertEqual(N.normalize_years("Desde 2015", 2025), 10)
        self.assertEqual(N.normalize_years("desde 2002", 2026), 24)

    def test_sub_year_durations_are_zero(self):
        self.assertEqual(N.normalize_years("6 meses", 2025), 0)
        self.assertEqual(N.normalize_years("poucos semanas", 2025), 0)

    def test_unparseable_returns_none(self):
        for value in ("N/A", "Iniciante", "Pouco tempo", ""):
            self.assertIsNone(N.normalize_years(value, 2025), value)


class NormalizePhoneTest(SimpleTestCase):
    def test_drops_numbers_destroyed_by_excel(self):
        # o Excel converteu alguns telefones em notação científica; os dígitos se perderam
        for value in ("5,52199E+12", "5,562E+12", "5,54199E+12"):
            self.assertEqual(N.normalize_phone(value), "", value)

    def test_keeps_usable_numbers(self):
        self.assertEqual(N.normalize_phone("+55 61 99977-3514"), "+55 61 99977-3514")


class NormalizeMultiSelectTest(SimpleTestCase):
    def test_split_ignores_commas_inside_parentheses(self):
        raw = "Unidade de conservação, Outras áreas protegidas (e.g., APP, FLONA), Área agrícola"
        self.assertEqual(
            N.split_multi(raw),
            ["Unidade de conservação", "Outras áreas protegidas (e.g., APP, FLONA)", "Área agrícola"],
        )

    def test_biomes_are_canonical_and_ordered(self):
        self.assertEqual(N.normalize_biomes("Cerrado, Amazônia"), ["Amazônia", "Cerrado"])
        self.assertEqual(N.normalize_biomes("Amazona"), ["Amazônia"])
        self.assertEqual(N.normalize_biomes("Transação dos biomas Cerrado e Amazonia"), ["Amazônia", "Cerrado"])

    def test_biomes_unknown_returns_empty(self):
        self.assertEqual(N.normalize_biomes("Rio de Janeiro"), [])

    def test_areas(self):
        raw = "Ecológica e ambiental, Governança e políticas públicas"
        self.assertEqual(N.normalize_areas(raw), ["Ecológica e ambiental", "Governança e políticas públicas"])


class NormalizeMiscTest(SimpleTestCase):
    def test_sector_multi_answer_prefers_public(self):
        raw = "Setor público (exemplo: universidade, etc.), Terceiro setor (exemplo: ONG, entre outros)"
        self.assertEqual(N.normalize_sector(raw), Sector.PUBLIC)

    def test_sector_third(self):
        self.assertEqual(N.normalize_sector("Terceiro setor (exemplo: ONG, entre outros)"), Sector.THIRD)

    def test_education(self):
        self.assertEqual(N.normalize_education("Doutorado"), EducationLevel.PHD)
        self.assertEqual(N.normalize_education("Doutorado em andamento"), EducationLevel.PHD_ONGOING)
        self.assertEqual(N.normalize_education("qualquer outra coisa"), "")

    def test_bool(self):
        self.assertIs(N.normalize_bool("Sim"), True)
        self.assertIs(N.normalize_bool("Não"), False)
        self.assertIsNone(N.normalize_bool(""))

    def test_orcid_accepts_bare_id_and_url(self):
        expected = "https://orcid.org/0000-0002-1698-1777"
        self.assertEqual(N.normalize_orcid("0000-0002-1698-1777"), expected)
        self.assertEqual(N.normalize_orcid("https://orcid.org/0000-0002-1698-1777"), expected)

    def test_url_rejects_non_urls(self):
        self.assertEqual(N.normalize_url("Não tenho", expect="linkedin"), "")
        self.assertEqual(N.normalize_url("Alba cordeiro", expect="linkedin"), "")
        self.assertTrue(N.normalize_url("http://lattes.cnpq.br/123", expect="lattes"))
