"""Vistas de lectura del catalogo (lo que ve el comprador)."""

from dataclasses import dataclass, field
from datetime import date
from uuid import UUID


@dataclass(frozen=True)
class Reputacion:
    """Lo calcula el modulo de reputacion; el catalogo solo lo muestra."""

    promedio: float | None = None
    resenas: int = 0
    entregas: int = 0
    porcentaje_cumplido: float | None = None
    rankeable: bool = False
    # Clave de orden que calcula la politica de ranking vigente. El catalogo ordena
    # por ella sin conocer la formula (punto de extension "ranking", PLAN-TECNICO §3).
    orden: tuple[float, ...] = (1.0, 0.0, 0.0)


@dataclass(frozen=True)
class ProductoVista:
    id: UUID
    nombre: str
    descripcion: str
    categoria: str
    etiquetas: tuple[str, ...]
    precio_cop: int
    activo: bool = True


@dataclass(frozen=True)
class OfertaTurno:
    producto_id: UUID
    total: int
    disponible: int


@dataclass(frozen=True)
class TurnoVista:
    id: UUID
    fecha: date
    franja_id: str
    franja_etiqueta: str
    punto_id: str
    punto_nombre: str
    abierto: bool
    ofertas: tuple[OfertaTurno, ...]


@dataclass(frozen=True)
class ResumenTienda:
    id: UUID
    slug: str
    nombre: str
    descripcion: str
    productos_activos: int
    turnos_abiertos_hoy: int
    reputacion: Reputacion = field(default_factory=Reputacion)


@dataclass(frozen=True)
class VistaTienda:
    id: UUID
    slug: str
    nombre: str
    descripcion: str
    vendedor_id: UUID
    productos: tuple[ProductoVista, ...]
    turnos: tuple[TurnoVista, ...]
    reputacion: Reputacion = field(default_factory=Reputacion)
