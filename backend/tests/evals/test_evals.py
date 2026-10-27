"""El harness de evals: el replay reproduce lo medido y la puerta no se deja enganar."""

import json
from pathlib import Path

import pytest

from evals.regresiones import correr_regresiones
from evals.runner import RESULTADOS, comparar, correr
from tests.conftest import URL_TEST

EN_VIVO = RESULTADOS / "2026-10-27-busqueda-intencion-v1-consulta-v1"
BASELINE_V2 = RESULTADOS / "2026-10-27-busqueda-palabras-consulta-v2"
REPLAY_V2 = RESULTADOS / "2026-10-27-busqueda-intencion-v1-consulta-v2-replay"


@pytest.mark.integracion
def test_el_replay_reproduce_la_medicion_commiteada(tmp_path: Path, motor: object) -> None:
    """Sin red ni cuota, el pipeline completo da exactamente lo que se midio en vivo."""
    destino = correr(
        "intencion", 1, "todo", EN_VIVO / "crudo.json", 3.0, "consulta-v1", tmp_path, URL_TEST
    )
    obtenido = json.loads((destino / "manifiesto.json").read_text("utf-8"))["resumen"]
    medido = json.loads((EN_VIVO / "manifiesto.json").read_text("utf-8"))["resumen"]
    for grupo in ("global", "categoria:intencion", "conjunto:test"):
        for metrica in ("acierto5", "filtros_ok", "inventados", "inventados_crudo"):
            assert obtenido[grupo][metrica] == medido[grupo][metrica], (grupo, metrica)


def test_la_puerta_usa_la_latencia_en_vivo_aunque_el_after_sea_un_replay() -> None:
    pasa, texto = comparar(BASELINE_V2, REPLAY_V2)
    assert not pasa
    assert "23.061s" in texto
    assert EN_VIVO.name in texto


def test_las_regresiones_pasan_en_todas_las_versiones() -> None:
    assert all(resultado == "PASS" for *_, resultado in correr_regresiones())
