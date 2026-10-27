from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import Engine

from scripts.sembrar_datos import sembrar_campus
from tests.apoyo import cliente, sistema
from umarket.campus import Campus, Franja

BOGOTA = ZoneInfo("America/Bogota")
MEDIODIA = Franja("f-1200", "c", time(12, 0), time(12, 30))


class TestFranja:
    def test_no_ha_pasado_mientras_no_termina(self) -> None:
        # 12:29 en Bogota = 17:29 UTC
        assert not MEDIODIA.ha_pasado(
            date(2026, 11, 3), datetime(2026, 11, 3, 17, 29, tzinfo=UTC), BOGOTA
        )

    def test_pasa_al_terminar(self) -> None:
        assert MEDIODIA.ha_pasado(
            date(2026, 11, 3), datetime(2026, 11, 3, 17, 30, tzinfo=UTC), BOGOTA
        )

    def test_la_franja_de_manana_no_ha_pasado(self) -> None:
        assert not MEDIODIA.ha_pasado(
            date(2026, 11, 4), datetime(2026, 11, 3, 23, 0, tzinfo=UTC), BOGOTA
        )

    def test_no_puede_terminar_antes_de_empezar(self) -> None:
        with pytest.raises(ValueError):
            Franja("mala", "c", time(12, 30), time(12, 0))

    def test_etiqueta(self) -> None:
        assert MEDIODIA.etiqueta == "12:00–12:30"


def test_campus_admite_solo_sus_dominios() -> None:
    campus = Campus("c", "Campus", "America/Bogota", ("demo.edu.co",))
    assert campus.admite_correo("ana@DEMO.edu.co")
    assert not campus.admite_correo("ana@gmail.com")


@pytest.mark.integracion
def test_campus_actual_sin_sesion_es_el_campus_por_defecto(bd: Engine) -> None:
    sembrar_campus(bd)
    c, _ = sistema()
    respuesta = cliente(c).get("/v1/campus/actual")
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["id"] == "campus-demo"
    assert [f["id"] for f in datos["franjas"]] == ["f-0700", "f-1000", "f-1200", "f-1600"]
    assert {p["id"] for p in datos["puntos"]} >= {"b19-entrada", "b19-cafeteria"}


@pytest.mark.integracion
def test_campus_inexistente_es_404(bd: Engine) -> None:
    c, _ = sistema(campus_por_defecto="no-existe")
    respuesta = cliente(c).get("/v1/campus/actual")
    assert respuesta.status_code == 404
    assert respuesta.json()["tipo"] == "campus_no_encontrado"
