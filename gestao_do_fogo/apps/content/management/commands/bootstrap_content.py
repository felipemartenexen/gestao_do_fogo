import json
from typing import Any

from django.core.management.base import BaseCommand
from django.core.serializers.json import DjangoJSONEncoder
from wagtail.models import Page, Site

from apps.content.models import BlogIndexPage, ContentPage

# slugs referenced by the public nav in templates/web/components/top_nav.html
NEWS_SLUG = "noticias"
NEWS_INTRO = "Acompanhe as novidades da plataforma Gestão do Fogo."
OLD_BLOG_INTRO = "Welcome to our blog!"
SECTION_PAGES = [
    (
        "iniciativas",
        "Iniciativas",
        "Conheça as iniciativas da plataforma Gestão do Fogo. "
        'Você pode editar esta página <a href="/cms">no admin de conteúdo</a>.',
    ),
    (
        "pesquisadores",
        "Pesquisadores",
        "Conheça os pesquisadores que fazem parte da rede Gestão do Fogo. "
        'Você pode editar esta página <a href="/cms">no admin de conteúdo</a>.',
    ),
]


class Command(BaseCommand):
    help = "Bootstraps your initial Wagtail / blog set up"

    def handle(self, **options: Any) -> None:
        bootstrap_initial_content()


def bootstrap_initial_content() -> None:
    root_page = Page.objects.get(slug="root").specific
    try:
        landing_page = ContentPage.objects.get(slug="content")
        print("Using existing content homepage...")
    except ContentPage.DoesNotExist:
        print("Creating your content homepage...")
        landing_page = ContentPage(
            slug="content",
            title="Conteúdo",
            body=_text_to_stream_value(
                "Área de conteúdo do site. As páginas e notícias abaixo podem ser editadas "
                'no <a href="/cms">admin de conteúdo</a>.'
            ),
        )
        root_page.add_child(instance=landing_page)
        landing_page.save()

    site = Site.objects.get()
    site.root_page = landing_page
    site.save()

    blog_index = BlogIndexPage.objects.filter(slug__in=[NEWS_SLUG, "blog"]).first()
    if blog_index is None:
        print("Creating your news index page...")
        blog_index = BlogIndexPage(
            slug=NEWS_SLUG,
            title="Notícias",
            intro=NEWS_INTRO,
        )
        landing_page.add_child(instance=blog_index)
        blog_index.save()
    else:
        if blog_index.slug != NEWS_SLUG:
            # the page was originally bootstrapped as "Blog" - rename it in place so that
            # existing posts are kept and the nav's {% slugurl 'noticias' %} resolves
            print("Renaming your blog index page to Notícias...")
            blog_index.slug = NEWS_SLUG
            blog_index.title = "Notícias"
        else:
            print("Using existing news index page...")
        if blog_index.intro == OLD_BLOG_INTRO:
            # only replace the leftover boilerplate, never an intro that was edited in the CMS
            blog_index.intro = NEWS_INTRO
        blog_index.save()

    for slug, title, body in SECTION_PAGES:
        if ContentPage.objects.filter(slug=slug).exists():
            print(f"Using existing {title} page...")
            continue
        print(f"Creating your {title} page...")
        section_page = ContentPage(slug=slug, title=title, body=_text_to_stream_value(body))
        landing_page.add_child(instance=section_page)
        section_page.save()

    # As notícias reais da rede são publicadas por `manage.py bootstrap_news`.
    # Os posts de exemplo do Pegasus ("Pegasus and Wagtail", "Another Blog Post") foram
    # removidos daqui para não reaparecerem a cada execução.
    print("Notícias: rode `manage.py bootstrap_news` para publicar o conteúdo da rede.")


def _text_to_stream_value(text: str) -> str:
    return json.dumps([{"type": "paragraph", "value": text}], cls=DjangoJSONEncoder)
