"""Reglas que verifican una consulta interpretada (PLAN-TECNICO.md §6.3).

Dos conjuntos, compuestos de las mismas piezas (como `baseline`/`after` en QuickDev):

- `consulta-v1`: para lo que devuelve un INTERPRETE. Exige que cada filtro tenga
  respaldo literal en el texto del comprador.
- `filtros-v1`: para filtros que el comprador EDITA a mano (quitar una etiqueta).
  Ahi no hay texto que respalde: solo se comprueba que los ids existan y que los
  montos sean plausibles.

Las reglas solo detectan. Que se anula lo decide `PoliticaCorreccionConsulta`.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from umarket.busqueda.dominio.contrato import ConsultaInterpretada, Orden
from umarket.busqueda.dominio.parseo import parsear_montos
from umarket.compartido.dominio.reglas import ConjuntoReglas, Hallazgo, Regla, Severidad
from umarket.compartido.dominio.texto import contiene_literal

MONTO_MIN_COP = 500
MONTO_MAX_COP = 200_000
CANTIDAD_MAX = 20


@dataclass(frozen=True)
class ContextoConsulta:
    texto: str
    puntos: frozenset[str]
    franjas_abiertas: frozenset[str]


class MencionesLiterales:
    """Cada mencion del modelo aparece en el texto. Si no, el filtro no tiene respaldo."""

    id = "mencion_no_literal"

    def revisar(self, q: ConsultaInterpretada, c: ContextoConsulta) -> Iterable[Hallazgo]:
        for i, item in enumerate(q.items):
            if not contiene_literal(c.texto, item.mencion):
                yield Hallazgo(self.id, f"items.{i}", f"'{item.mencion}' no esta en el texto")
        for campo in ("precio", "franja", "punto"):
            mencion = getattr(q.menciones, campo)
            if mencion is not None and not contiene_literal(c.texto, mencion):
                yield Hallazgo(self.id, f"menciones.{campo}", f"'{mencion}' no esta en el texto")


class MontoConRespaldo:
    """Un precio o presupuesto debe ser un monto que el parser encuentra en el texto."""

    id = "monto_sin_respaldo"

    def revisar(self, q: ConsultaInterpretada, c: ContextoConsulta) -> Iterable[Hallazgo]:
        montos = {m.valor for m in parsear_montos(c.texto)}
        for campo in ("precio_max_unitario_cop", "presupuesto_total_cop"):
            valor = getattr(q, campo)
            if valor is not None and valor not in montos:
                yield Hallazgo(self.id, campo, f"{valor} no aparece como monto en el texto")


class MontoPlausible:
    id = "monto_implausible"

    def revisar(self, q: ConsultaInterpretada, c: ContextoConsulta) -> Iterable[Hallazgo]:
        for campo in ("precio_max_unitario_cop", "presupuesto_total_cop"):
            valor = getattr(q, campo)
            if valor is not None and not MONTO_MIN_COP <= valor <= MONTO_MAX_COP:
                yield Hallazgo(self.id, campo, f"{valor} no es un monto plausible")


class PuntoConocido:
    id = "punto_desconocido"

    def revisar(self, q: ConsultaInterpretada, c: ContextoConsulta) -> Iterable[Hallazgo]:
        if q.punto_id is not None and q.punto_id not in c.puntos:
            yield Hallazgo(self.id, "punto_id", f"{q.punto_id} no es un punto del campus")
        for candidato in q.punto_candidatos:
            if candidato not in c.puntos:
                yield Hallazgo(self.id, "punto_candidatos", f"{candidato} no es un punto")


class FranjaAbierta:
    id = "franja_cerrada"

    def revisar(self, q: ConsultaInterpretada, c: ContextoConsulta) -> Iterable[Hallazgo]:
        if q.franja_id is not None and q.franja_id not in c.franjas_abiertas:
            yield Hallazgo(self.id, "franja_id", f"{q.franja_id} no esta abierta hoy")


class CantidadRazonable:
    id = "cantidad_irrazonable"

    def revisar(self, q: ConsultaInterpretada, c: ContextoConsulta) -> Iterable[Hallazgo]:
        for i, item in enumerate(q.items):
            if item.cantidad is not None and not 1 <= item.cantidad <= CANTIDAD_MAX:
                yield Hallazgo(self.id, f"items.{i}.cantidad", f"{item.cantidad} unidades")


class ConsultaUtilizable:
    """Sin nada que buscar ni filtrar, la consulta no sirve: se usa el respaldo."""

    id = "consulta_inutilizable"

    def revisar(self, q: ConsultaInterpretada, c: ContextoConsulta) -> Iterable[Hallazgo]:
        if not q.es_busqueda:
            return
        tiene_items = any(i.termino or i.categoria or i.etiquetas for i in q.items)
        tiene_filtros = any(
            (q.precio_max_unitario_cop, q.presupuesto_total_cop, q.franja_id, q.punto_id,
             q.punto_candidatos)
        )  # fmt: skip
        if not (tiene_items or tiene_filtros):
            yield Hallazgo(self.id, "items", "no hay nada que buscar", Severidad.ADVERTENCIA)


class ConsultaUtilizableConOrden:
    """Como `ConsultaUtilizable`, pero un orden pedido ("lo mas barato") TAMBIEN es utilizable.

    Salio del primer eval con Gemini (2026-10-27): ante "lo mas barato que haya" el
    modelo respondio bien (orden=precio, sin items), y `consulta-v1` lo mando al
    respaldo, que no entiende "barato": cero resultados. Fallo la validacion, no el
    modelo. `consulta-v1` se conserva tal cual: es lo que se midio.
    """

    id = "consulta_inutilizable"

    def revisar(self, q: ConsultaInterpretada, c: ContextoConsulta) -> Iterable[Hallazgo]:
        if q.orden is not Orden.RELEVANCIA:
            return
        yield from ConsultaUtilizable().revisar(q, c)


type ReglaConsulta = Regla[ConsultaInterpretada, ContextoConsulta]

_VERSIONES: dict[str, tuple[ReglaConsulta, ...]] = {
    "consulta-v1": (
        MencionesLiterales(),
        MontoConRespaldo(),
        MontoPlausible(),
        PuntoConocido(),
        FranjaAbierta(),
        CantidadRazonable(),
        ConsultaUtilizable(),
    ),
    "consulta-v2": (
        MencionesLiterales(),
        MontoConRespaldo(),
        MontoPlausible(),
        PuntoConocido(),
        FranjaAbierta(),
        CantidadRazonable(),
        ConsultaUtilizableConOrden(),
    ),
    "filtros-v1": (
        MontoPlausible(),
        PuntoConocido(),
        FranjaAbierta(),
        CantidadRazonable(),
    ),
}


def reglas_consulta(version: str) -> ConjuntoReglas[ConsultaInterpretada, ContextoConsulta]:
    if version not in _VERSIONES:
        raise KeyError(f"No existe el conjunto '{version}'. Disponibles: {sorted(_VERSIONES)}")
    return ConjuntoReglas(version, _VERSIONES[version])
