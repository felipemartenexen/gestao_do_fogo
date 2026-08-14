from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from . import services
from .forms import ResearcherProfileForm
from .models import (
    UF_CHOICES,
    Biome,
    MapMode,
    ProfileSource,
    ProfileStatus,
    ResearchArea,
    Researcher,
    Sector,
)

PAGE_SIZE = 24


def _filtered(request) -> tuple:
    """Aplica os filtros da querystring sobre os perfis públicos."""
    qs = Researcher.objects.public().prefetch_related("biomes", "research_areas")

    search = (request.GET.get("q") or "").strip()
    biome = (request.GET.get("bioma") or "").strip()
    state = (request.GET.get("uf") or "").strip()
    sector = (request.GET.get("setor") or "").strip()
    area = (request.GET.get("area") or "").strip()

    if search:
        qs = qs.filter(
            Q(full_name__icontains=search)
            | Q(institution__icontains=search)
            | Q(main_research_area__icontains=search)
            | Q(research_description__icontains=search)
            | Q(city__icontains=search)
        )
    if biome:
        qs = qs.filter(biomes__slug=biome)
    if state:
        qs = qs.filter(state=state)
    if sector:
        qs = qs.filter(sector=sector)
    if area:
        qs = qs.filter(research_areas__slug=area)

    return qs.distinct(), {"q": search, "bioma": biome, "uf": state, "setor": sector, "area": area}


def researcher_list(request) -> HttpResponse:
    researchers, active = _filtered(request)

    # UFs que realmente têm alguém, para não poluir o filtro com estados vazios
    used_states = set(Researcher.objects.public().values_list("state", flat=True))
    state_options = [(code, label) for code, label in UF_CHOICES if code in used_states]

    paginator = Paginator(researchers.order_by("full_name"), PAGE_SIZE)
    page = paginator.get_page(request.GET.get("page"))

    querystring = request.GET.copy()
    querystring.pop("page", None)
    # querystring sem o modo do mapa, para os botões do alternador trocarem só o `local`
    base_querystring = querystring.copy()
    base_querystring.pop("local", None)
    base_encoded = base_querystring.urlencode()

    # convite para completar o perfil, só para quem já tem um
    own_profile = None
    if request.user.is_authenticated:
        own_profile = (
            Researcher.objects.filter(user=request.user).first()
            or Researcher.objects.filter(email__iexact=request.user.email).first()
        )

    mode = _map_mode(request)
    context = {
        "own_profile": own_profile,
        "page_title": "Pesquisadores",
        "page_description": "Rede de pesquisadores de fogo no Brasil: quem são, onde estão e o que pesquisam.",
        "active_tab": "researchers",
        "page_obj": page,
        "total": paginator.count,
        "total_all": Researcher.objects.public().count(),
        "map_mode": mode,
        "map_modes": MapMode.choices,
        "institution_count": Researcher.objects.mappable(MapMode.INSTITUTION).count(),
        "residence_count": Researcher.objects.mappable(MapMode.RESIDENCE).count(),
        "biomes": Biome.objects.annotate(n=Count("researchers")).filter(n__gt=0),
        "areas": ResearchArea.objects.annotate(n=Count("researchers")).filter(n__gt=0),
        "state_options": state_options,
        "sector_options": Sector.choices,
        "active": active,
        "has_filters": any(active.values()),
        "querystring": querystring.urlencode(),
        "base_querystring": f"{base_encoded}&" if base_encoded else "",
    }
    return render(request, "researchers/researcher_list.html", context)


def _map_mode(request) -> str:
    mode = (request.GET.get("local") or "").strip()
    return mode if mode in MapMode.values else MapMode.INSTITUTION


def researcher_map_data(request) -> JsonResponse:
    """
    Pontos do mapa em JSON, respeitando os mesmos filtros da listagem.

    Só devolve campos cobertos pela autorização de divulgação (nome, instituição, local) -
    telefone e dados demográficos nunca saem daqui.
    """
    researchers, _ = _filtered(request)
    mode = _map_mode(request)
    is_residence = mode == MapMode.RESIDENCE

    points = [
        {
            "name": r.full_name,
            "slug": r.slug,
            "institution": r.institution,
            "location": r.residence_label if is_residence else r.location_label,
            "lat": r.residence_latitude if is_residence else r.institution_latitude,
            "lon": r.residence_longitude if is_residence else r.institution_longitude,
            "url": r.get_absolute_url(),
        }
        for r in researchers.mappable(mode).order_by("full_name")
    ]
    return JsonResponse({"points": points, "count": len(points), "mode": mode})


def researcher_detail(request, slug: str) -> HttpResponse:
    researcher = get_object_or_404(
        Researcher.objects.prefetch_related("biomes", "research_areas"),
        slug=slug,
    )
    # perfis não públicos só são visíveis para o dono e para a equipe
    if not researcher.is_public:
        user = request.user
        is_owner = user.is_authenticated and researcher.user_id == user.id
        if not (is_owner or (user.is_authenticated and user.is_staff)):
            raise Http404
    context = {
        "researcher": researcher,
        "page_title": researcher.full_name,
        "page_description": f"{researcher.full_name} - {researcher.institution}" if researcher.institution else "",
        "active_tab": "researchers",
        "is_owner": request.user.is_authenticated and researcher.user_id == request.user.id,
    }
    return render(request, "researchers/researcher_detail.html", context)


@login_required
def my_profile(request) -> HttpResponse:
    """O perfil de pesquisador é editado dentro do perfil da conta."""
    return redirect(f"{reverse('users:user_profile')}#pesquisador")


@login_required
@require_POST
def save_profile(request) -> HttpResponse:
    """
    Grava a seção de pesquisador do /users/profile/.

    Quando o formulário não valida, re-renderiza a página de perfil inteira com os erros,
    para a pessoa não perder o que já tinha digitado.
    """
    from apps.users.views import profile_context

    researcher = services.get_profile(request.user)
    is_new = researcher is None
    form = ResearcherProfileForm(request.POST, request.FILES, instance=researcher)

    if not form.is_valid():
        context = profile_context(request, researcher_form=form, researcher=researcher)
        return render(request, "account/profile.html", context)

    profile = form.save(commit=False)
    profile.user = request.user
    if is_new:
        profile.email = request.user.email
        profile.source = ProfileSource.SELF
        profile.status = ProfileStatus.PENDING
    profile.save()
    form.save_m2m()

    if is_new:
        messages.success(request, "Cadastro enviado. Ele passa por uma revisão da equipe antes de aparecer no mapa.")
    else:
        messages.success(request, "Perfil de pesquisador atualizado.")
    return redirect(f"{reverse('users:user_profile')}#pesquisador")
