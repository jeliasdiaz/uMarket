"""Que se hace con cada hallazgo: ANULAR el filtro, no bloquear la busqueda.

Un filtro equivocado esconde resultados validos; anularlo muestra de mas, y el
comprador ve los filtros y decide. Inventar una restriccion es peor que omitirla
(PLAN-TECNICO.md §6.3). Es la unica pieza que modifica una consulta, y se lee de
una sentada (patron `RepairPolicy` de QuickDev, ADR-0004).

| regla_id              | correccion                                          |
|-----------------------|-----------------------------------------------------|
| mencion_no_literal    | se quita el item, o el filtro de esa mencion        |
| monto_sin_respaldo    | precio / presupuesto a null                         |
| monto_implausible     | precio / presupuesto a null                         |
| punto_desconocido     | punto y candidatos desconocidos fuera               |
| franja_cerrada        | franja a null                                       |
| cantidad_irrazonable  | cantidad a null                                     |
| consulta_inutilizable | NADA: se usa el interprete de respaldo              |
"""

from dataclasses import dataclass

from umarket.busqueda.dominio.contrato import ConsultaInterpretada
from umarket.busqueda.dominio.reglas import ContextoConsulta
from umarket.compartido.dominio.reglas import Hallazgo

_CAMPO_DE_MENCION = {
    "menciones.precio": ("precio_max_unitario_cop", "presupuesto_total_cop"),
    "menciones.franja": ("franja_id",),
    "menciones.punto": ("punto_id",),
}


@dataclass(frozen=True)
class Correccion:
    consulta: ConsultaInterpretada
    anulados: tuple[str, ...]
    usar_respaldo: bool


class PoliticaCorreccionConsulta:
    def corregir(
        self, q: ConsultaInterpretada, hallazgos: list[Hallazgo], c: ContextoConsulta
    ) -> Correccion:
        if not hallazgos:
            return Correccion(q, (), False)
        datos = q.model_dump()
        anulados: list[str] = []
        items_fuera: set[int] = set()

        for h in hallazgos:
            if h.regla_id == "consulta_inutilizable":
                return Correccion(q, (), True)
            if h.campo.startswith("items."):
                partes = h.campo.split(".")
                indice = int(partes[1])
                if len(partes) == 3 and partes[2] == "cantidad":
                    datos["items"][indice]["cantidad"] = None
                else:
                    items_fuera.add(indice)
                anulados.append(h.campo)
            elif h.campo in _CAMPO_DE_MENCION:
                for campo in _CAMPO_DE_MENCION[h.campo]:
                    datos[campo] = None
                datos["menciones"][h.campo.split(".")[1]] = None
                anulados.append(h.campo)
            elif h.campo == "punto_candidatos":
                datos["punto_candidatos"] = [p for p in datos["punto_candidatos"] if p in c.puntos]
                anulados.append(h.campo)
            elif h.campo in datos:
                datos[h.campo] = None
                anulados.append(h.campo)

        datos["items"] = [it for i, it in enumerate(datos["items"]) if i not in items_fuera]
        return Correccion(
            ConsultaInterpretada.model_validate(datos), tuple(dict.fromkeys(anulados)), False
        )
