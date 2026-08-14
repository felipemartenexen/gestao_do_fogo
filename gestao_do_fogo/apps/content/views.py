"""
Área de notícias para a equipe, fora do admin do Wagtail.

O /cms/ do Wagtail continua existindo e é mais poderoso; estas telas cobrem o caminho
comum - escrever, revisar e publicar uma notícia - sem exigir familiaridade com ele.
"""

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.content.forms import NewsForm
from apps.content.models import BlogIndexPage, BlogPage


def _news_index() -> BlogIndexPage | None:
    return BlogIndexPage.objects.filter(slug="noticias").first()


@staff_member_required
def news_list(request) -> HttpResponse:
    posts = BlogPage.objects.all().order_by("-date")
    context = {
        "active_tab": "news-admin",
        "page_title": "Notícias",
        "posts": posts,
        "index_missing": _news_index() is None,
    }
    return render(request, "content/admin/news_list.html", context)


@staff_member_required
def news_create(request) -> HttpResponse:
    index = _news_index()
    if index is None:
        messages.error(request, "Página de Notícias não encontrada. Rode `manage.py bootstrap_content`.")
        return redirect("content:news_list")

    if request.method == "POST":
        form = NewsForm(request.POST)
        if form.is_valid():
            post = BlogPage(
                slug=form.cleaned_slug,
                title=form.cleaned_data["title"],
                date=form.cleaned_data["date"],
                intro=form.cleaned_data["intro"],
                body=form.stream_value(),
            )
            index.add_child(instance=post)
            post.save()
            post.save_revision().publish()
            messages.success(request, "Notícia publicada.")
            return redirect("content:news_list")
    else:
        form = NewsForm(initial={"date": timezone.localdate()})

    return render(
        request,
        "content/admin/news_form.html",
        {"form": form, "active_tab": "news-admin", "page_title": "Nova notícia", "post": None},
    )


@staff_member_required
def news_edit(request, page_id: int) -> HttpResponse:
    post = get_object_or_404(BlogPage, pk=page_id)

    if request.method == "POST":
        form = NewsForm(request.POST, instance=post)
        if form.is_valid():
            post.title = form.cleaned_data["title"]
            post.slug = form.cleaned_slug
            post.date = form.cleaned_data["date"]
            post.intro = form.cleaned_data["intro"]
            post.body = form.stream_value()
            post.save()
            post.save_revision().publish()
            messages.success(request, "Notícia atualizada.")
            return redirect("content:news_list")
    else:
        form = NewsForm(instance=post)

    return render(
        request,
        "content/admin/news_form.html",
        {"form": form, "active_tab": "news-admin", "page_title": post.title, "post": post},
    )


@staff_member_required
@require_POST
def news_toggle(request, page_id: int) -> HttpResponseRedirect:
    """
    Publica ou despublica sem apagar.

    Despublicar tira a notícia do site mantendo o texto - é o que se quer quando um
    evento é adiado, por exemplo.
    """
    post = get_object_or_404(BlogPage, pk=page_id)
    if post.live:
        post.unpublish()
        messages.success(request, f"“{post.title}” saiu do ar.")
    else:
        post.save_revision().publish()
        messages.success(request, f"“{post.title}” publicada.")
    return HttpResponseRedirect(reverse("content:news_list"))
