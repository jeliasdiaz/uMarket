"""El flujo completo de un pedido contra Postgres, por HTTP y con el worker real."""

import threading
from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from scripts.sembrar_datos import sembrar_campus
from tests.apoyo import cliente, entrar, montar_tienda, settings_de_prueba, sistema
from umarket.arranque import Worker, construir_worker
from umarket.compartido.dominio.reloj import RelojFijo
from umarket.notificaciones.adaptadores.canales import CanalRegistro

pytestmark = pytest.mark.integracion


class Escenario:
    """Una vendedora con su tienda y una compradora, sobre el mismo sistema y el mismo reloj."""

    def __init__(self, bd: Engine) -> None:
        sembrar_campus(bd)
        self.bd = bd
        self.contenedor, self.reloj = sistema()
        self.vendedora = cliente(self.contenedor)
        self.ids = montar_tienda(self.vendedora)
        self.compradora = cliente(self.contenedor)
        entrar(self.compradora, "ana@demo.edu.co", "Ana Compradora")
        self.avisos = CanalRegistro()
        self.worker: Worker = construir_worker(settings_de_prueba(), self.reloj, [self.avisos])

    def pedir(
        self,
        http: TestClient | None = None,
        pollo: int = 2,
        queso: int = 1,
        clave: str | None = None,
    ) -> dict[str, object]:
        items = [{"producto_id": self.ids["pollo"], "cantidad": pollo}]
        if queso:
            items.append({"producto_id": self.ids["queso"], "cantidad": queso})
        r = (http or self.compradora).post(
            "/v1/pedidos",
            json={"turno_id": self.ids["turno"], "items": items},
            headers={"Idempotency-Key": clave or uuid4().hex},
        )
        return {"status": r.status_code, **r.json()}

    def actuar(self, http: TestClient, pedido_id: object, accion: str) -> dict[str, object]:
        r = http.post(f"/v1/pedidos/{pedido_id}/{accion}", json={})
        return {"status": r.status_code, **r.json()}

    def disponible(self, producto: str) -> int:
        tienda = TestClient(self.vendedora.app).get(f"/v1/tiendas/{self.ids['slug']}").json()
        (turno,) = tienda["turnos"]
        return next(o["disponible"] for o in turno["ofertas"] if o["producto_id"] == producto)


@pytest.fixture
def e(bd: Engine) -> Escenario:
    return Escenario(bd)


def test_crear_pedido_reserva_stock_y_calcula_el_total(e: Escenario) -> None:
    p = e.pedir()
    assert p["status"] == 201
    assert p["estado"] == "pendiente"
    assert p["total_cop"] == 9000
    assert len(str(p["codigo"])) == 3
    assert p["acciones"] == ["cancelar"]
    assert e.disponible(e.ids["pollo"]) == 8
    with e.bd.connect() as c:
        assert c.execute(text("select tipo from eventos_salida")).scalars().all() == [
            "pedido.creado"
        ]


def test_el_cliente_no_puede_poner_el_precio(e: Escenario) -> None:
    r = e.compradora.post(
        "/v1/pedidos",
        json={
            "turno_id": e.ids["turno"],
            "total_cop": 0,
            "items": [{"producto_id": e.ids["pollo"], "cantidad": 1, "precio_cop": 0}],
        },
        headers={"Idempotency-Key": uuid4().hex},
    )
    assert r.status_code == 201
    assert r.json()["total_cop"] == 3000


def test_doble_toque_es_el_mismo_pedido(e: Escenario) -> None:
    primero = e.pedir(clave="clave-unica-1")
    segundo = e.pedir(clave="clave-unica-1")
    assert primero["id"] == segundo["id"]
    assert e.disponible(e.ids["pollo"]) == 8


def test_sin_stock_dice_cuanto_queda(e: Escenario) -> None:
    p = e.pedir(pollo=11, queso=0)
    assert p["status"] == 409
    assert p["tipo"] == "sin_stock"
    assert p["detalles"] == {"producto_id": e.ids["pollo"], "disponible": 10}
    assert e.disponible(e.ids["pollo"]) == 10


def test_dos_compradores_por_la_ultima_unidad(e: Escenario, bd: Engine) -> None:
    """La garantia de D-14: la base de datos serializa la reserva."""
    with bd.begin() as c:
        c.execute(
            text("update stock_turno set total = 1 where producto_id = :p"), {"p": e.ids["pollo"]}
        )
    otra = cliente(e.contenedor)
    entrar(otra, "beto@demo.edu.co", "Beto Comprador")
    resultados: list[int] = []
    barrera = threading.Barrier(2)

    def pedir(http: TestClient) -> None:
        barrera.wait()
        resultados.append(int(e.pedir(http, pollo=1, queso=0)["status"]))  # type: ignore[arg-type]

    hilos = [threading.Thread(target=pedir, args=(h,)) for h in (e.compradora, otra)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert sorted(resultados) == [201, 409]
    with bd.connect() as c:
        reservado, total = c.execute(
            text("select reservado, total from stock_turno where producto_id = :p"),
            {"p": e.ids["pollo"]},
        ).one()
    assert (reservado, total) == (1, 1)


def test_flujo_feliz_hasta_la_calificacion(e: Escenario) -> None:
    p = e.pedir()
    assert e.actuar(e.compradora, p["id"], "aprobar")["status"] == 403
    aprobado = e.actuar(e.vendedora, p["id"], "aprobar")
    assert aprobado["estado"] == "aprobado"
    assert e.actuar(e.vendedora, p["id"], "llegue")["estado"] == "en_punto"
    entregado = e.actuar(e.vendedora, p["id"], "entregar")
    assert entregado["estado"] == "entregado"

    r = e.compradora.post(
        "/v1/calificaciones", json={"pedido_id": p["id"], "estrellas": 5, "comentario": "¡Ricas!"}
    )
    assert r.status_code == 201
    assert (
        e.compradora.post(
            "/v1/calificaciones", json={"pedido_id": p["id"], "estrellas": 1}
        ).status_code
        == 409
    )

    resultado = e.worker.despachador.procesar()
    assert resultado.fallidos == 0
    destinatarios = {(a.titulo.split()[0], str(a.usuario_id)) for a in e.avisos.enviados}
    assert len(e.avisos.enviados) == 4  # creado, aprobado, llego, entregado
    assert ("Nuevo", e.vendedora.get("/v1/yo").json()["id"]) in destinatarios

    tienda = TestClient(e.vendedora.app).get(f"/v1/tiendas/{e.ids['slug']}").json()
    assert tienda["reputacion"]["entregas"] == 1
    assert tienda["reputacion"]["promedio"] == 5.0
    assert tienda["reputacion"]["porcentaje_cumplido"] == 100.0
    assert tienda["reputacion"]["rankeable"] is False  # menos de 5 resenas
    resenas = TestClient(e.vendedora.app).get(f"/v1/tiendas/{e.ids['slug']}/resenas").json()
    assert resenas[0]["comentario"] == "¡Ricas!"
    assert e.compradora.get(f"/v1/pedidos/{p['id']}").json()["calificado"] is True


def test_no_se_califica_antes_de_recibir(e: Escenario) -> None:
    p = e.pedir()
    r = e.compradora.post("/v1/calificaciones", json={"pedido_id": p["id"], "estrellas": 5})
    assert r.json()["tipo"] == "aun_no_entregado"


def test_rechazar_libera_el_stock(e: Escenario) -> None:
    p = e.pedir()
    assert e.disponible(e.ids["pollo"]) == 8
    r = e.vendedora.post(f"/v1/pedidos/{p['id']}/rechazar", json={"motivo": "Se acabo la masa"})
    assert r.json()["estado"] == "rechazado"
    assert r.json()["motivo"] == "Se acabo la masa"
    assert e.disponible(e.ids["pollo"]) == 10


def test_a_los_30_minutos_el_pedido_vence(e: Escenario) -> None:
    p = e.pedir()
    e.reloj.avanzar(timedelta(minutes=30))
    # Antes de que pase el worker, ya se ve vencido y no se puede aprobar.
    assert e.compradora.get(f"/v1/pedidos/{p['id']}").json()["estado"] == "vencido"
    assert e.actuar(e.vendedora, p["id"], "aprobar")["tipo"] == "pedido_vencido"
    assert e.disponible(e.ids["pollo"]) == 8

    assert e.worker.vencer_pedidos.ejecutar() == 1
    assert e.disponible(e.ids["pollo"]) == 10
    e.worker.despachador.procesar()
    assert any(a.titulo == "El vendedor no respondio a tiempo" for a in e.avisos.enviados)
    assert e.worker.vencer_pedidos.ejecutar() == 0


def test_limite_de_pedidos_abiertos(e: Escenario) -> None:
    assert e.pedir(pollo=1, queso=0)["status"] == 201
    assert e.pedir(pollo=1, queso=0)["status"] == 201
    tercero = e.pedir(pollo=1, queso=0)
    assert tercero["tipo"] == "demasiados_pedidos_abiertos"


def test_la_vendedora_no_se_pide_a_si_misma(e: Escenario) -> None:
    assert e.pedir(e.vendedora)["tipo"] == "pedido_a_si_mismo"


def test_inasistencias_bloquean_al_comprador(e: Escenario, bd: Engine) -> None:
    for _ in range(3):
        p = e.pedir(pollo=1, queso=0)
        e.actuar(e.vendedora, p["id"], "aprobar")
        e.actuar(e.vendedora, p["id"], "llegue")
        assert e.actuar(e.vendedora, p["id"], "no_asistio")["tipo"] == "espera_insuficiente"
        e.reloj.avanzar(timedelta(minutes=10))
        assert e.actuar(e.vendedora, p["id"], "no_asistio")["estado"] == "no_asistio"
    assert e.pedir(pollo=1, queso=0)["tipo"] == "comprador_bloqueado"


def test_un_tercero_no_ve_el_pedido(e: Escenario) -> None:
    p = e.pedir()
    intruso = cliente(e.contenedor)
    entrar(intruso, "intruso@demo.edu.co", "Intruso")
    assert intruso.get(f"/v1/pedidos/{p['id']}").status_code == 404
    assert e.actuar(intruso, p["id"], "cancelar")["status"] == 403


def test_bandeja_de_la_vendedora(e: Escenario) -> None:
    e.pedir()
    (pedido,) = e.vendedora.get("/v1/vendedor/pedidos").json()
    assert pedido["comprador_nombre"] == "Ana Compradora"
    assert set(pedido["acciones"]) == {"aprobar", "rechazar"}
    assert pedido["punto_nombre"] == "Bloque 19 - entrada"
    assert pedido["franja_etiqueta"] == "12:00–12:30"


def test_cancelar_avisa_a_la_otra_parte(e: Escenario) -> None:
    p = e.pedir()
    e.actuar(e.compradora, p["id"], "cancelar")
    e.worker.despachador.procesar()
    cancelado = [a for a in e.avisos.enviados if "cancelado" in a.titulo]
    assert len(cancelado) == 1
    assert cancelado[0].url == "/vendedor"


def test_sin_cabecera_de_idempotencia(e: Escenario) -> None:
    r = e.compradora.post(
        "/v1/pedidos",
        json={
            "turno_id": e.ids["turno"],
            "items": [{"producto_id": e.ids["pollo"], "cantidad": 1}],
        },
    )
    assert r.status_code == 422


def test_despachador_reintenta_y_luego_se_rinde(bd: Engine) -> None:
    from tests.apoyo import INSTANTE
    from umarket.bd.motor import crear_fabrica_sesiones
    from umarket.bd.plataforma import BuzonEventosSql
    from umarket.compartido.dominio.eventos import Evento
    from umarket.worker.despachador import DespachadorEventos

    fabrica = crear_fabrica_sesiones(bd)
    with fabrica() as s:
        BuzonEventosSql(s).publicar(Evento("prueba.falla", {"x": 1}, INSTANTE))
        s.commit()

    def falla(_: Evento) -> None:
        raise RuntimeError("manejador roto")

    despachador = DespachadorEventos(fabrica, {"prueba.falla": [falla]}, RelojFijo(INSTANTE), 2)
    assert despachador.procesar().fallidos == 1
    assert despachador.procesar().fallidos == 1
    assert despachador.procesar().fallidos == 0  # agotado: ya no se toma
    with bd.connect() as c:
        intentos, error, procesado = c.execute(
            text("select intentos, ultimo_error, procesado_en from eventos_salida")
        ).one()
    assert intentos == 2
    assert "manejador roto" in error
    assert procesado is not None
