"""Lo que el comprador ve como "Entendimos: dulce · hasta $5.000 · 12:00".

Cada etiqueta lleva el `campo` que la produjo, para que la interfaz pueda quitarla
y volver a buscar SIN llamar al modelo (PLAN-TECNICO.md §6.5).
"""

from dataclasses import dataclass

from umarket.busqueda.dominio.contrato import ConsultaInterpretada, Orden


@dataclass(frozen=True)
class Filtro:
    campo: str
    etiqueta: str


def _pesos(valor: int) -> str:
    return f"${valor:,}".replace(",", ".")


def describir(
    q: ConsultaInterpretada, puntos: dict[str, str], franjas: dict[str, str]
) -> list[Filtro]:
    filtros: list[Filtro] = []
    for i, item in enumerate(q.items):
        partes: list[str] = []
        if item.cantidad:
            partes.append(f"{item.cantidad} ×")
        if item.termino:
            partes.append(item.termino)
        elif item.categoria:
            partes.append(item.categoria.value)
        partes.extend(e.value for e in item.etiquetas if e.value not in partes)
        if partes:
            filtros.append(Filtro(f"items.{i}", " ".join(partes)))
    if q.precio_max_unitario_cop:
        filtros.append(
            Filtro("precio_max_unitario_cop", f"hasta {_pesos(q.precio_max_unitario_cop)}")
        )
    if q.presupuesto_total_cop:
        filtros.append(
            Filtro("presupuesto_total_cop", f"presupuesto {_pesos(q.presupuesto_total_cop)}")
        )
    if q.franja_id:
        filtros.append(Filtro("franja_id", franjas.get(q.franja_id, q.franja_id)))
    if q.punto_id:
        filtros.append(Filtro("punto_id", puntos.get(q.punto_id, q.punto_id)))
    if q.orden is not Orden.RELEVANCIA:
        filtros.append(
            Filtro("orden", "mas barato" if q.orden is Orden.PRECIO else "mejor calificado")
        )
    return filtros


def quitar(q: ConsultaInterpretada, campo: str) -> ConsultaInterpretada:
    """La consulta sin ese filtro. Lo que hace la interfaz al tocar la X de una etiqueta."""
    datos = q.model_dump()
    if campo.startswith("items."):
        indice = int(campo.split(".")[1])
        datos["items"] = [it for i, it in enumerate(datos["items"]) if i != indice]
    elif campo == "orden":
        datos["orden"] = Orden.RELEVANCIA
    elif campo in datos:
        datos[campo] = None
    return ConsultaInterpretada.model_validate(datos)
