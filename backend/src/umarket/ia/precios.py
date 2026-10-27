"""Cuanto cuesta una llamada.

QuickDev nunca midio el costo, y por eso "¿elegimos mal el modelo?" no se podia
responder. Aqui cada llamada calcula su costo y la traza lo guarda.

La tabla se mantiene A MANO y hay que verificarla contra la pagina de precios del
proveedor antes de usarla para decidir. Un modelo que no esta en la tabla
devuelve `None` ("sin precio"), no 0: un costo desconocido no es un costo cero.
"""

from umarket.ia.puerto import UsoTokens

# USD por millon de tokens: (entrada, salida). Los tokens de razonamiento se
# cobran como salida. Fuente: pagina de precios de Gemini API, a verificar.
PRECIOS_USD_POR_MILLON: dict[str, tuple[float, float]] = {
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gemini-2.5-flash": (0.30, 2.50),
}


def costo_usd(modelo: str, uso: UsoTokens) -> float | None:
    precio = PRECIOS_USD_POR_MILLON.get(modelo.removeprefix("models/"))
    if precio is None:
        return None
    entrada, salida = precio
    return (uso.entrada * entrada + (uso.salida + uso.razonamiento) * salida) / 1_000_000
