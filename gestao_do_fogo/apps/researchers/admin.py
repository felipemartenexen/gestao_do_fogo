from django.contrib import admin, messages
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils.html import format_html

from .models import Biome, ProfileStatus, ResearchArea, Researcher


@admin.register(Biome)
class BiomeAdmin(admin.ModelAdmin):
    list_display = ["name", "order", "researcher_count"]
    prepopulated_fields = {"slug": ("name",)}

    @admin.display(description="pesquisadores")
    def researcher_count(self, obj: Biome) -> int:
        return obj.researchers.count()


@admin.register(ResearchArea)
class ResearchAreaAdmin(admin.ModelAdmin):
    list_display = ["name", "order", "researcher_count"]
    prepopulated_fields = {"slug": ("name",)}

    @admin.display(description="pesquisadores")
    def researcher_count(self, obj: ResearchArea) -> int:
        return obj.researchers.count()


@admin.register(Researcher)
class ResearcherAdmin(admin.ModelAdmin):
    list_display = ["full_name", "institution", "location_label", "status", "consent_public", "on_map", "source"]
    list_filter = ["status", "consent_public", "source", "sector", "education_level", "state", "biomes"]
    list_select_related = ["user"]
    search_fields = ["full_name", "email", "institution", "city", "main_research_area"]
    filter_horizontal = ["biomes", "research_areas"]
    readonly_fields = ["created_at", "updated_at", "submitted_at", "years_researching_raw"]
    autocomplete_fields = ["user"]
    actions = ["approve", "reject"]
    fieldsets = [
        (
            "Publicação",
            {
                "fields": ["status", "consent_public", "source", "user", "submitted_at"],
                "description": (
                    "O perfil só aparece no site quando está <b>aprovado</b> E tem <b>autorização de divulgação</b>. "
                    "A autorização vem da pergunta do formulário sobre divulgar nome, e-mail e instituição."
                ),
            },
        ),
        ("Identificação", {"fields": ["full_name", "slug", "email", "photo"]}),
        ("Vínculo institucional", {"fields": ["institution", "sector", "position", "education_level"]}),
        (
            "Localização da instituição",
            {"fields": ["country", "state", "city", "institution_latitude", "institution_longitude"]},
        ),
        (
            "Moradia",
            {
                "description": (
                    "A cidade de moradia não existia no formulário original - só é preenchida "
                    "quando o próprio pesquisador atualiza o perfil."
                ),
                "fields": [
                    "residence_country",
                    "residence_state",
                    "residence_city",
                    "residence_latitude",
                    "residence_longitude",
                ],
            },
        ),
        (
            "Pesquisa",
            {
                "fields": [
                    "main_research_area",
                    "fire_focused",
                    "years_researching",
                    "years_researching_raw",
                    "focused_on_brazil",
                    "other_territories",
                    "biomes",
                    "research_areas",
                    "research_description",
                ]
            },
        ),
        (
            "Atuação",
            {
                "classes": ["collapse"],
                "fields": [
                    "develops_technology",
                    "technology_description",
                    "involves_communities",
                    "social_description",
                    "works_with_education",
                    "education_description",
                    "governance_description",
                ],
            },
        ),
        (
            "Produção e rede",
            {
                "classes": ["collapse"],
                "fields": [
                    "publications",
                    "funding_sources",
                    "partnerships",
                    "foreign_partnerships",
                    "outreach",
                    "lattes_url",
                    "orcid_url",
                    "linkedin_url",
                ],
            },
        ),
        (
            "Dados restritos (nunca exibidos publicamente)",
            {
                "classes": ["collapse"],
                "description": (
                    "A autorização do formulário cobria apenas nome, e-mail e instituição. "
                    "Estes campos ficam aqui só para estatísticas agregadas da rede."
                ),
                "fields": ["phone", "gender", "race", "age_range", "has_children", "origin_country", "origin_state"],
            },
        ),
        ("Metadados", {"classes": ["collapse"], "fields": ["created_at", "updated_at"]}),
    ]

    @admin.display(description="no mapa", boolean=True)
    def on_map(self, obj: Researcher) -> bool:
        return obj.is_public and obj.has_coordinates

    @admin.display(description="localização")
    def location_label(self, obj: Researcher) -> str:
        return obj.location_label or format_html('<span style="color:#999">-</span>')

    @admin.action(description="Aprovar perfis selecionados")
    def approve(self, request: HttpRequest, queryset: QuerySet) -> None:
        updated = queryset.update(status=ProfileStatus.APPROVED)
        without_consent = queryset.filter(consent_public=False).count()
        self.message_user(request, f"{updated} perfis aprovados.")
        if without_consent:
            self.message_user(
                request,
                f"{without_consent} deles continuam invisíveis no site por não terem autorização de divulgação.",
                level=messages.WARNING,
            )

    @admin.action(description="Recusar perfis selecionados")
    def reject(self, request: HttpRequest, queryset: QuerySet) -> None:
        self.message_user(request, f"{queryset.update(status=ProfileStatus.REJECTED)} perfis recusados.")
