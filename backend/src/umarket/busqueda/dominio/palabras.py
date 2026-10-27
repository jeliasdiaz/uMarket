"""El interprete SIN IA: el baseline honesto contra el que se mide Gemini (D-05).

Es "lo mejor que se puede hacer sin modelo en poco codigo": palabras clave,
coincidencia exacta con el vocabulario cerrado y los parsers deterministas de
montos, horas, cantidades y puntos. No entiende intencion ("algo pa almorzar",
"algo sin carne"): eso es justo lo que se espera que aporte el modelo, y lo que
los evals miden.

Ademas es el RESPALDO: si el modelo falla, tarda o se agota el presupuesto, la
busqueda sigue con este interprete.
"""

import re

from umarket.busqueda.dominio.contrato import (
    ConsultaInterpretada,
    EntradaInterprete,
    ItemBuscado,
    Menciones,
)
from umarket.busqueda.dominio.parseo import (
    PALABRAS_VACIAS,
    Relacion,
    parsear_cantidades,
    parsear_hora,
    parsear_montos,
    puntos_mencionados,
)
from umarket.catalogo import Categoria, Etiqueta
from umarket.compartido.dominio.texto import normalizar

_CATEGORIAS = {c.value: c for c in Categoria}
_ETIQUETAS = {e.value: e for e in Etiqueta}


def _singular(palabra: str) -> str:
    if len(palabra) > 4 and palabra.endswith("es") and not palabra.endswith("ies"):
        return palabra[:-2] if palabra[-3] not in "aeiou" else palabra[:-1]
    if len(palabra) > 3 and palabra.endswith("s"):
        return palabra[:-1]
    return palabra


def _como_categoria(palabra: str) -> Categoria | None:
    return _CATEGORIAS.get(palabra) or _CATEGORIAS.get(palabra + "s")


def _mencion_literal(texto: str, palabras: list[str]) -> str:
    """El tramo del texto original que va de la primera a la ultima palabra util.

    Siempre es literal: la regla `MencionesLiterales` lo comprueba tambien para este
    interprete, y una mencion armada a mano (con espacios de mas) no pasaria.
    """
    inicio = texto.find(palabras[0])
    fin = texto.find(palabras[-1], inicio)
    if inicio == -1 or fin == -1:
        return palabras[0]
    return texto[inicio : fin + len(palabras[-1])]


def franja_para(hora: int | None, entrada: EntradaInterprete) -> str | None:
    """La franja abierta que corresponde a una hora; con hora None ('ya'), la primera abierta."""
    if not entrada.franjas_abiertas:
        return None
    if hora is None:
        return entrada.franjas_abiertas[0].id
    for f in entrada.franjas_abiertas:
        inicio, fin = int(f.inicio[:2]), int(f.fin[:2])
        if inicio <= hora <= fin:
            return f.id
    return None


def interpretar_por_palabras(entrada: EntradaInterprete) -> ConsultaInterpretada:
    texto = normalizar(entrada.texto)
    restante = texto

    # Montos
    precio_max = presupuesto = None
    mencion_precio = None
    for monto in parsear_montos(texto):
        if monto.relacion is Relacion.PRESUPUESTO:
            presupuesto = monto.valor
        else:
            precio_max = monto.valor
        mencion_precio = monto.fragmento
        restante = restante.replace(monto.fragmento, " ")

    # Hora
    franja_id = mencion_franja = None
    hora = parsear_hora(texto)
    if hora is not None:
        franja_id = franja_para(hora.hora, entrada)
        mencion_franja = hora.fragmento if franja_id else None
        restante = restante.replace(hora.fragmento, " ")

    # Puntos
    ids, mencion_punto = puntos_mencionados(
        texto, [(p.id, p.nombre, p.alias) for p in entrada.puntos]
    )
    punto_id = ids[0] if len(ids) == 1 else None
    candidatos = ids if len(ids) > 1 else []
    if mencion_punto:
        restante = restante.replace(mencion_punto, " ")

    # Items: un segmento por "y" o coma.
    cantidades = {cosa: n for n, cosa, _ in parsear_cantidades(restante)}
    items: list[ItemBuscado] = []
    for segmento in re.split(r",|\by\b", restante):
        palabras = [
            p for p in re.findall(r"[a-z]+", segmento) if p not in PALABRAS_VACIAS and len(p) > 2
        ]
        if not palabras:
            continue
        categoria: Categoria | None = None
        etiquetas: list[Etiqueta] = []
        terminos: list[str] = []
        cantidad: int | None = None
        for p in palabras:
            cantidad = cantidad or cantidades.get(p)
            if (c := _como_categoria(p)) is not None:
                categoria = c
            elif p in _ETIQUETAS:
                etiquetas.append(_ETIQUETAS[p])
            else:
                terminos.append(_singular(p))
        if categoria is not None and not terminos:
            terminos = [_singular(categoria.value)]
        items.append(
            ItemBuscado(
                termino=" ".join(terminos)[:40] or None,
                categoria=categoria,
                etiquetas=etiquetas,
                cantidad=cantidad,
                mencion=_mencion_literal(texto, palabras)[:120],
            )
        )

    # Sin modelo no se distingue un saludo de "algo pa comer": cualquier texto es una
    # busqueda, y sin filtros se muestra lo disponible hoy. Distinguir es trabajo del modelo.
    return ConsultaInterpretada(
        es_busqueda=bool(texto),
        items=items[:5],
        precio_max_unitario_cop=precio_max,
        presupuesto_total_cop=presupuesto,
        franja_id=franja_id,
        punto_id=punto_id,
        punto_candidatos=candidatos,
        menciones=Menciones(
            precio=mencion_precio, franja=mencion_franja, punto=mencion_punto or None
        ),
    )
