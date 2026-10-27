from typing import Protocol

from umarket.campus.dominio.modelos import Campus, Franja, PuntoEncuentro
from umarket.compartido.aplicacion.puertos import UnidadDeTrabajo


class RepositorioCampus(Protocol):
    def obtener(self, campus_id: str) -> Campus | None: ...

    def puntos(self, campus_id: str) -> list[PuntoEncuentro]: ...

    def franjas(self, campus_id: str) -> list[Franja]: ...


class UnidadCampus(UnidadDeTrabajo, Protocol):
    @property
    def campus(self) -> RepositorioCampus: ...
