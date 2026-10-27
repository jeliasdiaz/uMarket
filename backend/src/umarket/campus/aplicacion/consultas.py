"""Lo que el resto del sistema pregunta sobre un campus."""

from collections.abc import Callable
from dataclasses import dataclass

from umarket.campus.dominio.modelos import Campus, Franja, PuntoEncuentro
from umarket.campus.puertos import UnidadCampus
from umarket.compartido.dominio.errores import NoEncontrado


@dataclass(frozen=True)
class VistaCampus:
    campus: Campus
    puntos: list[PuntoEncuentro]
    franjas: list[Franja]


class ObtenerCampus:
    def __init__(self, unidad: Callable[[], UnidadCampus]) -> None:
        self._unidad = unidad

    def ejecutar(self, campus_id: str) -> VistaCampus:
        with self._unidad() as u:
            campus = u.campus.obtener(campus_id)
            if campus is None:
                raise NoEncontrado("campus_no_encontrado", f"No existe el campus {campus_id}.")
            return VistaCampus(
                campus=campus,
                puntos=[p for p in u.campus.puntos(campus_id) if p.activo],
                franjas=sorted(u.campus.franjas(campus_id), key=lambda f: f.hora_inicio),
            )
