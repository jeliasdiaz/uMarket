"""Normalizacion de texto.

Responsabilidad: una sola forma de comparar textos escritos por personas:
minusculas, sin tildes y con los espacios colapsados.

Es la misma funcion que calcula `productos.nombre_normalizado` en la base de
datos y la que usan las reglas que comprueban que una mencion del modelo aparece
en el texto del comprador. Si las dos normalizaran distinto, una regla podria
rechazar una mencion que la busqueda si encuentra.
"""

import re
import unicodedata

_ESPACIOS = re.compile(r"\s+")


def normalizar(texto: str) -> str:
    """Minusculas, sin tildes ni dieresis, con los espacios colapsados.

    La enie pasa a "n": "año" y "ano" se comparan igual. En busqueda de comida
    del campus eso no confunde nada y tolera teclados sin enie.
    """
    descompuesto = unicodedata.normalize("NFKD", texto)
    sin_marcas = "".join(c for c in descompuesto if not unicodedata.combining(c))
    return _ESPACIOS.sub(" ", sin_marcas.casefold()).strip()


def contiene_literal(texto: str, fragmento: str) -> bool:
    """True si `fragmento` aparece en `texto`, comparando ya normalizados.

    Un fragmento vacio nunca "aparece": aceptarlo dejaria pasar menciones vacias
    del modelo como si estuvieran respaldadas por el texto.
    """
    buscado = normalizar(fragmento)
    return bool(buscado) and buscado in normalizar(texto)
