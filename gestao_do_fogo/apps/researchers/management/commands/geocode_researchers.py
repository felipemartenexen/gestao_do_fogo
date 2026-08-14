"""
Preenche as coordenadas que faltam nos perfis (instituição e moradia).

Rode depois que pesquisadores atualizarem o perfil com cidades ainda não conhecidas.
Sem `--online` o comando usa apenas o cache versionado e não acessa a rede.
"""

from typing import Any

from django.core.management.base import BaseCommand

from apps.researchers import geocoding
from apps.researchers.models import Researcher


class Command(BaseCommand):
    help = "Resolve coordenadas faltantes dos perfis de pesquisadores."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--online",
            action="store_true",
            help="Consulta o Nominatim para locais fora do cache (1 requisição por segundo).",
        )
        parser.add_argument("--dry-run", action="store_true", help="Só relata, não grava.")

    def handle(self, **options: Any) -> None:
        online = options["online"]
        dry_run = options["dry_run"]
        cache = geocoding.load_cache()
        cache_dirty = False
        resolved = unresolved = 0

        targets = Researcher.objects.filter(institution_latitude__isnull=True) | Researcher.objects.filter(
            residence_latitude__isnull=True, residence_city__gt=""
        )
        targets = targets.distinct()
        self.stdout.write(f"{targets.count()} perfis com coordenada faltando")

        for researcher in targets:
            updates = {}

            for prefix, city, state, country in (
                ("institution", researcher.city, researcher.state, researcher.country),
                (
                    "residence",
                    researcher.residence_city,
                    researcher.residence_state,
                    researcher.residence_country,
                ),
            ):
                if getattr(researcher, f"{prefix}_latitude") is not None or not city:
                    continue
                coordinates, changed = geocoding.resolve(city, state, country, allow_online=online, cache=cache)
                cache_dirty = cache_dirty or changed
                if coordinates:
                    updates[f"{prefix}_latitude"] = coordinates[0]
                    updates[f"{prefix}_longitude"] = coordinates[1]
                    resolved += 1
                    self.stdout.write(f"  {researcher.full_name}: {prefix} -> {coordinates}")
                else:
                    unresolved += 1
                    self.stdout.write(
                        self.style.WARNING(f"  {researcher.full_name}: {prefix} sem resultado para {city!r}")
                    )

            if updates and not dry_run:
                for field, value in updates.items():
                    setattr(researcher, field, value)
                researcher.save(update_fields=[*updates, "updated_at"])

        if cache_dirty and not dry_run:
            geocoding.save_cache(cache)
            self.stdout.write("cache de locais atualizado")

        self.stdout.write(self.style.SUCCESS(f"resolvidos: {resolved} | sem resultado: {unresolved}"))
        if not online and unresolved:
            self.stdout.write("rode de novo com --online para buscar os locais que faltam")
