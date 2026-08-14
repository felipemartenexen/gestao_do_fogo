"""
Controle de acesso: quem entra na plataforma e com qual papel.

Fica separado de `views.py` (que cuida das métricas de cadastro) porque aqui a
preocupação é operacional - revisar contas, ativar, desativar e promover.
"""

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import user_passes_test
from django.core.paginator import Paginator
from django.db.models import Count, Q, QuerySet
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.researchers.models import ProfileStatus, Researcher
from apps.users.models import CustomUser

PAGE_SIZE = 25

#: Papéis derivados das flags do Django. Não criamos um modelo de papel: com três
#: níveis, as flags nativas bastam e continuam valendo no /admin/.
ROLES = [
    ("superuser", "Administrador"),
    ("staff", "Equipe"),
    ("member", "Membro"),
]


def role_of(user: CustomUser) -> str:
    if user.is_superuser:
        return "superuser"
    if user.is_staff:
        return "staff"
    return "member"


def _filtered_users(request) -> tuple[QuerySet, dict]:
    users = CustomUser.objects.all().select_related("researcher_profile")

    search = (request.GET.get("q") or "").strip()
    role = (request.GET.get("papel") or "").strip()
    status = (request.GET.get("status") or "").strip()

    if search:
        users = users.filter(
            Q(email__icontains=search)
            | Q(username__icontains=search)
            | Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
        )
    if role == "superuser":
        users = users.filter(is_superuser=True)
    elif role == "staff":
        users = users.filter(is_staff=True, is_superuser=False)
    elif role == "member":
        users = users.filter(is_staff=False, is_superuser=False)

    if status == "ativos":
        users = users.filter(is_active=True)
    elif status == "inativos":
        users = users.filter(is_active=False)
    elif status == "pesquisadores":
        users = users.filter(researcher_profile__isnull=False)
    elif status == "aguardando":
        users = users.filter(researcher_profile__status=ProfileStatus.PENDING)

    return users, {"q": search, "papel": role, "status": status}


@user_passes_test(lambda u: u.is_superuser, login_url="/404")
@staff_member_required
def access_control(request) -> HttpResponse:
    users, active = _filtered_users(request)

    paginator = Paginator(users.order_by("-date_joined"), PAGE_SIZE)
    page = paginator.get_page(request.GET.get("page"))

    querystring = request.GET.copy()
    querystring.pop("page", None)

    counts = CustomUser.objects.aggregate(
        total=Count("id"),
        ativos=Count("id", filter=Q(is_active=True)),
        equipe=Count("id", filter=Q(is_staff=True)),
        administradores=Count("id", filter=Q(is_superuser=True)),
    )

    rows = [
        {
            "user": user,
            "role": role_of(user),
            "role_label": dict(ROLES)[role_of(user)],
            "researcher": getattr(user, "researcher_profile", None),
        }
        for user in page.object_list
    ]

    context = {
        "active_tab": "access-control",
        "page_title": "Controle de acesso",
        "page_obj": page,
        "rows": rows,
        "total": paginator.count,
        "counts": counts,
        "roles": ROLES,
        "active": active,
        "has_filters": any(active.values()),
        "querystring": querystring.urlencode(),
        "pending_profiles": Researcher.objects.filter(status=ProfileStatus.PENDING).count(),
    }
    return render(request, "dashboard/access_control.html", context)


@user_passes_test(lambda u: u.is_superuser, login_url="/404")
@staff_member_required
@require_POST
def update_user(request, user_id: int) -> HttpResponseRedirect:
    """
    Aplica uma ação sobre um usuário.

    O próprio administrador não pode se rebaixar nem se desativar: sem essa trava dá
    para ficar de fora da própria plataforma com um clique, sem forma de voltar.
    """
    user = get_object_or_404(CustomUser, pk=user_id)
    action = request.POST.get("acao", "")
    redirect_to = request.POST.get("next") or reverse("dashboard:access_control")

    if user == request.user and action in {"desativar", "papel"}:
        messages.error(request, "Você não pode alterar o próprio acesso por aqui.")
        return HttpResponseRedirect(redirect_to)

    if action == "ativar":
        user.is_active = True
        user.save(update_fields=["is_active"])
        messages.success(request, f"{user.get_display_name()} reativado.")
    elif action == "desativar":
        user.is_active = False
        user.save(update_fields=["is_active"])
        messages.success(request, f"{user.get_display_name()} desativado.")
    elif action == "papel":
        role = request.POST.get("papel", "member")
        user.is_superuser = role == "superuser"
        # administrador também é equipe: sem is_staff ele perde o acesso ao /admin/
        user.is_staff = role in {"superuser", "staff"}
        user.save(update_fields=["is_superuser", "is_staff"])
        messages.success(request, f"{user.get_display_name()} agora é {dict(ROLES)[role]}.")
    elif action == "aprovar_perfil":
        researcher = getattr(user, "researcher_profile", None)
        if researcher is None:
            messages.error(request, "Este usuário não tem perfil de pesquisador.")
        else:
            researcher.status = ProfileStatus.APPROVED
            researcher.save(update_fields=["status", "updated_at"])
            messages.success(request, f"Perfil de {researcher.full_name} aprovado.")
            if not researcher.consent_public:
                messages.warning(
                    request,
                    "O perfil segue invisível no site: falta a autorização de divulgação.",
                )
    else:
        messages.error(request, "Ação desconhecida.")

    return HttpResponseRedirect(redirect_to)
