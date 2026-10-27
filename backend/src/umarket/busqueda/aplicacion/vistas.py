"""Lo que devuelve una busqueda."""

from dataclasses import dataclass, field
from datetime import date, datetime
from uuid import UUID

from umarket.busqueda.dominio.contrato import ConsultaInterpretada
from umarket.busqueda.dominio.filtros import Filtro


@dataclass(frozen=True)
class Oferta:
    """Un producto con stock en un turno que todavia no paso. Lo arma el SQL."""

    producto_id: UUID
    nombre: str
    categoria: str
    etiquetas: tuple[str, ...]
    precio_cop: int
    disponible: int
    turno_id: UUID
    fecha: date
    franja_id: str
    franja_etiqueta: str
    punto_id: str
    punto_nombre: str
    tienda_id: UUID
    tienda_slug: str
    tienda_nombre: str
    promedio: float | None
    resenas: int
    relevancia: float
    item: int | None = None


@dataclass(frozen=True)
class ProductoEncontrado:
    producto_id: UUID
    nombre: str
    precio_cop: int
    disponible: int
    cantidad_sugerida: int


@dataclass(frozen=True)
class TiendaEncontrada:
    tienda_id: UUID
    slug: str
    nombre: str
    promedio: float | None
    resenas: int
    turno_id: UUID
    franja_etiqueta: str
    punto_id: str
    punto_nombre: str
    productos: tuple[ProductoEncontrado, ...]


@dataclass(frozen=True)
class OpcionPunto:
    id: str
    nombre: str


@dataclass(frozen=True)
class ResultadoBusqueda:
    busqueda_id: UUID
    interprete: str
    consulta: ConsultaInterpretada
    filtros: tuple[Filtro, ...]
    anulados: tuple[str, ...]
    relajados: tuple[str, ...]
    tiendas: tuple[TiendaEncontrada, ...]
    pregunta_punto: tuple[OpcionPunto, ...] = field(default_factory=tuple[OpcionPunto, ...])


@dataclass(frozen=True)
class RegistroBusqueda:
    id: UUID
    campus_id: str
    usuario_id: UUID | None
    texto: str
    interprete: str
    consulta: ConsultaInterpretada
    anulados: tuple[str, ...]
    relajados: tuple[str, ...]
    n_tiendas: int
    n_productos: int
    latencia_ms: int
    creada_en: datetime
