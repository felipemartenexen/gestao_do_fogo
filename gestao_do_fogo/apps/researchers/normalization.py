"""
Normalização das respostas do formulário de mapeamento.

O Google Forms deixou quase tudo como texto livre, então cada função aqui converte uma
resposta crua no valor canônico usado pelos modelos. Quando não dá para decidir com
segurança, devolvemos vazio/None em vez de chutar - o valor original fica guardado nos
campos `*_raw` ou é revisado no admin.
"""

import re
import unicodedata

from .models import EducationLevel, Sector

# --- helpers -----------------------------------------------------------------


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def key(text: str) -> str:
    """Chave de comparação: sem acento, minúscula, espaços colapsados."""
    return re.sub(r"\s+", " ", strip_accents(text or "").strip().lower())


def clean(text: str | None) -> str:
    """Colapsa espaços e remove espaços/pontuação solta nas bordas."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.replace(" ", " ")).strip().strip(",;").strip()


def first_of_multi(text: str) -> str:
    """Respostas com várias entradas ('SP; MG', 'Acre e SP') - fica com a primeira."""
    return re.split(r"[;,/]| e ", clean(text), maxsplit=1)[0].strip()


# --- UF ----------------------------------------------------------------------

_UF_BY_NAME = {
    "acre": "AC",
    "alagoas": "AL",
    "amapa": "AP",
    "amazonas": "AM",
    "bahia": "BA",
    "ceara": "CE",
    "distrito federal": "DF",
    "brasilia": "DF",
    "brasilia - df": "DF",
    "espirito santo": "ES",
    "goias": "GO",
    "go": "GO",
    "maranhao": "MA",
    "mato grosso": "MT",
    "mato grosso do sul": "MS",
    "minas gerais": "MG",
    "para": "PA",
    "paraiba": "PB",
    "parana": "PR",
    "pernambuco": "PE",
    "piaui": "PI",
    "rio de janeiro": "RJ",
    "rio grande do norte": "RN",
    "rio grande do sul": "RS",
    "rondonia": "RO",
    "roraima": "RR",
    "santa catarina": "SC",
    "sao paulo": "SP",
    "sergipe": "SE",
    "tocantins": "TO",
}
_UF_CODES = set(_UF_BY_NAME.values())

# valores que claramente não são uma UF brasileira.
# Respostas do tipo "atuo em todos os estados mas sou lotado em X" NÃO entram aqui:
# a lotação é justamente o que posiciona a pessoa no mapa, e a busca por substring resolve.
_NOT_A_UF = {
    "nacional",
    "n/a",
    "na",
    "instituto nacional de pesquisas da amazonia",
    "estados que compoem a amazonia e cerrado",
}


def normalize_uf(raw: str) -> str:
    """Devolve a sigla da UF, ou '' quando a resposta não identifica um estado brasileiro."""
    k = key(raw)
    if not k or k in _NOT_A_UF:
        return ""
    if k.upper() in _UF_CODES:
        return k.upper()
    if k in _UF_BY_NAME:
        return _UF_BY_NAME[k]
    # respostas compostas: "Mato Grosso, Mato Grosso do Sul", "SP; MG", "DF, CE"
    for piece in re.split(r"[;,/]|\se\s", raw or ""):
        pk = key(piece)
        if not pk:
            continue
        if pk.upper() in _UF_CODES:
            return pk.upper()
        if pk in _UF_BY_NAME:
            return _UF_BY_NAME[pk]
    # último recurso: nome de estado embutido em texto maior
    for name, uf in _UF_BY_NAME.items():
        if len(name) > 4 and name in k:
            return uf
    return ""


# --- país --------------------------------------------------------------------

_COUNTRY_ALIASES = {
    "brasil": "Brasil",
    "brazil": "Brasil",
    "brasil⁷": "Brasil",
    "bra": "Brasil",
    "uk": "Reino Unido",
    "united kingdom": "Reino Unido",
    "inglaterra": "Reino Unido",
    "reino unido": "Reino Unido",
    "escocia": "Reino Unido",
    "eua": "Estados Unidos",
    "estados unidos": "Estados Unidos",
    "usa": "Estados Unidos",
    "canada": "Canadá",
    "colombia": "Colômbia",
    "bolivia": "Bolívia",
    "espanha": "Espanha",
    "franca": "França",
    "italia": "Itália",
    "cuba": "Cuba",
    "japao": "Japão",
    "argentina": "Argentina",
    "alemanha": "Alemanha",
}


def normalize_country(raw: str) -> str:
    """'Brasil/SP' e 'BRASIL' viram 'Brasil'; vazio assume Brasil."""
    k = key(first_of_multi(raw))
    if not k:
        return "Brasil"
    if k in _COUNTRY_ALIASES:
        return _COUNTRY_ALIASES[k]
    # grafias truncadas ('Bras', 'Brasi') e quem preencheu o estado no campo país
    if k.startswith("bras") or normalize_uf(k):
        return "Brasil"
    return clean(raw).split("/")[0].strip().title()


# --- município ---------------------------------------------------------------

_CITY_ALIASES = {
    "brasilia - df": "Brasília",
    "brasilia-df": "Brasília",
    "brasilia -df": "Brasília",
    "brasilia df": "Brasília",
    "belem": "Belém",
    "brasilia": "Brasília",
    "goiania": "Goiânia",
    "cuiaba": "Cuiabá",
    "sao paulo": "São Paulo",
    "maceio": "Maceió",
    "vitoria": "Vitória",
    "florianopolis": "Florianópolis",
    "sao jose dos campos": "São José dos Campos",
    "sao carlos": "São Carlos",
    "sao goncalo": "São Gonçalo",
    "sao luis": "São Luís",
    "seropedica": "Seropédica",
    "vicosa": "Viçosa",
    "anapolis": "Anápolis",
    "niteroi": "Niterói",
    "macapa": "Macapá",
    "santarem": "Santarém",
}

# respostas que não são um município utilizável
_NOT_A_CITY = {"", "n/a", "na", "nsa", "-", ".", "varios", "varias", "nacional", "xxx"}


def normalize_city(raw: str) -> str:
    """Fica com o primeiro município citado e corrige acentuação das grafias mais comuns."""
    candidate = first_of_multi(raw)
    k = key(candidate)
    if k in _NOT_A_CITY:
        return ""
    if k in _CITY_ALIASES:
        return _CITY_ALIASES[k]
    # remove sufixo de UF colado: "Belo Horizonte - MG"
    candidate = re.sub(r"\s*[-–]\s*[A-Za-z]{2}\s*$", "", candidate).strip()
    k = key(candidate)
    if k in _CITY_ALIASES:
        return _CITY_ALIASES[k]
    if k in _NOT_A_CITY:
        return ""
    return candidate[:120]


# --- sim / não ---------------------------------------------------------------


def normalize_bool(raw: str) -> bool | None:
    k = key(raw)
    if k.startswith("sim"):
        return True
    if k.startswith("nao") or k == "n":
        return False
    return None


# --- setor -------------------------------------------------------------------


def normalize_sector(raw: str) -> str:
    """
    O campo aceitava múltipla escolha. Quando há mais de um setor, priorizamos
    público > terceiro > privado > internacional, que é a ordem de especificidade
    institucional usada no relatório da rede.
    """
    k = key(raw)
    if not k:
        return ""
    if "setor publico" in k:
        return Sector.PUBLIC
    if "terceiro setor" in k:
        return Sector.THIRD
    if "setor privado" in k:
        return Sector.PRIVATE
    if "organismo internacional" in k or "undp" in k:
        return Sector.INTERNATIONAL
    if "universidade" in k:
        return Sector.PUBLIC
    return Sector.OTHER


# --- formação ----------------------------------------------------------------

_EDUCATION = {
    "doutorado": EducationLevel.PHD,
    "doutorado em andamento": EducationLevel.PHD_ONGOING,
    "mestrado": EducationLevel.MASTERS,
    "mestrado em andamento": EducationLevel.MASTERS_ONGOING,
    "ensino superior completo": EducationLevel.UNDERGRAD,
    "ensino superior incompleto": EducationLevel.UNDERGRAD_ONGOING,
    "ensino basico completo": EducationLevel.BASIC,
}


def normalize_education(raw: str) -> str:
    return _EDUCATION.get(key(raw), "")


# --- tempo de pesquisa -------------------------------------------------------

_WORD_NUMBERS = {
    "um": 1,
    "uma": 1,
    "dois": 2,
    "duas": 2,
    "tres": 3,
    "quatro": 4,
    "cinco": 5,
    "seis": 6,
    "sete": 7,
    "oito": 8,
    "nove": 9,
    "dez": 10,
    "onze": 11,
    "doze": 12,
    "quinze": 15,
    "vinte": 20,
    "trinta": 30,
}


def normalize_years(raw: str, reference_year: int) -> int | None:
    """
    Converte 'há 3 anos', 'Dois anos', 'desde 2015', '6 meses' em número de anos.

    `reference_year` é o ano da resposta - usado quando a pessoa informou o ano de início
    em vez da duração. Devolve None quando não dá para inferir com segurança.
    """
    k = key(raw)
    if not k:
        return None

    # ano de início: "desde 2015", "2006", "a partir de 2020"
    year_match = re.search(r"\b(19[5-9]\d|20[0-2]\d)\b", k)
    if year_match:
        start = int(year_match.group(1))
        if start <= reference_year:
            return reference_year - start

    if "mes" in k and "ano" not in k:  # "6 meses", "poucas semanas" -> menos de um ano
        return 0
    if "semana" in k or "dia" in k:
        return 0

    number_match = re.search(r"\b(\d{1,2})\b", k)
    if number_match:
        value = int(number_match.group(1))
        return value if 0 <= value <= 70 else None

    for word, value in _WORD_NUMBERS.items():
        if re.search(rf"\b{word}\b", k):
            return value
    return None


# --- telefone ----------------------------------------------------------------


def normalize_phone(raw: str) -> str:
    """
    Descarta os números que o Excel converteu em notação científica (5,52199E+12) -
    esses dígitos foram perdidos e não dá para reconstruir o número.
    """
    text = clean(raw)
    if not text or re.search(r"[Ee]\+\d", text):
        return ""
    return text[:60]


# --- multi-seleção -----------------------------------------------------------


def split_multi(raw: str) -> list[str]:
    """
    Separa uma resposta de múltipla escolha em itens.

    Cuidado: algumas opções do formulário têm vírgula dentro do próprio rótulo
    (ex.: 'Outras áreas protegidas (e.g., APP, FLONA)'), então ignoramos vírgulas
    que estejam dentro de parênteses.
    """
    text = clean(raw)
    if not text:
        return []
    items, buffer, depth = [], [], 0
    for char in text:
        if char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        if char == "," and depth == 0:
            items.append("".join(buffer).strip())
            buffer = []
        else:
            buffer.append(char)
    items.append("".join(buffer).strip())
    return [i for i in items if i]


# --- biomas ------------------------------------------------------------------

CANONICAL_BIOMES = ["Amazônia", "Cerrado", "Caatinga", "Mata Atlântica", "Pampa", "Pantanal"]

_BIOME_LOOKUP = {key(b): b for b in CANONICAL_BIOMES}
_BIOME_LOOKUP.update({"amazona": "Amazônia", "amazonia": "Amazônia", "mata atlantica": "Mata Atlântica"})


def normalize_biomes(raw: str) -> list[str]:
    """
    Extrai os biomas canônicos. Respostas livres ('Todos', 'Temos os trez bioma',
    'Transação dos biomas Cerrado e Amazonia') são resolvidas por busca de substring.
    """
    text = key(raw)
    if not text:
        return []
    if "todos" in text and len(text) < 30:
        return list(CANONICAL_BIOMES)
    found = []
    for k, canonical in _BIOME_LOOKUP.items():
        if k in text and canonical not in found:
            found.append(canonical)
    return [b for b in CANONICAL_BIOMES if b in found]


# --- áreas de atuação --------------------------------------------------------

CANONICAL_AREAS = [
    "Ecológica e ambiental",
    "Desenvolvimento de modelos e tecnologias relacionadas ao fogo",
    "Governança e políticas públicas",
    "Educação ambiental",
    "Sociedade e economia",
    "Saúde",
]

_AREA_LOOKUP = {key(a): a for a in CANONICAL_AREAS}


def normalize_areas(raw: str) -> list[str]:
    found = []
    for item in split_multi(raw):
        canonical = _AREA_LOOKUP.get(key(item))
        if canonical and canonical not in found:
            found.append(canonical)
    return [a for a in CANONICAL_AREAS if a in found]


# --- links -------------------------------------------------------------------


def normalize_orcid(raw: str) -> str:
    """Aceita '0000-0002-...' ou a URL inteira e devolve sempre a URL canônica."""
    text = clean(raw)
    match = re.search(r"(\d{4}-\d{4}-\d{4}-\d{3}[\dXx])", text)
    if match:
        return f"https://orcid.org/{match.group(1).upper()}"
    return "" if not text.lower().startswith("http") else text[:200]


def normalize_url(raw: str, *, expect: str = "") -> str:
    """Descarta respostas que não são URL (nome da pessoa, 'não tenho', etc.)."""
    text = clean(raw)
    if not text:
        return ""
    lowered = text.lower()
    if lowered.startswith(("http://", "https://")):
        return text[:500]
    if expect and expect in lowered:
        return f"https://{text.lstrip('/')}"[:500]
    if re.fullmatch(r"\d{8,20}", text) and expect == "lattes":
        return f"http://lattes.cnpq.br/{text}"
    return ""
