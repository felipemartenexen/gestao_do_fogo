from typing import Any

from django.conf import settings
from django.contrib.auth.decorators import user_passes_test
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from health_check.views import HealthCheckView


def home(request) -> HttpResponse:
    if request.user.is_authenticated:
        return render(
            request,
            "web/app_home.html",
            context={
                "active_tab": "dashboard",
                "page_title": _("Painel"),
            },
        )
    return render(request, "web/landing_page.html", context=_landing_context())


def _landing_context() -> dict:
    """
    Números e notícias da home.

    Importado aqui dentro para a app `web` não depender de `researchers`/`content`
    no import time - se um dia esses apps saírem, a home continua carregando.
    """
    from apps.content.models import BlogPage
    from apps.researchers.models import Biome, Researcher

    public = Researcher.objects.public()
    return {
        "total_researchers": public.count(),
        "total_states": public.exclude(state="").values("state").distinct().count(),
        "total_institutions": public.exclude(institution="").values("institution").distinct().count(),
        "biomes": Biome.objects.all(),
        "latest_news": BlogPage.objects.live().order_by("-date")[:3],
    }


@user_passes_test(lambda u: u.is_superuser)
def simulate_error(request) -> HttpResponse:
    raise Exception("This is a simulated error.")


class HealthCheck(HealthCheckView):
    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        tokens = settings.HEALTH_CHECK_TOKENS
        if tokens and request.GET.get("token") not in tokens:
            raise Http404
        return super().get(request, *args, **kwargs)
