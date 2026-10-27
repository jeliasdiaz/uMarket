from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from scripts.sembrar_datos import sembrar_campus
from tests.apoyo import cliente, entrar, montar_tienda, sistema
from umarket.catalogo import Categoria, Etiqueta, Producto, StockTurno, Turno
from umarket.catalogo.dominio.modelos import slug_de
from umarket.compartido.dominio.errores import ReglaIncumplida


def _producto(**cambios: object) -> Producto:
    base: dict[str, object] = {
        "id": uuid4(),
        "tienda_id": uuid4(),
        "nombre": "Empanada de pollo",
        "descripcion": "",
        "categoria": Categoria.EMPANADAS,
        "etiquetas": (Etiqueta.SALADO,),
        "precio_cop": 3000,
    }
    return Producto(**{**base, **cambios})  # type: ignore[arg-type]


class TestDominio:
    def test_slug(self) -> None:
        assert slug_de("Empanadas Doña Rosa!!") == "empanadas-dona-rosa"
        assert slug_de("***") == "tienda"

    @pytest.mark.parametrize("precio", [0, 99, 500_001])
    def test_precio_fuera_de_rango(self, precio: int) -> None:
        with pytest.raises(ReglaIncumplida, match="precio"):
            _producto(precio_cop=precio)

    def test_nombre_largo_frena_el_relleno_de_palabras_clave(self) -> None:
        with pytest.raises(ReglaIncumplida):
            _producto(nombre="empanada " * 10)

    def test_maximo_cuatro_etiquetas_y_sin_repetir(self) -> None:
        with pytest.raises(ReglaIncumplida):
            _producto(etiquetas=tuple(Etiqueta)[:5])
        assert _producto(etiquetas=(Etiqueta.DULCE, Etiqueta.DULCE)).etiquetas == (Etiqueta.DULCE,)

    def test_stock_nunca_por_debajo_de_lo_reservado(self) -> None:
        p = uuid4()
        turno = Turno(uuid4(), uuid4(), date(2026, 11, 3), "f-1200", "b19", (StockTurno(p, 10, 4),))
        assert turno.con_stock({p: 6}).stock_de(p) == StockTurno(p, 6, 4)
        with pytest.raises(ReglaIncumplida) as error:
            turno.con_stock({p: 3})
        assert error.value.tipo == "stock_menor_que_reservado"

    def test_quitar_un_producto_con_reservas_lo_conserva(self) -> None:
        p, q = uuid4(), uuid4()
        turno = Turno(
            uuid4(), uuid4(), date(2026, 11, 3), "f", "b", (StockTurno(p, 5, 2), StockTurno(q, 5))
        )
        nuevo = turno.con_stock({q: 7})
        assert nuevo.stock_de(p) == StockTurno(p, 5, 2)


@pytest.fixture
def http(bd: Engine) -> TestClient:
    sembrar_campus(bd)
    c, _ = sistema()
    return cliente(c)


@pytest.mark.integracion
class TestFlujoVendedorYComprador:
    def test_el_comprador_ve_la_tienda_con_su_stock(self, http: TestClient) -> None:
        ids = montar_tienda(http)
        anonimo = TestClient(http.app)
        tienda = anonimo.get(f"/v1/tiendas/{ids['slug']}").json()
        assert tienda["nombre"] == "Empanadas Doña Rosa"
        assert {p["nombre"] for p in tienda["productos"]} == {
            "Empanada de pollo",
            "Empanada de queso",
        }
        (turno,) = tienda["turnos"]
        assert turno["abierto"] is True
        assert turno["franja_etiqueta"] == "12:00–12:30"
        assert turno["punto_nombre"] == "Bloque 19 - entrada"
        assert {o["disponible"] for o in turno["ofertas"]} == {10, 8}

    def test_listado_del_campus(self, http: TestClient) -> None:
        montar_tienda(http)
        (resumen,) = TestClient(http.app).get("/v1/tiendas").json()
        assert resumen["productos_activos"] == 2
        assert resumen["turnos_abiertos_hoy"] == 1

    def test_yo_muestra_la_tienda_del_vendedor(self, http: TestClient) -> None:
        ids = montar_tienda(http)
        assert http.get("/v1/yo").json()["tienda_slug"] == ids["slug"]

    def test_una_tienda_por_vendedor(self, http: TestClient) -> None:
        montar_tienda(http)
        r = http.post("/v1/vendedor/tienda", json={"nombre": "Otra"})
        assert r.status_code == 409

    def test_slug_unico(self, http: TestClient) -> None:
        montar_tienda(http)
        otra = TestClient(http.app)
        entrar(otra, "otro@demo.edu.co", "Otro Vendedor")
        r = otra.post("/v1/vendedor/tienda", json={"nombre": "Empanadas Doña Rosa"})
        assert r.json()["slug"] == "empanadas-dona-rosa-2"

    def test_turno_repetido_en_la_misma_franja(self, http: TestClient) -> None:
        ids = montar_tienda(http)
        r = http.post(
            "/v1/vendedor/turnos",
            json={
                "fecha": "2026-11-03",
                "franja_id": "f-1200",
                "punto_id": "biblioteca",
                "stock": [{"producto_id": ids["pollo"], "total": 1}],
            },
        )
        assert r.status_code == 409

    def test_franja_que_ya_paso(self, http: TestClient) -> None:
        ids = montar_tienda(http)
        r = http.post(
            "/v1/vendedor/turnos",
            json={
                "fecha": "2026-11-03",
                "franja_id": "f-1000",
                "punto_id": "biblioteca",
                "stock": [{"producto_id": ids["pollo"], "total": 1}],
            },
        )
        assert r.json()["tipo"] == "franja_pasada"

    def test_no_puede_ofrecer_productos_ajenos(self, http: TestClient) -> None:
        ids = montar_tienda(http)
        otra = TestClient(http.app)
        entrar(otra, "otro@demo.edu.co", "Otro Vendedor")
        otra.post("/v1/vendedor/tienda", json={"nombre": "Arepas"})
        r = otra.post(
            "/v1/vendedor/turnos",
            json={
                "fecha": "2026-11-03",
                "franja_id": "f-1600",
                "punto_id": "biblioteca",
                "stock": [{"producto_id": ids["pollo"], "total": 1}],
            },
        )
        assert r.status_code == 403

    def test_editar_stock_respeta_lo_reservado(self, http: TestClient, bd: Engine) -> None:
        ids = montar_tienda(http)
        with bd.begin() as conexion:
            conexion.execute(
                text("update stock_turno set reservado = 4 where producto_id = :p"),
                {"p": ids["pollo"]},
            )
        r = http.put(
            f"/v1/vendedor/turnos/{ids['turno']}/stock",
            json={"stock": [{"producto_id": ids["pollo"], "total": 3}]},
        )
        assert r.json()["tipo"] == "stock_menor_que_reservado"
        ok = http.put(
            f"/v1/vendedor/turnos/{ids['turno']}/stock",
            json={"stock": [{"producto_id": ids["pollo"], "total": 6}]},
        )
        assert ok.status_code == 200

    def test_duplicar_el_dia(self, http: TestClient) -> None:
        montar_tienda(http)
        r = http.post(
            "/v1/vendedor/turnos/duplicar", json={"desde": "2026-11-03", "hacia": "2026-11-04"}
        )
        (copia,) = r.json()
        assert copia["fecha"] == "2026-11-04"
        assert {o["disponible"] for o in copia["ofertas"]} == {10, 8}
        # Duplicar otra vez no crea repetidos.
        assert (
            http.post(
                "/v1/vendedor/turnos/duplicar", json={"desde": "2026-11-03", "hacia": "2026-11-04"}
            ).json()
            == []
        )

    def test_desactivar_un_producto_lo_oculta_al_comprador(self, http: TestClient) -> None:
        ids = montar_tienda(http)
        r = http.put(
            f"/v1/vendedor/productos/{ids['queso']}",
            json={
                "nombre": "Empanada de queso",
                "categoria": "empanadas",
                "precio_cop": 3000,
                "activo": False,
            },
        )
        assert r.status_code == 200
        tienda = TestClient(http.app).get(f"/v1/tiendas/{ids['slug']}").json()
        assert [p["nombre"] for p in tienda["productos"]] == ["Empanada de pollo"]
        mia = http.get("/v1/vendedor/tienda").json()
        assert len(mia["productos"]) == 2

    def test_categoria_fuera_del_vocabulario(self, http: TestClient) -> None:
        montar_tienda(http)
        r = http.post(
            "/v1/vendedor/productos",
            json={"nombre": "Pizza", "categoria": "pizzas", "precio_cop": 5000},
        )
        assert r.status_code == 422

    def test_vocabulario(self, http: TestClient) -> None:
        datos = http.get("/v1/vocabulario").json()
        assert "empanadas" in datos["categorias"]
        assert "dulce" in datos["etiquetas"]

    def test_vender_sin_tienda(self, http: TestClient) -> None:
        entrar(http, "nueva@demo.edu.co")
        r = http.post(
            "/v1/vendedor/productos",
            json={"nombre": "X producto", "categoria": "otros", "precio_cop": 1000},
        )
        assert r.json()["tipo"] == "sin_tienda"
