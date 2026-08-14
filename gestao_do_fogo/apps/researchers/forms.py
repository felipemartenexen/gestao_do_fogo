from typing import Any

from django import forms

from .models import Researcher

# classes DaisyUI aplicadas a cada tipo de campo
TEXT_INPUT = "input input-bordered w-full"
TEXTAREA = "textarea textarea-bordered w-full"
SELECT = "select select-bordered w-full"


class ResearcherProfileForm(forms.ModelForm):
    """
    Formulário que o próprio pesquisador usa para se cadastrar e manter os dados.

    Expõe só o que é público. Os campos restritos (telefone, gênero, raça/cor, faixa
    etária, filhos) ficam de fora de propósito: eles vieram do formulário original sob
    uma autorização que não cobria divulgação, então não são editados nem exibidos aqui.
    """

    consent_public = forms.BooleanField(
        required=False,
        label="Autorizo divulgar meu nome, e-mail e instituição na rede",
        help_text="Sem esta autorização seu perfil fica salvo, mas não aparece na página pública nem no mapa.",
    )

    class Meta:
        model = Researcher
        fields = [
            "full_name",
            "photo",
            "consent_public",
            "institution",
            "sector",
            "position",
            "education_level",
            "country",
            "state",
            "city",
            "residence_country",
            "residence_state",
            "residence_city",
            "main_research_area",
            "fire_focused",
            "years_researching",
            "focused_on_brazil",
            "other_territories",
            "biomes",
            "research_areas",
            "research_description",
            "develops_technology",
            "technology_description",
            "involves_communities",
            "social_description",
            "works_with_education",
            "education_description",
            "governance_description",
            "publications",
            "funding_sources",
            "partnerships",
            "foreign_partnerships",
            "outreach",
            "lattes_url",
            "orcid_url",
            "linkedin_url",
        ]
        widgets = {
            "biomes": forms.CheckboxSelectMultiple,
            "research_areas": forms.CheckboxSelectMultiple,
            "research_description": forms.Textarea(attrs={"rows": 4}),
            "technology_description": forms.Textarea(attrs={"rows": 3}),
            "social_description": forms.Textarea(attrs={"rows": 3}),
            "education_description": forms.Textarea(attrs={"rows": 3}),
            "governance_description": forms.Textarea(attrs={"rows": 3}),
            "publications": forms.Textarea(attrs={"rows": 3}),
            "partnerships": forms.Textarea(attrs={"rows": 2}),
            "foreign_partnerships": forms.Textarea(attrs={"rows": 2}),
        }
        help_texts = {
            "city": "Município onde fica a instituição.",
            "residence_city": "Cidade onde você mora. Permite ver a rede por moradia, não só por instituição.",
            "photo": "Opcional. Aparece no seu perfil público.",
            "years_researching": "Há quantos anos você pesquisa fogo.",
            "lattes_url": "URL completa do currículo Lattes.",
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["full_name"].required = True
        self.fields["full_name"].error_messages["required"] = "Informe seu nome completo."
        # o projeto roda com USE_I18N desligado, então as mensagens padrão do Django
        # sairiam em inglês no meio de um formulário em português
        for field in self.fields.values():
            field.error_messages.setdefault("required", "Campo obrigatório.")
            field.error_messages["invalid"] = "Valor inválido."
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxSelectMultiple):
                continue
            if isinstance(widget, forms.NullBooleanSelect):
                # o padrão do Django é "Unknown / Yes / No", em inglês e sem contexto
                widget.choices = [("unknown", "—"), ("true", "Sim"), ("false", "Não")]
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "checkbox checkbox-primary")
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", SELECT)
            elif isinstance(widget, forms.Textarea):
                widget.attrs.setdefault("class", TEXTAREA)
            elif isinstance(widget, forms.ClearableFileInput):
                widget.attrs.setdefault("class", "file-input file-input-bordered w-full")
            else:
                widget.attrs.setdefault("class", TEXT_INPUT)

    def clean_city(self) -> str:
        # mantém a mesma normalização usada na importação, para o geocoder achar o município
        from .normalization import normalize_city

        return normalize_city(self.cleaned_data.get("city", ""))

    def clean_residence_city(self) -> str:
        from .normalization import normalize_city

        return normalize_city(self.cleaned_data.get("residence_city", ""))

    def save(self, commit: bool = True) -> Researcher:
        """
        Resolve as coordenadas pelo cache local sempre que a cidade muda.

        Só o cache é consultado aqui - nada de chamada de rede no meio do request. Cidades
        que ainda não estão no cache ficam sem coordenada até rodar `geocode_researchers --online`.
        """
        from . import geocoding

        researcher = super().save(commit=False)
        cache = geocoding.load_cache()

        for prefix, city, state, country in (
            ("institution", researcher.city, researcher.state, researcher.country),
            ("residence", researcher.residence_city, researcher.residence_state, researcher.residence_country),
        ):
            field = "city" if prefix == "institution" else "residence_city"
            if field not in self.changed_data and getattr(researcher, f"{prefix}_latitude") is not None:
                continue
            coordinates = geocoding.lookup(city, state, country, cache=cache) if city else None
            setattr(researcher, f"{prefix}_latitude", coordinates[0] if coordinates else None)
            setattr(researcher, f"{prefix}_longitude", coordinates[1] if coordinates else None)

        if commit:
            researcher.save()
            self.save_m2m()
        return researcher
