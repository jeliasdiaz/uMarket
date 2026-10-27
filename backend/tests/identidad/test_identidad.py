from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import Engine, text

from scripts.sembrar_datos import sembrar_campus
from tests.apoyo import CODIGO, cliente, entrar, sistema
from umarket.compartido.dominio.errores import ReglaIncumplida
from umarket.identidad.dominio.modelos import CodigoAcceso, huella, validar_nombre

AHORA = datetime(2026, 11, 3, 16, 0, tzinfo=UTC)


class TestDominio:
    def _codigo(self, **cambios: object) -> CodigoAcceso:
        base = CodigoAcceso(
            uuid4(), "a@demo.edu.co", huella("s", "123456"), AHORA, AHORA + timedelta(minutes=10)
        )
        return CodigoAcceso(**{**base.__dict__, **cambios})  # type: ignore[arg-type]

    def test_vigente_hasta_que_vence_se_usa_o_agota_intentos(self) -> None:
        assert self._codigo().vigente(AHORA, max_intentos=5)
        assert not self._codigo().vigente(AHORA + timedelta(minutes=10), max_intentos=5)
        assert not self._codigo(usado_en=AHORA).vigente(AHORA, max_intentos=5)
        assert not self._codigo(intentos=5).vigente(AHORA, max_intentos=5)

    def test_coincide_por_huella(self) -> None:
        assert self._codigo().coincide(huella("s", "123456"))
        assert not self._codigo().coincide(huella("s", "654321"))
        assert not self._codigo().coincide(huella("otro-secreto", "123456"))

    def test_nombre(self) -> None:
        assert validar_nombre("  Ana   María ") == "Ana María"
        with pytest.raises(ReglaIncumplida):
            validar_nombre("A")


@pytest.mark.integracion
class TestAccesoHttp:
    def test_flujo_completo_crea_usuario_con_consentimiento_y_sesion(self, bd: Engine) -> None:
        sembrar_campus(bd)
        c, _ = sistema()
        http = cliente(c)
        usuario = entrar(http, "Ana@demo.edu.co")
        assert usuario["correo"] == "ana@demo.edu.co"
        assert usuario["campus_id"] == "campus-demo"
        assert http.get("/v1/yo").json()["nombre"] == "Ana Compradora"
        with bd.connect() as conexion:
            assert conexion.execute(text("select count(*) from consentimientos")).scalar_one() == 1
            # Ni el codigo ni el token se guardan en claro.
            huellas = conexion.execute(text("select codigo_huella from codigos_acceso")).scalars()
            assert CODIGO not in list(huellas)

    def test_correo_no_institucional(self, bd: Engine) -> None:
        sembrar_campus(bd)
        c, _ = sistema()
        respuesta = cliente(c).post("/v1/auth/codigo", json={"correo": "ana@gmail.com"})
        assert respuesta.status_code == 422
        assert respuesta.json()["tipo"] == "correo_no_institucional"

    def test_sin_consentimiento_no_se_crea_la_cuenta(self, bd: Engine) -> None:
        sembrar_campus(bd)
        c, _ = sistema()
        http = cliente(c)
        http.post("/v1/auth/codigo", json={"correo": "ana@demo.edu.co"})
        respuesta = http.post(
            "/v1/auth/verificar", json={"correo": "ana@demo.edu.co", "codigo": CODIGO}
        )
        assert respuesta.status_code == 422
        assert respuesta.json()["tipo"] == "falta_consentimiento"

    def test_codigo_incorrecto_suma_intento_y_al_quinto_se_bloquea(self, bd: Engine) -> None:
        sembrar_campus(bd)
        c, _ = sistema()
        http = cliente(c)
        http.post("/v1/auth/codigo", json={"correo": "ana@demo.edu.co"})
        for _ in range(5):
            r = http.post(
                "/v1/auth/verificar",
                json={"correo": "ana@demo.edu.co", "codigo": "000000", "acepta_terminos": True},
            )
            assert r.json()["tipo"] == "codigo_invalido"
        r = http.post(
            "/v1/auth/verificar",
            json={"correo": "ana@demo.edu.co", "codigo": CODIGO, "acepta_terminos": True},
        )
        assert r.status_code == 401
        assert r.json()["tipo"] == "codigo_vencido"

    def test_el_codigo_vence(self, bd: Engine) -> None:
        sembrar_campus(bd)
        c, reloj = sistema()
        http = cliente(c)
        http.post("/v1/auth/codigo", json={"correo": "ana@demo.edu.co"})
        reloj.avanzar(timedelta(minutes=11))
        r = http.post(
            "/v1/auth/verificar",
            json={"correo": "ana@demo.edu.co", "codigo": CODIGO, "acepta_terminos": True},
        )
        assert r.json()["tipo"] == "codigo_vencido"

    def test_limite_de_codigos_por_ventana(self, bd: Engine) -> None:
        sembrar_campus(bd)
        c, _ = sistema()
        http = cliente(c)
        for _ in range(3):
            assert (
                http.post("/v1/auth/codigo", json={"correo": "ana@demo.edu.co"}).status_code == 202
            )
        r = http.post("/v1/auth/codigo", json={"correo": "ana@demo.edu.co"})
        assert r.status_code == 429

    def test_salir_invalida_la_sesion(self, bd: Engine) -> None:
        sembrar_campus(bd)
        c, _ = sistema()
        http = cliente(c)
        entrar(http, "ana@demo.edu.co")
        assert http.post("/v1/auth/salir").status_code == 204
        assert http.get("/v1/yo").status_code == 401

    def test_sin_cookie_yo_es_401(self, bd: Engine) -> None:
        c, _ = sistema()
        r = cliente(c).get("/v1/yo")
        assert r.status_code == 401
        assert r.json()["tipo"] == "sin_sesion"


def test_produccion_no_arranca_con_codigo_fijo() -> None:
    from umarket.config import Settings

    with pytest.raises(ValueError, match="codigo_acceso_fijo"):
        Settings(
            entorno="produccion",
            codigo_acceso_fijo="123456",
            cookie_segura=True,
            secreto_servidor="x" * 40,
        )
    with pytest.raises(ValueError, match="secreto_servidor"):
        Settings(entorno="produccion", cookie_segura=True)
