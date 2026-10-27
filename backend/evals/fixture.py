"""Carga el catalogo fixture en una base de datos (tests, evals y semilla --demo).

Los ids son deterministas (uuid5 del nombre): la clave legible
'dulces-de-caro/brownie' siempre es el mismo producto, asi que los datasets de
evals etiquetan resultados sin depender de una base concreta.
"""

import json
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import Engine
from sqlalchemy.dialects.postgresql import insert

from umarket.catalogo.adaptadores.tablas import productos, stock_turno, tiendas, turnos
from umarket.compartido.dominio.texto import normalizar
from umarket.identidad.adaptadores.tablas import usuarios

ARCHIVO = Path(__file__).resolve().parent / "datos" / "catalogo_fixture.json"


def clave_producto(slug_tienda: str, nombre: str) -> str:
    return f"{slug_tienda}/{normalizar(nombre).replace(' ', '-')}"


def id_de(clave: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"umarket-fixture:{clave}")


def sembrar_fixture(motor: Engine, fecha: date, campus_id: str = "campus-demo") -> dict[str, UUID]:
    """Crea vendedores, tiendas, productos y turnos. Devuelve clave legible -> id de producto."""
    datos = json.loads(ARCHIVO.read_text(encoding="utf-8"))
    claves: dict[str, UUID] = {}
    ahora = datetime.now(UTC)
    with motor.begin() as c:
        for t in datos["tiendas"]:
            vendedor = id_de(f"vendedor:{t['slug']}")
            tienda = id_de(f"tienda:{t['slug']}")
            c.execute(
                insert(usuarios)
                .values(
                    id=vendedor,
                    campus_id=campus_id,
                    correo=f"{t['slug']}@demo.edu.co",
                    nombre=t["nombre"],
                    creado_en=ahora,
                )
                .on_conflict_do_nothing()
            )
            c.execute(
                insert(tiendas)
                .values(
                    id=tienda,
                    campus_id=campus_id,
                    vendedor_id=vendedor,
                    nombre=t["nombre"],
                    slug=t["slug"],
                    descripcion=t["descripcion"],
                    creada_en=ahora,
                )
                .on_conflict_do_nothing()
            )
            ids_productos: list[UUID] = []
            for p in t["productos"]:
                clave = clave_producto(t["slug"], p["nombre"])
                pid = id_de(f"producto:{clave}")
                claves[clave] = pid
                ids_productos.append(pid)
                c.execute(
                    insert(productos)
                    .values(
                        id=pid,
                        tienda_id=tienda,
                        nombre=p["nombre"],
                        nombre_normalizado=normalizar(p["nombre"]),
                        descripcion=p.get("descripcion", ""),
                        categoria=p["categoria"],
                        etiquetas=p["etiquetas"],
                        precio_cop=p["precio_cop"],
                    )
                    .on_conflict_do_nothing()
                )
            for tu in t["turnos"]:
                turno = id_de(f"turno:{t['slug']}:{fecha.isoformat()}:{tu['franja']}")
                c.execute(
                    insert(turnos)
                    .values(
                        id=turno,
                        tienda_id=tienda,
                        fecha=fecha,
                        franja_id=tu["franja"],
                        punto_id=tu["punto"],
                    )
                    .on_conflict_do_nothing()
                )
                for pid in ids_productos:
                    c.execute(
                        insert(stock_turno)
                        .values(turno_id=turno, producto_id=pid, total=tu["stock"])
                        .on_conflict_do_nothing()
                    )
    return claves
