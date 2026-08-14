from django.test import TestCase
from django.urls import reverse

from apps.researchers.models import Biome, ProfileStatus, Researcher
from apps.users.models import CustomUser


def make_researcher(**overrides) -> Researcher:
    defaults = {
        "full_name": "Maria da Silva",
        "email": "maria@example.com",
        "consent_public": True,
        "status": ProfileStatus.APPROVED,
        "institution": "Universidade Federal do Fogo",
        "city": "Brasília",
        "state": "DF",
        "institution_latitude": -15.79,
        "institution_longitude": -47.88,
    }
    return Researcher.objects.create(**{**defaults, **overrides})


class VisibilityTest(TestCase):
    """O perfil só é público com aprovação E autorização de divulgação."""

    def test_approved_and_consenting_is_listed(self):
        researcher = make_researcher()
        response = self.client.get(reverse("researchers:list"))
        self.assertContains(response, researcher.full_name)

    def test_without_consent_is_hidden_from_list_and_detail(self):
        researcher = make_researcher(consent_public=False, email="sem@example.com")
        response = self.client.get(reverse("researchers:list"))
        self.assertNotContains(response, researcher.full_name)
        self.assertEqual(self.client.get(researcher.get_absolute_url()).status_code, 404)

    def test_pending_is_hidden_even_with_consent(self):
        researcher = make_researcher(status=ProfileStatus.PENDING, email="pend@example.com")
        self.assertEqual(self.client.get(researcher.get_absolute_url()).status_code, 404)

    def test_owner_can_preview_own_pending_profile(self):
        user = CustomUser.objects.create_user(username="dono", email="dono@example.com", password="x")
        researcher = make_researcher(status=ProfileStatus.PENDING, email="dono@example.com", user=user)
        self.client.force_login(user)
        self.assertEqual(self.client.get(researcher.get_absolute_url()).status_code, 200)


class MapDataTest(TestCase):
    def test_only_public_points_with_coordinates(self):
        make_researcher()
        make_researcher(email="sem-consent@example.com", consent_public=False)
        make_researcher(email="sem-coord@example.com", institution_latitude=None, institution_longitude=None)

        data = self.client.get(reverse("researchers:map_data")).json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["points"][0]["name"], "Maria da Silva")

    def test_restricted_fields_never_leave_the_api(self):
        make_researcher(phone="+55 61 99999-9999", gender="Mulher cisgênero", race="Parda", age_range="31 a 40 anos")
        payload = self.client.get(reverse("researchers:map_data")).content.decode()
        for secret in ("99999-9999", "cisgênero", "Parda", "31 a 40"):
            self.assertNotIn(secret, payload)

    def test_respects_filters(self):
        cerrado = Biome.objects.create(name="Cerrado", slug="cerrado")
        make_researcher().biomes.add(cerrado)
        make_researcher(email="outro@example.com", full_name="João Souza")

        data = self.client.get(reverse("researchers:map_data"), {"bioma": "cerrado"}).json()
        self.assertEqual(data["count"], 1)


class MapModeTest(TestCase):
    """O mapa pode posicionar por instituição (padrão) ou por cidade de moradia."""

    def test_institution_is_the_default_mode(self):
        make_researcher()
        data = self.client.get(reverse("researchers:map_data")).json()
        self.assertEqual(data["mode"], "instituicao")
        self.assertEqual(data["count"], 1)

    def test_residence_mode_only_includes_who_informed_it(self):
        make_researcher()  # só tem coordenada de instituição
        make_researcher(
            email="mora@example.com",
            full_name="João Mora",
            residence_city="Manaus",
            residence_state="AM",
            residence_latitude=-3.13,
            residence_longitude=-59.98,
        )
        data = self.client.get(reverse("researchers:map_data"), {"local": "moradia"}).json()
        self.assertEqual(data["mode"], "moradia")
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["points"][0]["name"], "João Mora")
        self.assertEqual(data["points"][0]["location"], "Manaus - Amazonas")

    def test_unknown_mode_falls_back_to_institution(self):
        make_researcher()
        data = self.client.get(reverse("researchers:map_data"), {"local": "sei-la"}).json()
        self.assertEqual(data["mode"], "instituicao")

    def test_residence_city_is_geocoded_from_cache_on_save(self):
        user = CustomUser.objects.create_user(username="geo", email="geo@example.com", password="x")
        self.client.force_login(user)
        self.client.post(
            reverse("researchers:save_profile"),
            {
                "full_name": "Quem Mora",
                "country": "Brasil",
                "city": "Brasília",
                "state": "DF",
                "residence_country": "Brasil",
                "residence_city": "brasilia",
                "residence_state": "DF",
            },
        )
        researcher = Researcher.objects.get(email="geo@example.com")
        self.assertEqual(researcher.residence_city, "Brasília")
        # Brasília está no cache versionado, então as coordenadas saem sem acessar a rede
        self.assertIsNotNone(researcher.residence_latitude)
        self.assertTrue(researcher.has_residence_coordinates)


class MissingFieldsTest(TestCase):
    def test_lists_what_is_worth_completing(self):
        researcher = make_researcher()
        self.assertIn("cidade onde mora", researcher.missing_profile_fields)
        self.assertIn("foto", researcher.missing_profile_fields)

    def test_filled_profile_has_nothing_missing(self):
        biome = Biome.objects.create(name="Cerrado", slug="cerrado")
        researcher = make_researcher(
            residence_city="Brasília",
            photo="researchers/photos/x.jpg",
            research_description="Ecologia do fogo no Cerrado.",
            lattes_url="http://lattes.cnpq.br/1",
        )
        researcher.biomes.add(biome)
        self.assertEqual(researcher.missing_profile_fields, [])


class DetailTest(TestCase):
    def test_restricted_fields_are_not_rendered(self):
        researcher = make_researcher(phone="+55 61 98888-8888", gender="Mulher cisgênero", race="Branca")
        body = self.client.get(researcher.get_absolute_url()).content.decode()
        self.assertNotIn("98888-8888", body)
        self.assertNotIn("cisgênero", body)
        self.assertNotIn("Branca", body)

    def test_shows_institution_and_location(self):
        researcher = make_researcher()
        response = self.client.get(researcher.get_absolute_url())
        self.assertContains(response, "Universidade Federal do Fogo")
        self.assertContains(response, "Brasília - Distrito Federal")


class ProfileSectionTest(TestCase):
    """O perfil de pesquisador é editado dentro de /users/profile/."""

    def test_save_requires_login(self):
        response = self.client.post(reverse("researchers:save_profile"), {})
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_legacy_url_redirects_to_account_profile(self):
        user = CustomUser.objects.create_user(username="velho", email="velho@example.com", password="x")
        self.client.force_login(user)
        response = self.client.get(reverse("researchers:my_profile"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], f"{reverse('users:user_profile')}#pesquisador")

    def test_section_is_rendered_on_the_account_profile_page(self):
        user = CustomUser.objects.create_user(username="sec", email="sec@example.com", password="x")
        self.client.force_login(user)
        response = self.client.get(reverse("users:user_profile"))
        self.assertContains(response, 'id="pesquisador"')
        self.assertContains(response, reverse("researchers:save_profile"))

    def test_claims_imported_profile_when_opening_the_page(self):
        researcher = make_researcher(email="claim@example.com")
        user = CustomUser.objects.create_user(username="claim", email="claim@example.com", password="x")
        self.client.force_login(user)

        response = self.client.get(reverse("users:user_profile"))
        researcher.refresh_from_db()
        self.assertEqual(researcher.user, user)
        # a ficha já vem preenchida com o que a pessoa respondeu no formulário
        self.assertContains(response, "Universidade Federal do Fogo")

    def test_new_profile_starts_pending(self):
        user = CustomUser.objects.create_user(username="novo", email="novo@example.com", password="x")
        self.client.force_login(user)

        response = self.client.post(
            reverse("researchers:save_profile"),
            {"full_name": "Pesquisador Novo", "country": "Brasil", "city": "Manaus", "state": "AM"},
        )
        self.assertEqual(response["Location"], f"{reverse('users:user_profile')}#pesquisador")
        researcher = Researcher.objects.get(email="novo@example.com")
        self.assertEqual(researcher.status, ProfileStatus.PENDING)
        self.assertFalse(researcher.is_public)

    def test_city_is_normalized_on_save(self):
        user = CustomUser.objects.create_user(username="norm", email="norm@example.com", password="x")
        self.client.force_login(user)
        self.client.post(
            reverse("researchers:save_profile"),
            {"full_name": "Alguém", "country": "Brasil", "city": "brasilia", "state": "DF"},
        )
        self.assertEqual(Researcher.objects.get(email="norm@example.com").city, "Brasília")

    def test_invalid_submission_rerenders_the_page_keeping_input(self):
        user = CustomUser.objects.create_user(username="inv", email="inv@example.com", password="x")
        self.client.force_login(user)

        response = self.client.post(
            reverse("researchers:save_profile"),
            {"full_name": "", "institution": "Instituto que não quero perder"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Instituto que não quero perder")
        self.assertContains(response, "Informe seu nome completo.")
        self.assertFalse(Researcher.objects.filter(email="inv@example.com").exists())

    def test_editing_does_not_change_status(self):
        user = CustomUser.objects.create_user(username="ed", email="ed@example.com", password="x")
        researcher = make_researcher(email="ed@example.com", user=user)
        self.client.force_login(user)

        self.client.post(
            reverse("researchers:save_profile"),
            {"full_name": "Maria da Silva", "country": "Brasil", "city": "Brasília", "state": "DF"},
        )
        researcher.refresh_from_db()
        self.assertEqual(researcher.status, ProfileStatus.APPROVED)


class SlugTest(TestCase):
    def test_slug_is_generated_and_unique(self):
        first = make_researcher()
        second = make_researcher(email="outra@example.com")
        self.assertEqual(first.slug, "maria-da-silva")
        self.assertEqual(second.slug, "maria-da-silva-2")
