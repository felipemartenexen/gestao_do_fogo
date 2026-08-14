from django.db import models
from django.urls import reverse
from django.utils.text import slugify

from apps.users.models import CustomUser
from apps.utils.models import BaseModel

# Unidades federativas, usadas para normalizar o campo livre do formulário.
UF_CHOICES = [
    ("AC", "Acre"),
    ("AL", "Alagoas"),
    ("AP", "Amapá"),
    ("AM", "Amazonas"),
    ("BA", "Bahia"),
    ("CE", "Ceará"),
    ("DF", "Distrito Federal"),
    ("ES", "Espírito Santo"),
    ("GO", "Goiás"),
    ("MA", "Maranhão"),
    ("MT", "Mato Grosso"),
    ("MS", "Mato Grosso do Sul"),
    ("MG", "Minas Gerais"),
    ("PA", "Pará"),
    ("PB", "Paraíba"),
    ("PR", "Paraná"),
    ("PE", "Pernambuco"),
    ("PI", "Piauí"),
    ("RJ", "Rio de Janeiro"),
    ("RN", "Rio Grande do Norte"),
    ("RS", "Rio Grande do Sul"),
    ("RO", "Rondônia"),
    ("RR", "Roraima"),
    ("SC", "Santa Catarina"),
    ("SP", "São Paulo"),
    ("SE", "Sergipe"),
    ("TO", "Tocantins"),
]


class Sector(models.TextChoices):
    PUBLIC = "public", "Setor público"
    PRIVATE = "private", "Setor privado"
    THIRD = "third", "Terceiro setor"
    INTERNATIONAL = "international", "Organismo internacional"
    OTHER = "other", "Outro"


class EducationLevel(models.TextChoices):
    BASIC = "basic", "Ensino básico completo"
    UNDERGRAD_ONGOING = "undergrad_ongoing", "Ensino superior incompleto"
    UNDERGRAD = "undergrad", "Ensino superior completo"
    MASTERS_ONGOING = "masters_ongoing", "Mestrado em andamento"
    MASTERS = "masters", "Mestrado"
    PHD_ONGOING = "phd_ongoing", "Doutorado em andamento"
    PHD = "phd", "Doutorado"


class ProfileStatus(models.TextChoices):
    PENDING = "pending", "Aguardando aprovação"
    APPROVED = "approved", "Aprovado"
    REJECTED = "rejected", "Recusado"


class ProfileSource(models.TextChoices):
    FORM = "form", "Formulário de mapeamento"
    SELF = "self", "Cadastro pelo próprio pesquisador"


class Biome(BaseModel):
    """Bioma pesquisado. Multi-seleção no formulário original."""

    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=80, unique=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "bioma"
        verbose_name_plural = "biomas"

    def __str__(self) -> str:
        return self.name


class ResearchArea(BaseModel):
    """Principal área de atuação dentro da pesquisa sobre fogo."""

    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "área de atuação"
        verbose_name_plural = "áreas de atuação"

    def __str__(self) -> str:
        return self.name


class MapMode(models.TextChoices):
    """Qual localização usar para posicionar o pesquisador no mapa."""

    INSTITUTION = "instituicao", "Instituição"
    RESIDENCE = "moradia", "Moradia"


class ResearcherQuerySet(models.QuerySet):
    def public(self) -> ResearcherQuerySet:
        """Perfis que podem aparecer no site: aprovados E com consentimento explícito."""
        return self.filter(status=ProfileStatus.APPROVED, consent_public=True)

    def mappable(self, mode: str = MapMode.INSTITUTION) -> ResearcherQuerySet:
        prefix = "residence_" if mode == MapMode.RESIDENCE else "institution_"
        return (
            self.public().exclude(**{f"{prefix}latitude__isnull": True}).exclude(**{f"{prefix}longitude__isnull": True})
        )


class Researcher(BaseModel):
    """
    Perfil de um pesquisador da rede Gestão do Fogo.

    Os campos agrupados em "dados restritos" ficam fora do consentimento dado no formulário
    (que cobria apenas nome, e-mail e instituição), então nunca são expostos publicamente -
    servem só para estatísticas agregadas no admin.
    """

    user = models.OneToOneField(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="researcher_profile",
        help_text="Conta que pode editar este perfil.",
    )
    full_name = models.CharField("nome completo", max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    email = models.EmailField("e-mail", unique=True)
    photo = models.ImageField("foto", upload_to="researchers/photos/", blank=True)

    consent_public = models.BooleanField(
        "autoriza divulgação",
        default=False,
        help_text="Respondeu 'Sim' à autorização de divulgar nome, e-mail e instituição para a rede.",
    )
    status = models.CharField(max_length=20, choices=ProfileStatus.choices, default=ProfileStatus.PENDING)
    source = models.CharField(max_length=20, choices=ProfileSource.choices, default=ProfileSource.SELF)
    submitted_at = models.DateTimeField(null=True, blank=True, help_text="Carimbo de data/hora da resposta original.")

    # vínculo institucional
    institution = models.CharField("instituição", max_length=400, blank=True)
    sector = models.CharField("setor", max_length=20, choices=Sector.choices, blank=True)
    position = models.CharField("cargo", max_length=300, blank=True)
    education_level = models.CharField("formação", max_length=30, choices=EducationLevel.choices, blank=True)

    # localização da instituição
    country = models.CharField("país da instituição", max_length=80, blank=True, default="Brasil")
    state = models.CharField("UF da instituição", max_length=2, choices=UF_CHOICES, blank=True)
    city = models.CharField("município da instituição", max_length=120, blank=True)
    institution_latitude = models.FloatField(null=True, blank=True)
    institution_longitude = models.FloatField(null=True, blank=True)

    # onde a pessoa mora - pergunta que não existia no formulário original, então só é
    # preenchida quando o próprio pesquisador atualiza o perfil
    residence_country = models.CharField("país onde mora", max_length=80, blank=True, default="Brasil")
    residence_state = models.CharField("UF onde mora", max_length=2, choices=UF_CHOICES, blank=True)
    residence_city = models.CharField("cidade onde mora", max_length=120, blank=True)
    residence_latitude = models.FloatField(null=True, blank=True)
    residence_longitude = models.FloatField(null=True, blank=True)

    # pesquisa
    main_research_area = models.CharField("principal área de pesquisa", max_length=400, blank=True)
    fire_focused = models.BooleanField("pesquisa majoritariamente focada no fogo", null=True, blank=True)
    years_researching = models.PositiveSmallIntegerField("anos pesquisando fogo", null=True, blank=True)
    years_researching_raw = models.CharField(max_length=120, blank=True, help_text="Resposta original, sem tratamento.")
    focused_on_brazil = models.BooleanField("pesquisa focada no Brasil", null=True, blank=True)
    other_territories = models.CharField("outros territórios", max_length=400, blank=True)

    biomes = models.ManyToManyField(Biome, blank=True, related_name="researchers", verbose_name="biomas")
    research_areas = models.ManyToManyField(
        ResearchArea, blank=True, related_name="researchers", verbose_name="áreas de atuação"
    )

    research_description = models.TextField("descrição da pesquisa", blank=True)
    develops_technology = models.BooleanField("desenvolve tecnologias", null=True, blank=True)
    technology_description = models.TextField("tecnologias desenvolvidas", blank=True)
    involves_communities = models.BooleanField("envolve comunidades humanas", null=True, blank=True)
    social_description = models.TextField("pesquisa socioambiental e econômica", blank=True)
    works_with_education = models.BooleanField("atua em educação ambiental", null=True, blank=True)
    education_description = models.TextField("pesquisa em educação ambiental", blank=True)
    governance_description = models.TextField("pesquisa em governança e políticas públicas", blank=True)

    publications = models.TextField("principais produções", blank=True)
    funding_sources = models.CharField("fontes de financiamento", max_length=500, blank=True)
    partnerships = models.TextField("parcerias nacionais", blank=True)
    foreign_partnerships = models.TextField("parcerias estrangeiras", blank=True)
    outreach = models.CharField("divulgação para público não acadêmico", max_length=500, blank=True)

    # links
    lattes_url = models.CharField("currículo Lattes", max_length=500, blank=True)
    orcid_url = models.CharField("ORCID", max_length=200, blank=True)
    linkedin_url = models.CharField("LinkedIn", max_length=300, blank=True)

    # --- dados restritos: fora do consentimento, nunca exibidos publicamente ---
    phone = models.CharField("telefone", max_length=60, blank=True)
    gender = models.CharField("gênero", max_length=60, blank=True)
    race = models.CharField("raça/cor", max_length=60, blank=True)
    age_range = models.CharField("faixa etária", max_length=40, blank=True)
    has_children = models.BooleanField("tem filhos", null=True, blank=True)
    origin_country = models.CharField("país de origem", max_length=80, blank=True)
    origin_state = models.CharField("estado de origem", max_length=80, blank=True)

    objects = ResearcherQuerySet.as_manager()

    class Meta:
        ordering = ["full_name"]
        verbose_name = "pesquisador"
        verbose_name_plural = "pesquisadores"
        indexes = [
            models.Index(fields=["status", "consent_public"]),
            models.Index(fields=["state"]),
        ]

    def __str__(self) -> str:
        return self.full_name

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = self._build_unique_slug()
        super().save(*args, **kwargs)

    def _build_unique_slug(self) -> str:
        base = slugify(self.full_name) or "pesquisador"
        slug, counter = base, 2
        while Researcher.objects.filter(slug=slug).exclude(pk=self.pk).exists():
            slug = f"{base}-{counter}"
            counter += 1
        return slug

    def get_absolute_url(self) -> str:
        return reverse("researchers:detail", args=[self.slug])

    @property
    def is_public(self) -> bool:
        return self.status == ProfileStatus.APPROVED and self.consent_public

    @staticmethod
    def _format_location(city: str, state_display: str, country: str) -> str:
        parts = [p for p in (city, state_display) if p]
        if not parts:
            return country or ""
        label = " - ".join(parts)
        return f"{label} ({country})" if country and country != "Brasil" else label

    @property
    def location_label(self) -> str:
        """Onde fica a instituição."""
        return self._format_location(self.city, self.get_state_display() if self.state else "", self.country)

    @property
    def residence_label(self) -> str:
        """Onde a pessoa mora."""
        return self._format_location(
            self.residence_city,
            self.get_residence_state_display() if self.residence_state else "",
            self.residence_country,
        )

    @property
    def has_coordinates(self) -> bool:
        return self.institution_latitude is not None and self.institution_longitude is not None

    @property
    def has_residence_coordinates(self) -> bool:
        return self.residence_latitude is not None and self.residence_longitude is not None

    @property
    def missing_profile_fields(self) -> list[str]:
        """Campos que valem a pena pedir para o pesquisador completar."""
        missing = []
        if not self.residence_city:
            missing.append("cidade onde mora")
        if not self.photo:
            missing.append("foto")
        if not self.research_description:
            missing.append("descrição da pesquisa")
        if not self.biomes.exists():
            missing.append("biomas")
        if not (self.lattes_url or self.orcid_url):
            missing.append("Lattes ou ORCID")
        return missing

    @property
    def initials(self) -> str:
        parts = [p for p in self.full_name.split() if len(p) > 2]
        if not parts:
            return self.full_name[:2].upper()
        return (parts[0][0] + parts[-1][0]).upper()
