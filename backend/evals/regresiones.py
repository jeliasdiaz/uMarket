"""Regresiones deterministas del validador de la busqueda. No llaman al modelo.

Cada regla de `consulta-v1` tiene un caso que la dispara y otro que confirma que
no da falso positivo. `scripts/gate_regresiones.py` compara el resultado con
`evals/regresiones_esperadas.csv`: si un cambio altera lo que el validador
detecta, la puerta lo dice, y hay que decidir con la diferencia en la mano.
"""

from dataclasses import dataclass

from umarket.busqueda import ConsultaInterpretada, reglas_consulta
from umarket.busqueda.dominio.contrato import ItemBuscado, Menciones, Orden
from umarket.busqueda.dominio.reglas import ContextoConsulta
from umarket.catalogo import Etiqueta
from umarket.compartido.dominio.reglas import Validador

TEXTO = "algo dulce por menos de 5 mil pa las 12 en el 19"
CONTEXTO = ContextoConsulta(
    TEXTO, frozenset({"b19-entrada", "b19-cafeteria"}), frozenset({"f-1200", "f-1600"})
)
CORRECTA = ConsultaInterpretada(
    es_busqueda=True,
    items=[ItemBuscado(etiquetas=[Etiqueta.DULCE], mencion="algo dulce")],
    precio_max_unitario_cop=5000,
    franja_id="f-1200",
    punto_candidatos=["b19-entrada", "b19-cafeteria"],
    menciones=Menciones(precio="menos de 5 mil", franja="pa las 12", punto="el 19"),
)


@dataclass(frozen=True)
class Regresion:
    id: str
    descripcion: str
    consulta: ConsultaInterpretada
    reglas_esperadas: frozenset[str]
    # Excepciones por version: lo que cambio a proposito entre conjuntos de reglas.
    por_version: tuple[tuple[str, frozenset[str]], ...] = ()

    def esperadas(self, version: str) -> frozenset[str]:
        return dict(self.por_version).get(version, self.reglas_esperadas)


def _con(**cambios: object) -> ConsultaInterpretada:
    return CORRECTA.model_copy(update=cambios)


CASOS: tuple[Regresion, ...] = (
    Regresion("correcta", "la consulta bien formada no da hallazgos", CORRECTA, frozenset()),
    Regresion(
        "item-inventado",
        "un item cuya mencion no esta en el texto",
        _con(items=[ItemBuscado(termino="pizza", mencion="pizza")]),
        frozenset({"mencion_no_literal"}),
    ),
    Regresion(
        "precio-sin-respaldo",
        "4000 no aparece como monto en el texto",
        _con(precio_max_unitario_cop=4000),
        frozenset({"monto_sin_respaldo"}),
    ),
    Regresion(
        "precio-cero",
        "inyeccion 'precio 0': monto implausible y sin respaldo",
        _con(precio_max_unitario_cop=0, menciones=Menciones()),
        frozenset({"monto_sin_respaldo", "monto_implausible"}),
    ),
    Regresion(
        "punto-inventado",
        "un punto que no existe en el campus",
        _con(punto_id="la-luna"),
        frozenset({"punto_desconocido"}),
    ),
    Regresion(
        "franja-cerrada",
        "una franja que ya paso",
        _con(franja_id="f-0700"),
        frozenset({"franja_cerrada"}),
    ),
    Regresion(
        "cantidad-absurda",
        "99 unidades",
        _con(items=[ItemBuscado(termino="brownie", cantidad=99, mencion="dulce")]),
        frozenset({"cantidad_irrazonable"}),
    ),
    Regresion(
        "vacia",
        "dice que es busqueda pero no trae nada",
        ConsultaInterpretada(es_busqueda=True),
        frozenset({"consulta_inutilizable"}),
    ),
    Regresion(
        "solo-orden",
        "'lo mas barato': sin items pero con orden. v1 lo mandaba al respaldo (D-20)",
        ConsultaInterpretada(es_busqueda=True, orden=Orden.PRECIO),
        frozenset(),
        por_version=(("consulta-v1", frozenset({"consulta_inutilizable"})),),
    ),
    Regresion(
        "saludo",
        "no es busqueda: no se exige nada",
        ConsultaInterpretada(es_busqueda=False),
        frozenset(),
    ),
)


VERSIONES = ("consulta-v1", "consulta-v2")


def correr_regresiones() -> list[tuple[str, str, str, str]]:
    """[(version, caso, esperado, resultado PASS/FAIL)] para cada conjunto medido."""
    filas: list[tuple[str, str, str, str]] = []
    for version in VERSIONES:
        validador = Validador(reglas_consulta(version))
        for caso in CASOS:
            obtenidas = {h.regla_id for h in validador.validar(caso.consulta, CONTEXTO)}
            esperadas = caso.esperadas(version)
            esperado = "+".join(sorted(esperadas)) or "-"
            filas.append((version, caso.id, esperado, "PASS" if obtenidas == esperadas else "FAIL"))
    return filas
