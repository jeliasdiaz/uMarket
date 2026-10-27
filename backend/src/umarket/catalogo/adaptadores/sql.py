from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import delete, insert, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, sessionmaker

from umarket.bd.uow import UnidadSql
from umarket.campus import Franja, PuntoEncuentro
from umarket.campus.adaptadores.tablas import campus, franjas, puntos_encuentro
from umarket.catalogo.adaptadores.tablas import productos, stock_turno, tiendas, turnos
from umarket.catalogo.aplicacion.vistas import (
    OfertaTurno,
    ProductoVista,
    Reputacion,
    ResumenTienda,
    TurnoVista,
    VistaTienda,
)
from umarket.catalogo.dominio.modelos import Producto, StockTurno, Tienda, Turno
from umarket.catalogo.dominio.vocabulario import Categoria, Etiqueta


def _tienda(f: Any) -> Tienda:
    return Tienda(
        id=f["id"],
        campus_id=f["campus_id"],
        vendedor_id=f["vendedor_id"],
        nombre=f["nombre"],
        slug=f["slug"],
        descripcion=f["descripcion"],
        activa=f["activa"],
        creada_en=f["creada_en"],
    )


def _producto(f: Any) -> Producto:
    return Producto(
        id=f["id"],
        tienda_id=f["tienda_id"],
        nombre=f["nombre"],
        descripcion=f["descripcion"],
        categoria=Categoria(f["categoria"]),
        etiquetas=tuple(Etiqueta(e) for e in f["etiquetas"]),
        precio_cop=f["precio_cop"],
        activo=f["activo"],
    )


class RepositorioTiendasSql:
    def __init__(self, sesion: Session) -> None:
        self._s = sesion

    def por_vendedor(self, vendedor_id: UUID) -> Tienda | None:
        f = self._s.execute(select(tiendas).where(tiendas.c.vendedor_id == vendedor_id))
        fila = f.mappings().first()
        return None if fila is None else _tienda(fila)

    def slugs_que_empiezan(self, base: str) -> set[str]:
        filas = self._s.execute(select(tiendas.c.slug).where(tiendas.c.slug.startswith(base)))
        return set(filas.scalars())

    def agregar(self, tienda: Tienda) -> None:
        self._s.execute(
            insert(tiendas).values(
                id=tienda.id,
                campus_id=tienda.campus_id,
                vendedor_id=tienda.vendedor_id,
                nombre=tienda.nombre,
                slug=tienda.slug,
                descripcion=tienda.descripcion,
                activa=tienda.activa,
                creada_en=tienda.creada_en,
            )
        )


class RepositorioProductosSql:
    def __init__(self, sesion: Session) -> None:
        self._s = sesion

    def de_tienda(self, tienda_id: UUID) -> list[Producto]:
        filas = self._s.execute(
            select(productos).where(productos.c.tienda_id == tienda_id).order_by(productos.c.nombre)
        )
        return [_producto(f) for f in filas.mappings()]

    def por_id(self, producto_id: UUID) -> Producto | None:
        fila = self._s.execute(select(productos).where(productos.c.id == producto_id))
        fila = fila.mappings().first()
        return None if fila is None else _producto(fila)

    def guardar(self, producto: Producto) -> None:
        valores = {
            "tienda_id": producto.tienda_id,
            "nombre": producto.nombre,
            "nombre_normalizado": producto.nombre_normalizado,
            "descripcion": producto.descripcion,
            "categoria": producto.categoria.value,
            "etiquetas": [e.value for e in producto.etiquetas],
            "precio_cop": producto.precio_cop,
            "activo": producto.activo,
        }
        self._s.execute(
            pg_insert(productos)
            .values(id=producto.id, **valores)
            .on_conflict_do_update(index_elements=["id"], set_=valores)
        )


class RepositorioTurnosSql:
    def __init__(self, sesion: Session) -> None:
        self._s = sesion

    def _con_stock(self, filas: list[Any]) -> list[Turno]:
        if not filas:
            return []
        ids = [f["id"] for f in filas]
        por_turno: dict[UUID, list[StockTurno]] = defaultdict(list)
        for s in self._s.execute(
            select(stock_turno).where(stock_turno.c.turno_id.in_(ids))
        ).mappings():
            por_turno[s["turno_id"]].append(
                StockTurno(s["producto_id"], s["total"], s["reservado"])
            )
        return [
            Turno(
                f["id"],
                f["tienda_id"],
                f["fecha"],
                f["franja_id"],
                f["punto_id"],
                tuple(por_turno[f["id"]]),
            )
            for f in filas
        ]

    def por_id(self, turno_id: UUID) -> Turno | None:
        filas = list(self._s.execute(select(turnos).where(turnos.c.id == turno_id)).mappings())
        encontrados = self._con_stock(filas)
        return encontrados[0] if encontrados else None

    def de_tienda(self, tienda_id: UUID, desde: date, hasta: date) -> list[Turno]:
        filas = self._s.execute(
            select(turnos)
            .where(turnos.c.tienda_id == tienda_id, turnos.c.fecha.between(desde, hasta))
            .order_by(turnos.c.fecha, turnos.c.franja_id)
        )
        return self._con_stock(list(filas.mappings()))

    def existe(self, tienda_id: UUID, fecha: date, franja_id: str) -> bool:
        return (
            self._s.execute(
                select(turnos.c.id).where(
                    turnos.c.tienda_id == tienda_id,
                    turnos.c.fecha == fecha,
                    turnos.c.franja_id == franja_id,
                )
            ).first()
            is not None
        )

    def agregar(self, turno: Turno) -> None:
        self._s.execute(
            insert(turnos).values(
                id=turno.id,
                tienda_id=turno.tienda_id,
                fecha=turno.fecha,
                franja_id=turno.franja_id,
                punto_id=turno.punto_id,
            )
        )
        self._insertar_stock(turno)

    def guardar_stock(self, turno: Turno) -> None:
        """Reemplaza el stock. `reservado` se re-lee del turno: los pedidos lo mueven aparte."""
        self._s.execute(delete(stock_turno).where(stock_turno.c.turno_id == turno.id))
        self._insertar_stock(turno)

    def _insertar_stock(self, turno: Turno) -> None:
        if turno.stock:
            self._s.execute(
                insert(stock_turno),
                [
                    {
                        "turno_id": turno.id,
                        "producto_id": s.producto_id,
                        "total": s.total,
                        "reservado": s.reservado,
                    }
                    for s in turno.stock
                ],
            )


class CampusParaCatalogoSql:
    def __init__(self, sesion: Session) -> None:
        self._s = sesion

    def zona_horaria(self, campus_id: str) -> str:
        return self._s.execute(
            select(campus.c.zona_horaria).where(campus.c.id == campus_id)
        ).scalar_one()

    def franja(self, campus_id: str, franja_id: str) -> Franja | None:
        f = (
            self._s.execute(
                select(franjas).where(franjas.c.id == franja_id, franjas.c.campus_id == campus_id)
            )
            .mappings()
            .first()
        )
        return (
            None if f is None else Franja(f["id"], f["campus_id"], f["hora_inicio"], f["hora_fin"])
        )

    def punto(self, campus_id: str, punto_id: str) -> PuntoEncuentro | None:
        f = (
            self._s.execute(
                select(puntos_encuentro).where(
                    puntos_encuentro.c.id == punto_id, puntos_encuentro.c.campus_id == campus_id
                )
            )
            .mappings()
            .first()
        )
        if f is None:
            return None
        return PuntoEncuentro(
            f["id"],
            f["campus_id"],
            f["nombre"],
            f["descripcion"],
            f["foto_url"],
            tuple(f["alias"]),
            f["activo"],
        )


class UnidadCatalogoSql(UnidadSql):
    def _al_abrir(self, sesion: Session) -> None:
        self.tiendas = RepositorioTiendasSql(sesion)
        self.productos = RepositorioProductosSql(sesion)
        self.turnos = RepositorioTurnosSql(sesion)
        self.campus = CampusParaCatalogoSql(sesion)


# ---------------------------------------------------------------------------
# Lado de lectura
# ---------------------------------------------------------------------------


class FuenteReputacion(Protocol):
    """Lo implementa el modulo de reputacion; el catalogo solo lo muestra."""

    def de_tienda(self, sesion: Session, tienda_id: UUID) -> Reputacion: ...


# Una franja esta abierta mientras su hora de fin, en la zona del campus, no llega.
SQL_FRANJA_ABIERTA = "timezone(c.zona_horaria, tu.fecha + f.hora_fin) > :ahora"


class ConsultasCatalogoSql:
    """Implementa `ConsultasCatalogo`. La reputacion llega por `FuenteReputacion`."""

    def __init__(
        self,
        fabrica: sessionmaker[Session],
        reputacion: FuenteReputacion | None = None,
    ) -> None:
        self._fabrica = fabrica
        self._reputacion = reputacion

    def listar_tiendas(self, campus_id: str, fecha: date, ahora: datetime) -> list[ResumenTienda]:
        with self._fabrica() as s:
            filas = s.execute(
                text(
                    f"""
                    select t.id, t.slug, t.nombre, t.descripcion,
                      (select count(*) from productos p
                        where p.tienda_id = t.id and p.activo) as productos_activos,
                      (select count(*) from turnos tu
                         join franjas f on f.id = tu.franja_id
                        where tu.tienda_id = t.id and tu.fecha = :fecha
                          and {SQL_FRANJA_ABIERTA}) as turnos_abiertos_hoy
                    from tiendas t join campus c on c.id = t.campus_id
                    where t.campus_id = :campus and t.activa
                    """
                ),
                {"campus": campus_id, "fecha": fecha, "ahora": ahora},
            ).mappings()
            resumenes = [
                ResumenTienda(
                    id=f["id"],
                    slug=f["slug"],
                    nombre=f["nombre"],
                    descripcion=f["descripcion"],
                    productos_activos=f["productos_activos"],
                    turnos_abiertos_hoy=f["turnos_abiertos_hoy"],
                    reputacion=self._reputacion_de(s, f["id"]),
                )
                for f in filas
            ]
        return resumenes

    def ver_tienda(self, slug: str, fecha: date, ahora: datetime) -> VistaTienda | None:
        with self._fabrica() as s:
            t = (
                s.execute(select(tiendas).where(tiendas.c.slug == slug, tiendas.c.activa))
                .mappings()
                .first()
            )
            if t is None:
                return None
            prods = [
                ProductoVista(
                    p.id,
                    p.nombre,
                    p.descripcion,
                    p.categoria.value,
                    tuple(e.value for e in p.etiquetas),
                    p.precio_cop,
                )
                for p in RepositorioProductosSql(s).de_tienda(t["id"])
                if p.activo
            ]
            filas = s.execute(
                text(
                    f"""
                    select tu.id, tu.fecha, tu.franja_id, tu.punto_id, pe.nombre as punto_nombre,
                           f.hora_inicio, f.hora_fin, ({SQL_FRANJA_ABIERTA}) as abierto
                    from turnos tu
                      join franjas f on f.id = tu.franja_id
                      join puntos_encuentro pe on pe.id = tu.punto_id
                      join tiendas t on t.id = tu.tienda_id
                      join campus c on c.id = t.campus_id
                    where tu.tienda_id = :tienda and tu.fecha between :desde and :hasta
                    order by tu.fecha, f.hora_inicio
                    """
                ),
                {
                    "tienda": t["id"],
                    "desde": fecha,
                    "hasta": fecha + timedelta(days=1),
                    "ahora": ahora,
                },
            ).mappings()
            filas = list(filas)
            stock: dict[UUID, list[OfertaTurno]] = defaultdict(list)
            if filas:
                for st in s.execute(
                    select(stock_turno).where(stock_turno.c.turno_id.in_([f["id"] for f in filas]))
                ).mappings():
                    stock[st["turno_id"]].append(
                        OfertaTurno(st["producto_id"], st["total"], st["total"] - st["reservado"])
                    )
            turnos_vista = tuple(
                TurnoVista(
                    id=f["id"],
                    fecha=f["fecha"],
                    franja_id=f["franja_id"],
                    franja_etiqueta=f"{f['hora_inicio']:%H:%M}–{f['hora_fin']:%H:%M}",
                    punto_id=f["punto_id"],
                    punto_nombre=f["punto_nombre"],
                    abierto=bool(f["abierto"]),
                    ofertas=tuple(stock[f["id"]]),
                )
                for f in filas
            )
            return VistaTienda(
                id=t["id"],
                slug=t["slug"],
                nombre=t["nombre"],
                descripcion=t["descripcion"],
                vendedor_id=t["vendedor_id"],
                productos=tuple(prods),
                turnos=turnos_vista,
                reputacion=self._reputacion_de(s, t["id"]),
            )

    def slug_de_vendedor(self, vendedor_id: UUID) -> str | None:
        with self._fabrica() as s:
            return s.execute(
                select(tiendas.c.slug).where(tiendas.c.vendedor_id == vendedor_id)
            ).scalar_one_or_none()

    def _reputacion_de(self, s: Session, tienda_id: UUID) -> Reputacion:
        if self._reputacion is None:
            return Reputacion()
        return self._reputacion.de_tienda(s, tienda_id)


class ReservaStockSql:
    """Implementa el puerto `ReservaStock` de pedidos sobre `stock_turno` (D-14).

    El catalogo es dueno de la tabla; pedidos define lo que necesita. La reserva
    es un UPDATE condicional: si no alcanza, no toca ninguna fila y devuelve
    False. Dos compradores por la ultima unidad: la base de datos serializa los
    dos UPDATE sobre la misma fila y solo uno cumple la condicion.
    """

    def __init__(self, sesion: Session) -> None:
        self._s = sesion

    def reservar(self, turno_id: UUID, producto_id: UUID, cantidad: int) -> bool:
        resultado = self._s.execute(
            text(
                """
                update stock_turno set reservado = reservado + :cantidad
                where turno_id = :turno and producto_id = :producto
                  and total - reservado >= :cantidad
                """
            ),
            {"turno": turno_id, "producto": producto_id, "cantidad": cantidad},
        )
        return resultado.rowcount == 1  # type: ignore[attr-defined]

    def disponible(self, turno_id: UUID, producto_id: UUID) -> int:
        valor = self._s.execute(
            text(
                "select total - reservado from stock_turno "
                "where turno_id = :turno and producto_id = :producto"
            ),
            {"turno": turno_id, "producto": producto_id},
        ).scalar_one_or_none()
        return int(valor or 0)

    def liberar(self, turno_id: UUID, producto_id: UUID, cantidad: int) -> None:
        self._s.execute(
            text(
                """
                update stock_turno set reservado = greatest(reservado - :cantidad, 0)
                where turno_id = :turno and producto_id = :producto
                """
            ),
            {"turno": turno_id, "producto": producto_id, "cantidad": cantidad},
        )
