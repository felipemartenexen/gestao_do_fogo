"""
Estatísticas do recorte atual, lidas das planilhas importadas.

O recorte segue a mesma regra do mapa - município > estado > bioma > Brasil - para que a
estatística responda exatamente à pergunta que a imagem está mostrando.

A planilha mensal não desce a município. Quando o recorte é um município, ela responde
pelo estado e diz isso em `escopo`, em vez de devolver vazio: a sazonalidade estadual
ainda informa o usuário, desde que a interface seja honesta sobre o que está somando.
"""

from django.db.models import Sum

from .catalog import MONTHS
from .models import BurnedAreaAnnual, BurnedAreaMonthly, FireRisk

# quantas categorias listar antes de agrupar o resto
TOPO = 8


def _recorte(queryset, *, biome: str, state: str, municipality: str, com_municipio: bool = True):
    """Aplica o recorte mais específico disponível e devolve (queryset, escopo, chave)."""
    if municipality and com_municipio:
        return queryset.filter(municipality_code=municipality), "municipio", municipality
    if state:
        return queryset.filter(state_code=state), "estado", state
    if biome:
        return queryset.filter(biome=biome), "bioma", biome
    return queryset, "brasil", ""


def _posicao(modelo, *, escopo: str, chave: str, biome: str, state: str, year: int, valor: float) -> dict | None:
    """
    Posição do recorte no ranking do ano, entre os seus pares.

    Um município é comparado aos municípios do mesmo estado; um estado, aos 27; um bioma,
    aos 6. Comparar um município a todos os 5.573 do país diria pouco.
    """
    if escopo == "municipio":
        pares = modelo.objects.filter(year=year, state_code=state).values("municipality_code")
        campo = "municipality_code"
    elif escopo == "estado":
        pares = modelo.objects.filter(year=year)
        if biome:
            pares = pares.filter(biome=biome)
        pares = pares.values("state_code")
        campo = "state_code"
    elif escopo == "bioma":
        pares = modelo.objects.filter(year=year).values("biome")
        campo = "biome"
    else:
        return None

    totais = pares.annotate(ha=Sum("area_ha")).order_by("-ha")
    for indice, linha in enumerate(totais, start=1):
        if linha[campo] == chave:
            return {"posicao": indice, "de": len(totais)}
    # o recorte não queimou nada no ano: fica fora do ranking, o que já é a informação
    return {"posicao": None, "de": len(totais)} if valor == 0 else None


def area_queimada(*, biome: str, state: str, municipality: str, year: int) -> dict:
    """Área queimada anual da Coleção 5: total do ano, série histórica, anomalia e ranking."""
    base, escopo, chave = _recorte(BurnedAreaAnnual.objects.all(), biome=biome, state=state, municipality=municipality)

    serie = list(base.values("year").annotate(ha=Sum("area_ha")).order_by("year"))
    if not serie:
        return {"disponivel": False, "motivo": "Sem dado para este recorte na planilha da Coleção 5."}

    por_ano = {linha["year"]: linha["ha"] for linha in serie}
    total = por_ano.get(year, 0.0)

    # a média exclui o ano em análise: comparar um ano consigo mesmo achata a anomalia
    historico = [ha for ano, ha in por_ano.items() if ano != year]
    media = sum(historico) / len(historico) if historico else 0.0
    anomalia = ((total / media) - 1) * 100 if media else None

    return {
        "disponivel": True,
        "escopo": escopo,
        "ano": year,
        "total_ha": total,
        "media_ha": media,
        "anomalia_pct": anomalia,
        "ranking": _posicao(
            BurnedAreaAnnual, escopo=escopo, chave=chave, biome=biome, state=state, year=year, valor=total
        ),
        "serie": [{"ano": linha["year"], "ha": linha["ha"]} for linha in serie],
    }


def monitor_fogo(*, biome: str, state: str, municipality: str, year: int) -> dict:
    """Monitor mensal: sazonalidade do ano e o que queimou, por classe de cobertura."""
    base, escopo, _ = _recorte(
        BurnedAreaMonthly.objects.all(),
        biome=biome,
        state=state,
        municipality=municipality,
        com_municipio=False,
    )
    do_ano = base.filter(year=year)
    meses = {linha["month"]: linha["ha"] for linha in do_ano.values("month").annotate(ha=Sum("area_ha"))}
    if not meses:
        return {"disponivel": False, "motivo": "Sem dado para este recorte na planilha mensal."}

    cobertura = list(do_ano.values("cover_class").annotate(ha=Sum("area_ha")).order_by("-ha")[:TOPO])
    origem = list(do_ano.values("cover_origin").annotate(ha=Sum("area_ha")).order_by("-ha"))

    return {
        "disponivel": True,
        # avisa a interface de que o município caiu para o estado, para ela poder dizer isso
        "escopo": escopo,
        "rebaixado": bool(municipality),
        "ano": year,
        "total_ha": sum(meses.values()),
        "meses": [{"mes": numero, "nome": nome, "ha": meses.get(numero, 0.0)} for numero, nome in MONTHS],
        "cobertura": [{"classe": linha["cover_class"], "ha": linha["ha"]} for linha in cobertura],
        "origem": [{"classe": linha["cover_origin"], "ha": linha["ha"]} for linha in origem],
    }


def focos_calor(**_) -> dict:
    """Sem planilha: os focos do FIRMS existem como camada, mas não como estatística agregada."""
    return {
        "disponivel": False,
        "motivo": "Os focos de calor vêm do FIRMS em tempo quase real e ainda não têm planilha consolidada.",
    }


def risco_potencial(*, biome: str, state: str, municipality: str, **_) -> dict:
    """
    Risco de fogo do IPAM, por classe e por malha fundiária.

    Atenção à unidade: aqui `ha` é território classificado por risco, não área queimada.
    A interface precisa rotular isso de forma diferente das outras abas, senão o número
    (dezenas de milhões de hectares) é lido como queimada.
    """
    base, escopo, _ = _recorte(FireRisk.objects.all(), biome=biome, state=state, municipality=municipality)
    if not base.exists():
        return {
            "disponivel": False,
            "motivo": "A análise do IPAM cobre Amazônia, Cerrado e Pantanal em 9 estados. Este recorte está fora.",
        }

    temporada = base.values_list("season", flat=True).first()
    classes = list(base.values("risk_class").annotate(ha=Sum("area_ha")).order_by("-ha"))
    fundiaria = list(base.values("tenure").annotate(ha=Sum("area_ha")).order_by("-ha")[:TOPO])

    return {
        "disponivel": True,
        "escopo": escopo,
        "temporada": temporada,
        "unidade": "território classificado",
        "total_ha": sum(linha["ha"] for linha in classes),
        "classes": [{"classe": linha["risk_class"], "ha": linha["ha"]} for linha in classes],
        "fundiaria": [{"categoria": linha["tenure"], "ha": linha["ha"]} for linha in fundiaria],
    }


CALCULADORAS = {
    "area_queimada": area_queimada,
    "monitor_fogo": monitor_fogo,
    "focos_calor": focos_calor,
    "risco_potencial": risco_potencial,
}
