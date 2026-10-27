from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from scripts.sembrar_datos import sembrar_campus
from tests.apoyo import cliente, entrar, montar_tienda, sistema
from umarket.bd.motor import crear_fabrica_sesiones
from umarket.compartido.dominio.errores import ReglaIncumplida
from umarket.compartido.dominio.eventos import Evento
from umarket.notificaciones import avisos_de
from umarket.notificaciones.adaptadores.canales import CanalWebPush
from umarket.notificaciones.dominio.avisos import Aviso
from umarket.reputacion import Metricas, RankingV1
from umarket.reputacion.dominio.modelos import Calificacion

AHORA = datetime(2026, 11, 3, 16, 0, tzinfo=UTC)


class TestMetricasYRanking:
    def test_promedio_y_porcentaje(self) -> None:
        m = Metricas(
            resenas=4, suma_estrellas=18, entregas=9, vencidos=1, cancelados_por_vendedor=0
        )
        assert m.promedio == 4.5
        assert m.porcentaje_cumplido == 90.0
        assert Metricas().promedio is None
        assert Metricas().porcentaje_cumplido is None

    def test_minimo_de_resenas_para_rankear(self) -> None:
        r = RankingV1(minimo_resenas=5)
        assert not r.rankeable(Metricas(resenas=4, suma_estrellas=20))
        assert r.rankeable(Metricas(resenas=5, suma_estrellas=20))

    def test_una_sola_resena_perfecta_no_gana_a_un_historial(self) -> None:
        r = RankingV1(minimo_resenas=5)
        amigo = Metricas(resenas=1, suma_estrellas=5, entregas=1)
        constante = Metricas(resenas=20, suma_estrellas=84, entregas=25)  # 4.2
        assert r.clave(constante) < r.clave(amigo)

    def test_estrellas_fuera_de_rango(self) -> None:
        with pytest.raises(ReglaIncumplida):
            Calificacion(uuid4(), uuid4(), uuid4(), uuid4(), 6, "", AHORA)


class TestAvisos:
    def _datos(self, **cambios: object) -> dict[str, Any]:
        return {
            "pedido_id": str(uuid4()),
            "codigo": "K7P",
            "vendedor_id": str(uuid4()),
            "comprador_id": str(uuid4()),
            "total_cop": 9000,
            "motivo": None,
            **cambios,
        }

    def test_pedido_creado_avisa_al_vendedor_con_el_total(self) -> None:
        d = self._datos()
        (aviso,) = avisos_de(Evento("pedido.creado", d, AHORA))
        assert str(aviso.usuario_id) == d["vendedor_id"]
        assert "$9.000" in aviso.cuerpo

    def test_cancelado_avisa_solo_a_la_otra_parte(self) -> None:
        d = self._datos(actor="vendedor", motivo="Llovio")
        (aviso,) = avisos_de(Evento("pedido.cancelado", d, AHORA))
        assert str(aviso.usuario_id) == d["comprador_id"]
        assert aviso.cuerpo == "Llovio"

    def test_un_evento_sin_plantilla_no_avisa(self) -> None:
        assert avisos_de(Evento("calificacion.registrada", {}, AHORA)) == []


@pytest.mark.integracion
def test_web_push_borra_las_suscripciones_muertas(bd: Engine) -> None:
    sembrar_campus(bd)
    c, _ = sistema()
    http = cliente(c)
    usuario = entrar(http, "ana@demo.edu.co")
    for n in (1, 2):
        r = http.post(
            "/v1/push/suscripciones",
            json={
                "endpoint": f"https://push.example/{n}",
                "keys": {"p256dh": "x" * 20, "auth": "y" * 16},
            },
        )
        assert r.status_code == 201
    enviados: list[str] = []

    def enviar(suscripcion: dict[str, Any], _datos: str) -> int:
        enviados.append(suscripcion["endpoint"])
        return 410 if suscripcion["endpoint"].endswith("/1") else 201

    canal = CanalWebPush(crear_fabrica_sesiones(bd), "clave", "mailto:x@y.z", enviar=enviar)
    canal.enviar(Aviso(usuario["id"], "Hola", "Prueba", "/"))  # type: ignore[arg-type]
    assert sorted(enviados) == ["https://push.example/1", "https://push.example/2"]
    with bd.connect() as conexion:
        restantes = conexion.execute(text("select endpoint from suscripciones_push")).scalars()
        assert list(restantes) == ["https://push.example/2"]


@pytest.mark.integracion
def test_las_tiendas_rankeables_van_primero(bd: Engine) -> None:
    sembrar_campus(bd)
    c, _ = sistema()
    montar_tienda(cliente(c), "a@demo.edu.co", "A sin resenas")
    montar_tienda(cliente(c), "b@demo.edu.co", "B con historial")
    with bd.begin() as conexion:
        conexion.execute(
            text(
                "insert into metricas_tienda (tienda_id, resenas, suma_estrellas, entregas, "
                "actualizado_en) select id, 5, 22, 6, now() from tiendas "
                "where slug = 'b-con-historial'"
            )
        )
    nombres = [t["nombre"] for t in TestClient(cliente(c).app).get("/v1/tiendas").json()]
    assert nombres == ["B con historial", "A sin resenas"]
