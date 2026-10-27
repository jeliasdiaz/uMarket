"""Reintentos, cache, presupuesto y la composicion de produccion."""

from datetime import date
from pathlib import Path

import pytest

from umarket.ia.adaptadores import PROVEEDORES, ConfigLlm, build_llm
from umarket.ia.adaptadores.cache import CachingLlm
from umarket.ia.adaptadores.fake import FakeLlm, SinRespuestaGrabada, clave_de_payload
from umarket.ia.adaptadores.presupuesto import ConPresupuesto
from umarket.ia.adaptadores.reintentos import RetryingLlm
from umarket.ia.puerto import (
    LlmPresupuestoAgotado,
    LlmRequest,
    LlmResponse,
    LlmRetryableError,
    LlmTerminalError,
    UsoTokens,
)

PETICION = LlmRequest(system_prompt="s", payload={"texto": "hola"})


class _Guion:
    """Un puerto que lanza o responde segun un guion, y cuenta las llamadas."""

    def __init__(self, *pasos: Exception | LlmResponse) -> None:
        self.pasos = list(pasos)
        self.llamadas = 0

    def complete_json(self, request: LlmRequest) -> LlmResponse:
        self.llamadas += 1
        paso = self.pasos.pop(0)
        if isinstance(paso, Exception):
            raise paso
        return paso


def _ok(modelo: str = "gemini-2.5-flash-lite", salida: int = 1_000_000) -> LlmResponse:
    return LlmResponse(
        data={"ok": True}, raw_text="{}", model=modelo, usage=UsoTokens(salida=salida)
    )


class TestReintentos:
    def test_reintenta_lo_transitorio_y_anota_el_intento(self) -> None:
        esperas: list[float] = []
        inner = _Guion(LlmRetryableError("429"), _ok())
        respuesta = RetryingLlm(
            inner, retries=3, backoff_base_s=1.0, sleep=esperas.append
        ).complete_json(PETICION)
        assert respuesta.attempts == 2
        assert esperas == [1.0]

    def test_lo_terminal_no_se_reintenta_ni_se_duerme(self) -> None:
        esperas: list[float] = []
        inner = _Guion(LlmTerminalError("401"))
        with pytest.raises(LlmTerminalError):
            RetryingLlm(inner, retries=3, sleep=esperas.append).complete_json(PETICION)
        assert inner.llamadas == 1
        assert esperas == []

    def test_respeta_el_tope_total_de_tiempo(self) -> None:
        instante = iter([0.0, 2.5])  # inicio, y luego el reloj marca 2.5 s
        inner = _Guion(LlmRetryableError("lento"), _ok())
        with pytest.raises(LlmRetryableError):
            RetryingLlm(
                inner,
                retries=3,
                backoff_base_s=1.0,
                tope_total_s=3.0,
                sleep=lambda _: None,
                reloj=lambda: next(instante),
            ).complete_json(PETICION)
        assert inner.llamadas == 1


class TestCache:
    def test_segunda_llamada_sale_del_disco(self, tmp_path: Path) -> None:
        inner = _Guion(_ok())
        cache = CachingLlm(inner, cache_dir=tmp_path, model="m")
        assert cache.complete_json(PETICION).from_cache is False
        segunda = cache.complete_json(PETICION)
        assert segunda.from_cache is True
        assert segunda.data == {"ok": True}
        assert inner.llamadas == 1

    def test_apagada_es_transparente(self, tmp_path: Path) -> None:
        inner = _Guion(_ok(), _ok())
        cache = CachingLlm(inner, cache_dir=tmp_path, model="m", enabled=False)
        cache.complete_json(PETICION)
        cache.complete_json(PETICION)
        assert inner.llamadas == 2


class TestPresupuesto:
    def test_corta_al_superar_el_limite(self) -> None:
        # 1M tokens de salida de flash-lite cuestan 0.40 USD; el limite es 0.5.
        inner = _Guion(_ok(), _ok())
        con = ConPresupuesto(inner, limite_usd=0.5, hoy=lambda: date(2026, 11, 3))
        con.complete_json(PETICION)
        con.complete_json(PETICION)
        assert con.gastado_hoy_usd == pytest.approx(0.8)
        with pytest.raises(LlmPresupuestoAgotado):
            con.complete_json(PETICION)
        assert inner.llamadas == 2

    def test_se_reinicia_al_cambiar_el_dia(self) -> None:
        dias = iter([date(2026, 11, 3), date(2026, 11, 3), date(2026, 11, 4), date(2026, 11, 4)])
        con = ConPresupuesto(_Guion(_ok(), _ok()), limite_usd=0.3, hoy=lambda: next(dias))
        con.complete_json(PETICION)
        con.complete_json(PETICION)  # nuevo dia: el gasto de ayer no cuenta

    def test_un_modelo_sin_precio_no_suma_pero_no_rompe(self) -> None:
        con = ConPresupuesto(_Guion(_ok(modelo="desconocido")), limite_usd=0.01)
        con.complete_json(PETICION)
        assert con.gastado_hoy_usd == 0


class TestFake:
    def test_grita_si_no_hay_respuesta_grabada(self) -> None:
        with pytest.raises(SinRespuestaGrabada):
            FakeLlm({}).complete_json(PETICION)

    def test_consume_las_corridas_en_orden_y_grita_al_agotarlas(self) -> None:
        fake = FakeLlm({clave_de_payload(PETICION.payload): [{"run": 1}, {"run": 2}]})
        assert fake.complete_json(PETICION).data == {"run": 1}
        assert fake.complete_json(PETICION).data == {"run": 2}
        with pytest.raises(SinRespuestaGrabada):
            fake.complete_json(PETICION)

    def test_la_clave_no_depende_del_orden_de_las_claves(self) -> None:
        assert clave_de_payload({"a": 1, "b": 2}) == clave_de_payload({"b": 2, "a": 1})


class TestComposicion:
    def test_proveedor_desconocido_falla_con_los_disponibles(self) -> None:
        with pytest.raises(LlmTerminalError, match="gemini"):
            build_llm(ConfigLlm(proveedor="otro", modelo="x"))

    def test_registro_de_proveedores(self) -> None:
        assert {"gemini", "fake"} <= set(PROVEEDORES)

    def test_gemini_sin_clave_falla_al_construir(self) -> None:
        with pytest.raises(LlmTerminalError, match="GEMINI_API_KEY"):
            build_llm(ConfigLlm(proveedor="gemini", modelo="gemini-3.5-flash-lite"))
