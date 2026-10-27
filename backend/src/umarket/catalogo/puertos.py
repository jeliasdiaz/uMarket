from datetime import date, datetime
from typing import Protocol
from uuid import UUID

from umarket.campus import Franja, PuntoEncuentro
from umarket.catalogo.aplicacion.vistas import ResumenTienda, VistaTienda
from umarket.catalogo.dominio.modelos import Producto, Tienda, Turno
from umarket.compartido.aplicacion.puertos import UnidadDeTrabajo


class RepositorioTiendas(Protocol):
    def por_vendedor(self, vendedor_id: UUID) -> Tienda | None: ...

    def slugs_que_empiezan(self, base: str) -> set[str]: ...

    def agregar(self, tienda: Tienda) -> None: ...


class RepositorioProductos(Protocol):
    def de_tienda(self, tienda_id: UUID) -> list[Producto]: ...

    def por_id(self, producto_id: UUID) -> Producto | None: ...

    def guardar(self, producto: Producto) -> None:
        """Inserta o actualiza."""
        ...


class RepositorioTurnos(Protocol):
    def por_id(self, turno_id: UUID) -> Turno | None: ...

    def de_tienda(self, tienda_id: UUID, desde: date, hasta: date) -> list[Turno]: ...

    def existe(self, tienda_id: UUID, fecha: date, franja_id: str) -> bool: ...

    def agregar(self, turno: Turno) -> None: ...

    def guardar_stock(self, turno: Turno) -> None: ...


class CampusParaCatalogo(Protocol):
    def zona_horaria(self, campus_id: str) -> str: ...

    def franja(self, campus_id: str, franja_id: str) -> Franja | None: ...

    def punto(self, campus_id: str, punto_id: str) -> PuntoEncuentro | None: ...


class UnidadCatalogo(UnidadDeTrabajo, Protocol):
    @property
    def tiendas(self) -> RepositorioTiendas: ...

    @property
    def productos(self) -> RepositorioProductos: ...

    @property
    def turnos(self) -> RepositorioTurnos: ...

    @property
    def campus(self) -> CampusParaCatalogo: ...


class ConsultasCatalogo(Protocol):
    """El lado de lectura: vistas armadas con una consulta, sin pasar por entidades."""

    def listar_tiendas(
        self, campus_id: str, fecha: date, ahora: datetime
    ) -> list[ResumenTienda]: ...

    def ver_tienda(self, slug: str, fecha: date, ahora: datetime) -> VistaTienda | None: ...

    def slug_de_vendedor(self, vendedor_id: UUID) -> str | None: ...
