"""Formulário de notícia fora do admin do Wagtail, para quem só precisa publicar."""

import json
import re

from django import forms
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.text import slugify

from apps.content.models import BlogPage

INPUT = "input input-bordered w-full"
TEXTAREA = "textarea textarea-bordered w-full"


class NewsForm(forms.Form):
    """
    Cria e edita uma notícia (BlogPage) com os campos que importam no dia a dia.

    O corpo é HTML simples porque é o que o StreamField já aceita no bloco `html` -
    o mesmo formato usado por `bootstrap_news`. Quem precisar de blocos ricos
    (galeria, embeds) continua tendo o /cms/.
    """

    title = forms.CharField(
        label="Título",
        max_length=200,
        widget=forms.TextInput(attrs={"class": INPUT, "placeholder": "Título da notícia"}),
    )
    date = forms.DateField(
        label="Data",
        widget=forms.DateInput(attrs={"class": INPUT, "type": "date"}),
        help_text="Data exibida na notícia e usada para ordenar a listagem.",
    )
    intro = forms.CharField(
        label="Chamada",
        max_length=250,
        widget=forms.Textarea(attrs={"class": TEXTAREA, "rows": 3}),
        help_text="Resumo de uma ou duas frases. Aparece na listagem e na home.",
    )
    body = forms.CharField(
        label="Texto",
        widget=forms.Textarea(attrs={"class": TEXTAREA, "rows": 16}),
        help_text="Aceita HTML simples: <p>, <strong>, <em>, <ul>/<li>, <h3> e <a href>.",
    )

    def __init__(self, *args, instance: BlogPage | None = None, **kwargs):
        self.instance = instance
        if instance is not None and "initial" not in kwargs:
            kwargs["initial"] = {
                "title": instance.title,
                "date": instance.date,
                "intro": instance.intro,
                "body": _stream_to_html(instance.body),
            }
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.error_messages.setdefault("required", "Campo obrigatório.")

    def clean_title(self) -> str:
        title = self.cleaned_data["title"].strip()
        slug = slugify(title)[:250]
        conflict = BlogPage.objects.filter(slug=slug)
        if self.instance is not None:
            conflict = conflict.exclude(pk=self.instance.pk)
        if conflict.exists():
            raise forms.ValidationError("Já existe uma notícia com esse título. Escolha outro.")
        self.cleaned_slug = slug
        return title

    def stream_value(self) -> str:
        return json.dumps(
            [{"type": "html", "value": self.cleaned_data["body"].strip()}],
            cls=DjangoJSONEncoder,
        )


def _stream_to_html(body) -> str:
    """Volta do StreamField para o textarea, juntando os blocos de texto."""
    parts = []
    for block in body:
        value = block.value
        parts.append(str(value.source) if hasattr(value, "source") else str(value))
    return "\n\n".join(p for p in parts if p).strip()


def html_preview(text: str, limit: int = 240) -> str:
    """Texto sem marcação, para a listagem administrativa."""
    return re.sub(r"<[^>]+>", " ", text)[:limit].strip()
