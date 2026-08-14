"""
Importa as respostas do formulário "Mapeamento de pesquisadores de fogo no Brasil".

O comando é idempotente: rodar de novo atualiza os perfis existentes (casados pelo e-mail)
em vez de duplicar. Perfis editados pelo próprio pesquisador (source=self) nunca são
sobrescritos pela planilha.
"""

import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.researchers import normalization as N
from apps.researchers.models import (
    Biome,
    ProfileSource,
    ProfileStatus,
    ResearchArea,
    Researcher,
)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
LOCATIONS_PATH = DATA_DIR / "locations.json"

# Posição (1-based) de cada pergunta na planilha exportada pelo Google Forms.
COL = {
    "timestamp": 1,
    "email": 2,
    "name": 3,
    "consent": 4,
    "phone": 5,
    "origin_country": 6,
    "origin_state": 7,
    "residence_country": 8,
    "residence_state": 9,
    "gender": 10,
    "children": 11,
    "age_range": 12,
    "race": 13,
    "education": 16,
    "lattes": 17,
    "orcid": 18,
    "linkedin": 19,
    "sector": 20,
    "institution": 21,
    "state": 22,
    "city": 23,
    "position": 24,
    "main_area": 25,
    "fire_focused": 26,
    "years": 27,
    "brazil": 28,
    "other_territories": 29,
    "areas": 30,
    "biomes": 31,
    "research_description": 37,
    "develops_tech": 38,
    "tech_description": 39,
    "involves_communities": 40,
    "social_description": 44,
    "education_work": 45,
    "education_description": 48,
    "governance_description": 50,
    "publications": 52,
    "funding": 53,
    "partnerships": 55,
    "foreign_partnerships": 57,
    "outreach": 58,
}


class Command(BaseCommand):
    help = "Importa o CSV do formulário de mapeamento de pesquisadores de fogo."

    def add_arguments(self, parser) -> None:
        parser.add_argument("csv_path", type=str, help="Caminho do CSV exportado do Google Forms.")
        parser.add_argument("--dry-run", action="store_true", help="Só relata, não grava nada.")
        parser.add_argument(
            "--no-merge-names",
            action="store_true",
            help="Não unifica respostas com o mesmo nome quando os e-mails diferem.",
        )

    def handle(self, **options: Any) -> None:
        path = Path(options["csv_path"])
        if not path.exists():
            raise CommandError(f"CSV não encontrado: {path}")

        rows = self._read(path)
        self.stdout.write(f"{len(rows)} respostas lidas de {path.name}")

        deduped = self._dedupe(rows, merge_names=not options["no_merge_names"])
        locations = self._load_locations()
        self._ensure_taxonomies()

        created = updated = skipped = no_coords = 0
        with transaction.atomic():
            for row in deduped:
                result = self._upsert(row, locations, dry_run=options["dry_run"])
                if result == "created":
                    created += 1
                elif result == "updated":
                    updated += 1
                else:
                    skipped += 1
            if options["dry_run"]:
                transaction.set_rollback(True)

        if not options["dry_run"]:
            no_coords = Researcher.objects.public().filter(institution_latitude__isnull=True).count()

        consenting = sum(1 for r in deduped if N.normalize_bool(self._v(r, "consent")) is True)
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"criados: {created} | atualizados: {updated} | ignorados: {skipped}"))
        self.stdout.write(f"com autorização de divulgação: {consenting} de {len(deduped)}")
        if not options["dry_run"]:
            self.stdout.write(f"públicos sem coordenada (não entram no mapa): {no_coords}")
        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("dry-run: nada foi gravado"))

    # --- leitura e deduplicação ---------------------------------------------

    def _read(self, path: Path) -> list[dict]:
        with path.open(encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.DictReader(fh, delimiter=";"))
        if not rows:
            raise CommandError("CSV vazio.")
        self._cols = list(rows[0].keys())
        return rows

    def _v(self, row: dict, field: str) -> str:
        return (row[self._cols[COL[field] - 1]] or "").strip()

    def _timestamp(self, row: dict) -> datetime:
        raw = self._v(row, "timestamp")
        for fmt in ("%m/%d/%Y %H:%M:%S", "%d/%m/%Y %H:%M:%S"):
            try:
                return timezone.make_aware(datetime.strptime(raw, fmt))
            except ValueError:
                continue
        return timezone.now()

    def _dedupe(self, rows: list[dict], *, merge_names: bool) -> list[dict]:
        """Mantém sempre a resposta mais recente de cada pessoa."""
        by_email: dict[str, dict] = {}
        for row in rows:
            email = self._v(row, "email").lower()
            if not email:
                continue
            current = by_email.get(email)
            if current is None or self._timestamp(row) > self._timestamp(current):
                by_email[email] = row
        dropped_email = len(rows) - len(by_email)
        if dropped_email:
            self.stdout.write(f"  {dropped_email} respostas repetidas por e-mail descartadas (mantida a mais recente)")

        result = list(by_email.values())
        if not merge_names:
            return result

        by_name: dict[str, dict] = {}
        merged = []
        for row in result:
            name_key = re.sub(r"\s+", " ", N.strip_accents(self._v(row, "name")).strip().lower())
            current = by_name.get(name_key)
            if current is None:
                by_name[name_key] = row
            elif self._timestamp(row) > self._timestamp(current):
                merged.append((self._v(current, "name"), self._v(current, "email"), self._v(row, "email")))
                by_name[name_key] = row
            else:
                merged.append((self._v(row, "name"), self._v(row, "email"), self._v(current, "email")))
        for name, dropped, kept in merged:
            self.stdout.write(f"  mesmo nome com e-mails diferentes: {name} - descartado {dropped}, mantido {kept}")
        return list(by_name.values())

    # --- apoio ---------------------------------------------------------------

    def _load_locations(self) -> dict:
        if not LOCATIONS_PATH.exists():
            self.stdout.write(self.style.WARNING(f"sem tabela de coordenadas em {LOCATIONS_PATH} - mapa ficará vazio"))
            return {}
        return json.loads(LOCATIONS_PATH.read_text(encoding="utf-8"))

    def _ensure_taxonomies(self) -> None:
        for order, name in enumerate(N.CANONICAL_BIOMES):
            Biome.objects.get_or_create(
                name=name, defaults={"slug": N.strip_accents(name).lower().replace(" ", "-"), "order": order}
            )
        for order, name in enumerate(N.CANONICAL_AREAS):
            ResearchArea.objects.get_or_create(
                name=name,
                defaults={"slug": N.strip_accents(name).lower().replace(" ", "-")[:120], "order": order},
            )

    # --- gravação ------------------------------------------------------------

    def _upsert(self, row: dict, locations: dict, *, dry_run: bool) -> str:
        email = self._v(row, "email").lower()
        existing = Researcher.objects.filter(email=email).first()
        if existing and existing.source == ProfileSource.SELF:
            # o pesquisador já assumiu o perfil - a planilha não sobrescreve o que ele editou
            return "skipped"

        submitted_at = self._timestamp(row)
        city = N.normalize_city(self._v(row, "city"))
        state = N.normalize_uf(self._v(row, "state"))
        country = N.normalize_country(self._v(row, "residence_country"))
        coords = locations.get(f"{city}|{state}|{country}", {})

        # O formulário perguntou o país e o estado de residência, mas nunca a cidade -
        # por isso a moradia só ganha coordenadas quando o pesquisador atualiza o perfil.
        residence_state = N.normalize_uf(self._v(row, "residence_state"))
        residence_country = N.normalize_country(self._v(row, "residence_country"))

        fields = {
            "full_name": N.clean(self._v(row, "name")),
            "consent_public": N.normalize_bool(self._v(row, "consent")) is True,
            "status": ProfileStatus.APPROVED,
            "source": ProfileSource.FORM,
            "submitted_at": submitted_at,
            "institution": N.clean(self._v(row, "institution"))[:400],
            "sector": N.normalize_sector(self._v(row, "sector")),
            "position": N.clean(self._v(row, "position"))[:300],
            "education_level": N.normalize_education(self._v(row, "education")),
            "country": country,
            "state": state,
            "city": city,
            "institution_latitude": coords.get("lat"),
            "institution_longitude": coords.get("lon"),
            "residence_country": residence_country,
            "residence_state": residence_state,
            "main_research_area": N.clean(self._v(row, "main_area"))[:400],
            "fire_focused": N.normalize_bool(self._v(row, "fire_focused")),
            "years_researching": N.normalize_years(self._v(row, "years"), submitted_at.year),
            "years_researching_raw": N.clean(self._v(row, "years"))[:120],
            "focused_on_brazil": N.normalize_bool(self._v(row, "brazil")),
            "other_territories": N.clean(self._v(row, "other_territories"))[:400],
            "research_description": N.clean(self._v(row, "research_description")),
            "develops_technology": N.normalize_bool(self._v(row, "develops_tech")),
            "technology_description": N.clean(self._v(row, "tech_description")),
            "involves_communities": N.normalize_bool(self._v(row, "involves_communities")),
            "social_description": N.clean(self._v(row, "social_description")),
            "works_with_education": N.normalize_bool(self._v(row, "education_work")),
            "education_description": N.clean(self._v(row, "education_description")),
            "governance_description": N.clean(self._v(row, "governance_description")),
            "publications": N.clean(self._v(row, "publications")),
            "funding_sources": N.clean(self._v(row, "funding"))[:500],
            "partnerships": N.clean(self._v(row, "partnerships")),
            "foreign_partnerships": N.clean(self._v(row, "foreign_partnerships")),
            "outreach": N.clean(self._v(row, "outreach"))[:500],
            "lattes_url": N.normalize_url(self._v(row, "lattes"), expect="lattes"),
            "orcid_url": N.normalize_orcid(self._v(row, "orcid")),
            "linkedin_url": N.normalize_url(self._v(row, "linkedin"), expect="linkedin"),
            # dados restritos - não aparecem em nenhuma página pública
            "phone": N.normalize_phone(self._v(row, "phone")),
            "gender": N.clean(self._v(row, "gender"))[:60],
            "race": N.clean(self._v(row, "race"))[:60],
            "age_range": N.clean(self._v(row, "age_range"))[:40],
            "has_children": N.normalize_bool(self._v(row, "children")),
            "origin_country": N.normalize_country(self._v(row, "origin_country"))[:80],
            "origin_state": N.clean(self._v(row, "origin_state"))[:80],
        }

        if dry_run:
            return "updated" if existing else "created"

        researcher, created = Researcher.objects.update_or_create(email=email, defaults=fields)
        researcher.biomes.set(Biome.objects.filter(name__in=N.normalize_biomes(self._v(row, "biomes"))))
        researcher.research_areas.set(ResearchArea.objects.filter(name__in=N.normalize_areas(self._v(row, "areas"))))
        return "created" if created else "updated"
