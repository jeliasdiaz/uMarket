"""Parsers deterministas del texto del comprador: montos, horas, cantidades y puntos.

Los usan dos piezas, y por eso viven aqui:
  1. El interprete SIN IA (el baseline), que con ellos arma la consulta.
  2. Las reglas que VERIFICAN al modelo: un precio que el modelo devuelve debe
     coincidir con un monto que estos parsers encuentran en el texto.

Trabajan sobre texto ya normalizado (minusculas, sin tildes).
"""

import re
from dataclasses import dataclass
from enum import StrEnum

from umarket.compartido.dominio.texto import normalizar

NUMEROS_EN_PALABRAS = {
    "un": 1,
    "una": 1,
    "uno": 1,
    "dos": 2,
    "tres": 3,
    "cuatro": 4,
    "cinco": 5,
    "seis": 6,
    "siete": 7,
    "ocho": 8,
    "nueve": 9,
    "diez": 10,
    "doce": 12,
    "quince": 15,
    "veinte": 20,
}


PALABRAS_VACIAS = frozenset(
    [
        "a",
        "al",
        "algo",
        "alguna",
        "alguno",
        "de",
        "del",
        "el",
        "en",
        "la",
        "las",
        "lo",
        "los",
        "me",
        "mi",
        "para",
        "pa",
        "por",
        "que",
        "quiero",
        "dame",
        "deme",
        "regalame",
        "guardas",
        "guarda",
        "tienes",
        "tiene",
        "hay",
        "venden",
        "vende",
        "busco",
        "necesito",
        "un",
        "una",
        "uno",
        "unos",
        "unas",
        "y",
        "o",
        "con",
        "sin",
        "mas",
        "menos",
        "hasta",
        "maximo",
        "como",
        "tipo",
        "cerca",
        "ya",
        "ahora",
        "favor",
        "porfa",
        "porfavor",
        "hola",
        "buenas",
        "mil",
        "pesos",
        "lucas",
        "luca",
        "k",
        "tengo",
        "comer",
        "tomar",
        "antojo",
        "antoja",
        "provoca",
        "gustaria",
        "quisiera",
        "pues",
        "bueno",
        "tan",
        "barato",
        "rico",
        "rica",
        "media",
        "docena",
    ]
)


class Relacion(StrEnum):
    MAXIMO = "maximo"
    PRESUPUESTO = "presupuesto"


@dataclass(frozen=True)
class Monto:
    valor: int
    fragmento: str
    relacion: Relacion


_MONTO = re.compile(
    r"(?P<pre>\$\s*)?"
    r"(?P<num>\d{1,3}(?:[.,]\d{3})+|\d+(?:[.,]\d)?|"
    + "|".join(NUMEROS_EN_PALABRAS)
    + r")\s*(?P<mult>mil\b|k\b|lucas?\b|pesos\b)?"
)
_PRESUPUESTO = re.compile(r"(tengo|con|presupuesto|me alcanza|cargo)\s*(de\s*)?$")


def _valor(num: str, mult: str | None, signo: bool) -> int | None:
    if num in NUMEROS_EN_PALABRAS:
        base = float(NUMEROS_EN_PALABRAS[num])
        if mult not in ("mil", "k", "luca", "lucas"):
            return None  # "dos" solo es una cantidad, no plata
    elif re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", num):
        base = float(re.sub(r"[.,]", "", num))
    else:
        base = float(num.replace(",", "."))
    if mult in ("mil", "k", "luca", "lucas"):
        return int(base * 1000)
    if mult == "pesos" or signo or base >= 100:
        return int(base)
    return None  # "a las 12", "2 empanadas": no es plata


def parsear_montos(texto: str) -> list[Monto]:
    t = normalizar(texto)
    montos: list[Monto] = []
    for m in _MONTO.finditer(t):
        valor = _valor(m["num"], m["mult"], bool(m["pre"]))
        if valor is None:
            continue
        antes = t[max(0, m.start() - 20) : m.start()]
        relacion = Relacion.PRESUPUESTO if _PRESUPUESTO.search(antes) else Relacion.MAXIMO
        montos.append(Monto(valor, m.group(0).strip(), relacion))
    return montos


# -- horas -------------------------------------------------------------------

_HORA = re.compile(
    r"\b(?:a|pa|para|tipo|como a|antes de)?\s*las?\s+(?P<h>\d{1,2})(?::(?P<m>\d{2}))?"
    r"(?:\s*(?P<sufijo>m\b|pm\b|am\b|de la tarde|de la manana))?"
    r"|\b(?P<h2>\d{1,2}):(?P<m2>\d{2})\b"
)
_YA = re.compile(r"\b(pa ya|para ya|ya mismo|de una|ahora|ahorita)\b")


@dataclass(frozen=True)
class HoraMencionada:
    hora: int | None  # None = "ya" (la franja abierta mas proxima)
    fragmento: str


def parsear_hora(texto: str) -> HoraMencionada | None:
    t = normalizar(texto)
    ya = _YA.search(t)
    if ya:
        return HoraMencionada(None, ya.group(0))
    m = _HORA.search(t)
    if m is None:
        return None
    h = int(m["h"] or m["h2"])
    sufijo = m["sufijo"] or ""
    if ("tarde" in sufijo or sufijo == "pm" or 1 <= h <= 6) and h < 12:
        h += 12
    if not 0 <= h <= 23:
        return None
    return HoraMencionada(h, m.group(0).strip())


# -- cantidades ----------------------------------------------------------------

_CANTIDAD = re.compile(
    r"\b(?P<n>\d{1,2}|" + "|".join(NUMEROS_EN_PALABRAS) + r"|media docena|docena)\s+(?:de\s+)?"
    r"(?P<cosa>[a-z]{3,})"
)


def parsear_cantidades(texto: str) -> list[tuple[int, str, str]]:
    """[(cantidad, palabra siguiente, fragmento)]: '2 de pollo' -> (2, 'pollo', '2 de pollo')."""
    t = normalizar(texto)
    resultado: list[tuple[int, str, str]] = []
    for m in _CANTIDAD.finditer(t):
        n = m["n"]
        if n == "media docena":
            valor = 6
        elif n == "docena":
            valor = 12
        elif n.isdigit():
            valor = int(n)
        else:
            valor = NUMEROS_EN_PALABRAS[n]
        if m["cosa"] in PALABRAS_VACIAS or m["cosa"] in ("mil", "pesos", "lucas", "luca"):
            continue
        resultado.append((valor, m["cosa"], m.group(0)))
    return resultado


# -- puntos --------------------------------------------------------------------


def puntos_mencionados(
    texto: str, puntos: list[tuple[str, str, list[str]]]
) -> tuple[list[str], str]:
    """Los puntos (id, nombre, alias) que el texto menciona por nombre o alias.

    Devuelve los ids y el fragmento que los menciono. Si son varios, la consulta
    los declara como candidatos: el codigo no adivina.
    """
    t = normalizar(texto)
    encontrados: list[str] = []
    fragmento = ""
    for pid, nombre, alias in puntos:
        for forma in (nombre, *alias):
            f = normalizar(forma)
            if f and re.search(rf"\b{re.escape(f)}\b", t):
                if pid not in encontrados:
                    encontrados.append(pid)
                fragmento = fragmento or f
                break
    return encontrados, fragmento
