import pytest
from sqlalchemy import Engine

from tests.apoyo import cliente, sistema


def test_salud() -> None:
    c, _ = sistema()
    respuesta = cliente(c).get("/salud")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok", "entorno": "test"}


def test_rechaza_mutaciones_desde_otro_origen() -> None:
    c, _ = sistema()
    respuesta = cliente(c).post("/v1/auth/codigo", headers={"Origin": "https://malicioso.example"})
    assert respuesta.status_code == 403
    assert respuesta.json()["tipo"] == "origen_no_permitido"


@pytest.mark.integracion
def test_salud_bd(bd: Engine) -> None:
    c, _ = sistema()
    respuesta = cliente(c).get("/salud/bd")
    assert respuesta.status_code == 200
    assert "PostgreSQL 17" in respuesta.json()["postgres"]
