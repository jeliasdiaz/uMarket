"""Tiendas, productos y turnos con stock.

Un turno es la promesa del vendedor: "el martes, en la franja de las 12, estare
en el Bloque 19 con 10 empanadas de pollo y 8 de queso". El stock vive en el
turno, no en el producto, porque lo que importa es cuanto hay donde y cuando.

`reservado` lo mueven los pedidos (reserva atomica en la base de datos, D-14).
El vendedor puede cambiar `total`, pero nunca por debajo de lo ya reservado.
"""

import re
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from uuid import UUID

from umarket.catalogo.dominio.vocabulario import Categoria, Etiqueta
from umarket.compartido.dominio.errores import ReglaIncumplida
from umarket.compartido.dominio.texto import normalizar

PRECIO_MIN_COP = 100
PRECIO_MAX_COP = 500_000
LARGO_NOMBRE = (2, 60)
MAX_ETIQUETAS = 4
MAX_STOCK = 500


def slug_de(nombre: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", normalizar(nombre)).strip("-")
    return base[:40].strip("-") or "tienda"


def _nombre_valido(nombre: str, que: str) -> str:
    limpio = " ".join(nombre.split())
    minimo, maximo = LARGO_NOMBRE
    if not minimo <= len(limpio) <= maximo:
        raise ReglaIncumplida(
            "nombre_invalido", f"El nombre de {que} debe tener entre {minimo} y {maximo} letras."
        )
    return limpio


@dataclass(frozen=True)
class Tienda:
    id: UUID
    campus_id: str
    vendedor_id: UUID
    nombre: str
    slug: str
    descripcion: str
    activa: bool
    creada_en: datetime

    @staticmethod
    def nueva(
        id: UUID,
        campus_id: str,
        vendedor_id: UUID,
        nombre: str,
        slug: str,
        descripcion: str,
        ahora: datetime,
    ) -> "Tienda":
        return Tienda(
            id=id,
            campus_id=campus_id,
            vendedor_id=vendedor_id,
            nombre=_nombre_valido(nombre, "la tienda"),
            slug=slug,
            descripcion=descripcion.strip()[:280],
            activa=True,
            creada_en=ahora,
        )


@dataclass(frozen=True)
class Producto:
    id: UUID
    tienda_id: UUID
    nombre: str
    descripcion: str
    categoria: Categoria
    etiquetas: tuple[Etiqueta, ...]
    precio_cop: int
    activo: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "nombre", _nombre_valido(self.nombre, "el producto"))
        object.__setattr__(self, "descripcion", self.descripcion.strip()[:280])
        if not PRECIO_MIN_COP <= self.precio_cop <= PRECIO_MAX_COP:
            raise ReglaIncumplida(
                "precio_invalido",
                f"El precio debe estar entre ${PRECIO_MIN_COP:,} y ${PRECIO_MAX_COP:,}.",
            )
        if len(set(self.etiquetas)) > MAX_ETIQUETAS:
            raise ReglaIncumplida(
                "demasiadas_etiquetas", f"Un producto lleva hasta {MAX_ETIQUETAS} etiquetas."
            )
        object.__setattr__(self, "etiquetas", tuple(dict.fromkeys(self.etiquetas)))

    @property
    def nombre_normalizado(self) -> str:
        return normalizar(self.nombre)


@dataclass(frozen=True)
class StockTurno:
    producto_id: UUID
    total: int
    reservado: int = 0

    @property
    def disponible(self) -> int:
        return self.total - self.reservado


@dataclass(frozen=True)
class Turno:
    id: UUID
    tienda_id: UUID
    fecha: date
    franja_id: str
    punto_id: str
    stock: tuple[StockTurno, ...] = field(default_factory=tuple[StockTurno, ...])

    def stock_de(self, producto_id: UUID) -> StockTurno | None:
        return next((s for s in self.stock if s.producto_id == producto_id), None)

    def con_stock(self, nuevos: dict[UUID, int]) -> "Turno":
        """Reemplaza los totales. Nunca por debajo de lo reservado: eso ya es de alguien."""
        resultado: list[StockTurno] = []
        for producto_id, total in nuevos.items():
            if not 0 <= total <= MAX_STOCK:
                raise ReglaIncumplida(
                    "stock_invalido", f"El stock de un producto va de 0 a {MAX_STOCK}."
                )
            actual = self.stock_de(producto_id)
            reservado = actual.reservado if actual else 0
            if total < reservado:
                raise ReglaIncumplida(
                    "stock_menor_que_reservado",
                    f"Ya hay {reservado} unidades reservadas; el stock no puede ser menor.",
                    producto_id=str(producto_id),
                    reservado=reservado,
                )
            resultado.append(StockTurno(producto_id, total, reservado))
        # Los productos que no vienen en `nuevos` se conservan si tienen reservas.
        for s in self.stock:
            if s.producto_id not in nuevos and s.reservado > 0:
                resultado.append(s)
        return replace(self, stock=tuple(resultado))
