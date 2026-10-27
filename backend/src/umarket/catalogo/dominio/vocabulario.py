"""El vocabulario cerrado del catalogo: categorias y etiquetas.

Es la UNICA fuente: la usan el formulario del vendedor, el SQL de la busqueda y
el contrato de salida del modelo de lenguaje (PLAN-TECNICO.md §6.2). Si el
modelo devuelve una categoria que no esta aqui, el tipo lo rechaza: no hace
falta una regla.

Cambiar el vocabulario es un cambio de contrato: version menor del esquema de
la busqueda y una migracion que actualice la restriccion CHECK de `productos`.
"""

from enum import StrEnum


class Categoria(StrEnum):
    EMPANADAS = "empanadas"
    AREPAS = "arepas"
    ALMUERZOS = "almuerzos"
    POSTRES = "postres"
    BEBIDAS = "bebidas"
    SNACKS = "snacks"
    FRUTAS = "frutas"
    OTROS = "otros"


class Etiqueta(StrEnum):
    DULCE = "dulce"
    SALADO = "salado"
    VEGETARIANO = "vegetariano"
    PICANTE = "picante"
    FRIO = "frio"
    CALIENTE = "caliente"


CATEGORIAS: tuple[str, ...] = tuple(c.value for c in Categoria)
ETIQUETAS: tuple[str, ...] = tuple(e.value for e in Etiqueta)
