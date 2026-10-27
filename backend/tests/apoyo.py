"""Ayudas para tests de integracion: el sistema armado por la raiz de composicion REAL.

Los tests de aplicacion corren contra Postgres, no contra repositorios en memoria
(ver docs/DECISIONES.md, D-19). Se arman con `arranque.construir`, asi que prueban
tambien la composicion que se despliega.
"""

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from tests.conftest import URL_TEST
from umarket.arranque import ROUTERS, construir
from umarket.compartido.dominio.reloj import RelojFijo
from umarket.config import Settings
from umarket.contenedor import Contenedor
from umarket.http.app import crear_app

CODIGO = "123456"
# Martes 3 de noviembre de 2026, 11:20 en Bogota (16:20 UTC).
INSTANTE = datetime(2026, 11, 3, 16, 20, tzinfo=UTC)


def settings_de_prueba(**cambios: object) -> Settings:
    base: dict[str, object] = {
        "entorno": "test",
        "database_url": URL_TEST,
        "codigo_acceso_fijo": CODIGO,
        "llm_provider": "fake",
        "busqueda_interprete": "palabras",
    }
    return Settings(**{**base, **cambios})  # type: ignore[arg-type]


def sistema(reloj: RelojFijo | None = None, **cambios: object) -> tuple[Contenedor, RelojFijo]:
    reloj = reloj or RelojFijo(INSTANTE)
    return construir(settings_de_prueba(**cambios), reloj), reloj


def cliente(contenedor: Contenedor) -> TestClient:
    return TestClient(crear_app(contenedor, ROUTERS))


def entrar(http: TestClient, correo: str, nombre: str = "Ana Compradora") -> dict[str, object]:
    """Acceso completo por HTTP: pide el codigo y lo verifica. Deja la cookie en el cliente."""
    assert http.post("/v1/auth/codigo", json={"correo": correo}).status_code == 202
    respuesta = http.post(
        "/v1/auth/verificar",
        json={"correo": correo, "codigo": CODIGO, "nombre": nombre, "acepta_terminos": True},
    )
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def montar_tienda(
    http: TestClient,
    correo: str = "vendedora@demo.edu.co",
    nombre: str = "Empanadas Doña Rosa",
    fecha: str = "2026-11-03",
    franja: str = "f-1200",
    punto: str = "b19-entrada",
    stock_pollo: int = 10,
    stock_queso: int = 8,
) -> dict[str, str]:
    """Vendedora con tienda, dos productos y un turno publicado. Devuelve los ids."""
    entrar(http, correo, "Rosa Vendedora")
    tienda = http.post("/v1/vendedor/tienda", json={"nombre": nombre, "descripcion": "Caseras"})
    assert tienda.status_code == 201, tienda.text
    pollo = http.post(
        "/v1/vendedor/productos",
        json={
            "nombre": "Empanada de pollo",
            "categoria": "empanadas",
            "etiquetas": ["salado", "caliente"],
            "precio_cop": 3000,
        },
    ).json()
    queso = http.post(
        "/v1/vendedor/productos",
        json={
            "nombre": "Empanada de queso",
            "categoria": "empanadas",
            "etiquetas": ["salado", "vegetariano"],
            "precio_cop": 3000,
        },
    ).json()
    turno = http.post(
        "/v1/vendedor/turnos",
        json={
            "fecha": fecha,
            "franja_id": franja,
            "punto_id": punto,
            "stock": [
                {"producto_id": pollo["id"], "total": stock_pollo},
                {"producto_id": queso["id"], "total": stock_queso},
            ],
        },
    )
    assert turno.status_code == 201, turno.text
    return {
        "slug": tienda.json()["slug"],
        "pollo": pollo["id"],
        "queso": queso["id"],
        "turno": turno.json()["id"],
    }
