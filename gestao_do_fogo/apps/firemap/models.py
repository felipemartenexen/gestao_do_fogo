"""
Estatísticas de fogo já consolidadas, por recorte territorial.

Estes números não vêm do Earth Engine. Calcular área queimada com `reduceRegion` a cada
requisição custa dezenas de segundos por recorte, e a rede já publica as planilhas
consolidadas (MapBiomas Fogo Coleção 5 e a análise de risco do IPAM). Guardar essas
planilhas em tabela dá resposta em milissegundos e mantém o site citando exatamente os
mesmos números dos relatórios.

As planilhas ficam em `apps/firemap/data/` e entram por `manage.py importar_estatisticas_fogo`.
"""

from django.db import models

from apps.utils.models import BaseModel


class TerritorialStat(BaseModel):
    """
    Campos de recorte comuns às três planilhas.

    Os códigos são os do IBGE porque é com eles que o mapa filtra: o front manda o mesmo
    `bioma`/`uf`/`municipio` que usa para recortar a geometria no Earth Engine, e a
    estatística precisa responder à mesma pergunta sem tradução no meio.
    """

    biome = models.CharField("bioma", max_length=32, db_index=True)
    state_code = models.CharField("código da UF", max_length=2, db_index=True)
    state_uf = models.CharField("sigla da UF", max_length=2)
    area_ha = models.FloatField("área em hectares")

    class Meta:
        abstract = True


class BurnedAreaAnnual(TerritorialStat):
    """Área queimada por ano, bioma, UF e município (MapBiomas Fogo, Coleção 5)."""

    year = models.PositiveSmallIntegerField("ano", db_index=True)
    municipality_code = models.CharField("código do município", max_length=7, db_index=True)
    municipality_name = models.CharField("município", max_length=120)

    class Meta:
        verbose_name = "área queimada anual"
        verbose_name_plural = "áreas queimadas anuais"
        indexes = [
            models.Index(fields=["year", "biome"]),
            models.Index(fields=["year", "state_code"]),
            models.Index(fields=["year", "municipality_code"]),
        ]

    def __str__(self) -> str:
        return f"{self.municipality_name}/{self.state_uf} {self.year}: {self.area_ha:.0f} ha"


class BurnedAreaMonthly(TerritorialStat):
    """
    Área queimada por mês, bioma, UF e classe de cobertura.

    Não desce a município: a planilha mensal do MapBiomas para em UF, e é ela que sustenta
    a leitura de sazonalidade e de "o que queimou" (pastagem, floresta, agricultura).
    """

    year = models.PositiveSmallIntegerField("ano", db_index=True)
    month = models.PositiveSmallIntegerField("mês")
    cover_origin = models.CharField("origem da cobertura", max_length=32)  # Natural / Antrópico
    cover_class = models.CharField("classe de cobertura", max_length=64)  # Nível 1: Floresta, Pastagem...
    cover_detail = models.CharField("detalhe da cobertura", max_length=64)  # Nível 2

    class Meta:
        verbose_name = "área queimada mensal"
        verbose_name_plural = "áreas queimadas mensais"
        indexes = [
            models.Index(fields=["year", "biome"]),
            models.Index(fields=["year", "state_code"]),
        ]

    def __str__(self) -> str:
        return f"{self.state_uf} {self.month:02d}/{self.year} {self.cover_class}: {self.area_ha:.0f} ha"


class FireRisk(TerritorialStat):
    """
    Risco de fogo por município e malha fundiária (IPAM).

    Sem coluna de ano: a planilha é uma projeção para uma temporada, e o arquivo de origem
    carrega o ano no nome. `season` guarda esse ano para a interface poder dizer de quando é.
    """

    season = models.PositiveSmallIntegerField("temporada", db_index=True)
    municipality_code = models.CharField("código do município", max_length=7, db_index=True)
    municipality_name = models.CharField("município", max_length=120)
    tenure = models.CharField("categoria fundiária", max_length=64)
    jurisdiction = models.CharField("jurisdição", max_length=32)
    risk_class = models.CharField("classe de risco", max_length=8)

    class Meta:
        verbose_name = "risco de fogo"
        verbose_name_plural = "riscos de fogo"
        indexes = [
            models.Index(fields=["season", "biome"]),
            models.Index(fields=["season", "state_code"]),
            models.Index(fields=["season", "municipality_code"]),
        ]

    def __str__(self) -> str:
        return f"{self.municipality_name}/{self.state_uf} {self.risk_class}: {self.area_ha:.0f} ha"
