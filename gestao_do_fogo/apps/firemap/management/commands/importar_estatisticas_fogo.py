"""Carrega as planilhas de `apps/firemap/data/` nas tabelas de estatística."""

from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.firemap import importers

LOTE = 5000


class Command(BaseCommand):
    help = "Importa as planilhas de estatística de fogo de apps/firemap/data/."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--pasta",
            default=str(importers.DATA_DIR),
            help="Pasta com os CSV (padrão: apps/firemap/data/).",
        )
        parser.add_argument(
            "--conferir",
            action="store_true",
            help="Só diagnostica: mostra o que cada arquivo é e o que não cruzaria, sem gravar.",
        )

    def handle(self, *args, **options) -> None:
        pasta = Path(options["pasta"])
        arquivos = sorted(pasta.glob("*.csv"))
        if not arquivos:
            self.stdout.write(self.style.WARNING(f"Nenhum CSV em {pasta}."))
            return

        reconhecidos = []
        for arquivo in arquivos:
            planilha = importers.reconhecer(arquivo)
            if planilha is None:
                self.stdout.write(self.style.ERROR(f"✗ {arquivo.name}: cabeçalho não reconhecido"))
                continue
            self.stdout.write(f"✓ {arquivo.name} → {planilha.nome}")
            reconhecidos.append((arquivo, planilha))

        if not reconhecidos:
            self.stdout.write(self.style.ERROR("Nenhuma planilha reconhecida. Veja o README da pasta."))
            return

        # a malha do IBGE vem do Earth Engine e é cara; uma vez por execução basta
        self.stdout.write("Carregando a malha do IBGE…")
        referencia = importers.Referencia()
        self.stdout.write(f"  {len(referencia.municipios)} municípios, {len(referencia.uf_por_sigla)} UF")

        for arquivo, planilha in reconhecidos:
            self._importar(arquivo, planilha, referencia, conferir=options["conferir"])

    def _importar(self, arquivo: Path, planilha, referencia, *, conferir: bool) -> None:
        avisos: list[str] = []
        registros = planilha.leitor(arquivo, referencia, avisos)

        if conferir:
            total = sum(1 for _ in registros)
            self.stdout.write(f"\n{planilha.nome}: {total:,} linhas aproveitáveis".replace(",", "."))
            self._relatar(avisos)
            return

        with transaction.atomic():
            planilha.modelo.objects.all().delete()
            total = 0
            lote: list = []
            for registro in registros:
                lote.append(registro)
                if len(lote) >= LOTE:
                    planilha.modelo.objects.bulk_create(lote)
                    total += len(lote)
                    lote = []
            if lote:
                planilha.modelo.objects.bulk_create(lote)
                total += len(lote)

        self.stdout.write(self.style.SUCCESS(f"\n{planilha.nome}: {total:,} registros".replace(",", ".")))
        self._relatar(avisos)

    def _relatar(self, avisos: list[str]) -> None:
        if not avisos:
            return
        unicos = sorted(set(avisos))
        self.stdout.write(self.style.WARNING(f"  {len(avisos)} linhas ignoradas, {len(unicos)} motivos distintos:"))
        for aviso in unicos[:20]:
            self.stdout.write(f"    - {aviso}")
        if len(unicos) > 20:
            self.stdout.write(f"    … e mais {len(unicos) - 20}")
