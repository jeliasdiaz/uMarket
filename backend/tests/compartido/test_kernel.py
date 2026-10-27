from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from umarket.compartido.dominio.reglas import ConjuntoReglas, Hallazgo, Validador
from umarket.compartido.dominio.reloj import RelojFijo
from umarket.compartido.dominio.texto import contiene_literal, normalizar


class TestNormalizar:
    @pytest.mark.parametrize(
        ("entrada", "esperado"),
        [
            ("Café  CON   leche", "cafe con leche"),
            ("  Empanada de POLLO ", "empanada de pollo"),
            ("Año", "ano"),
            ("pingüino", "pinguino"),
        ],
    )
    def test_casos(self, entrada: str, esperado: str) -> None:
        assert normalizar(entrada) == esperado

    @given(st.text())
    def test_es_idempotente(self, texto: str) -> None:
        assert normalizar(normalizar(texto)) == normalizar(texto)


class TestContieneLiteral:
    def test_ignora_tildes_y_mayusculas(self) -> None:
        assert contiene_literal("Algo DULCE por menos de 5 mil", "algo dulce")
        assert contiene_literal("un café", "cafe")

    def test_no_inventa(self) -> None:
        assert not contiene_literal("algo dulce", "algo salado")

    def test_fragmento_vacio_nunca_aparece(self) -> None:
        assert not contiene_literal("lo que sea", "   ")


def test_reloj_fijo_avanza_solo_cuando_se_pide() -> None:
    reloj = RelojFijo(datetime(2026, 11, 3, 12, 0, tzinfo=UTC))
    assert reloj.ahora() == datetime(2026, 11, 3, 12, 0, tzinfo=UTC)
    reloj.avanzar(timedelta(minutes=31))
    assert reloj.ahora() == datetime(2026, 11, 3, 12, 31, tzinfo=UTC)


def test_reloj_fijo_exige_zona_horaria() -> None:
    with pytest.raises(ValueError):
        RelojFijo(datetime(2026, 11, 3, 12, 0))


class _Mayor:
    id = "mayor_que_cero"

    def revisar(self, sujeto: int, contexto: None) -> list[Hallazgo]:
        return [] if sujeto > 0 else [Hallazgo(self.id, "valor", "debe ser mayor que cero")]


class _Par:
    id = "par"

    def revisar(self, sujeto: int, contexto: None) -> list[Hallazgo]:
        return [] if sujeto % 2 == 0 else [Hallazgo(self.id, "valor", "debe ser par")]


def test_validador_corre_las_reglas_en_orden() -> None:
    validador = Validador(ConjuntoReglas[int, None]("v1", (_Mayor(), _Par())))
    assert validador.version == "v1"
    assert [h.regla_id for h in validador.validar(-3, None)] == ["mayor_que_cero", "par"]
    assert validador.validar(4, None) == []
