"""Smoke contra la API real. Deseleccionado por defecto: `pytest -m llm` (gasta cuota).

Existe por la leccion del ADR-0014 de QuickDev: el doble del cliente no valida el
esquema, asi que un esquema que el proveedor rechaza (400 en el 100% de las
llamadas) pasa todos los tests unitarios. Solo una llamada real lo detecta.
"""

import os

import pytest

from umarket.busqueda.adaptadores.interprete_llm import InterpreteLlm
from umarket.busqueda.dominio.contrato import (
    ConsultaInterpretada,
    EntradaInterprete,
    FranjaContexto,
    PuntoContexto,
    Vocabulario,
)
from umarket.catalogo import CATEGORIAS, ETIQUETAS
from umarket.config import RAIZ_BACKEND, Settings
from umarket.ia.adaptadores.gemini import GeminiAdapter
from umarket.ia.prompts import RegistroPrompts
from umarket.ia.traza import Traza

pytestmark = pytest.mark.llm


@pytest.fixture
def interprete() -> InterpreteLlm:
    settings = Settings()
    clave = os.environ.get("GEMINI_API_KEY") or settings.gemini_api_key
    if not clave:
        pytest.skip("Sin GEMINI_API_KEY")
    adaptador = GeminiAdapter(api_key=clave, model=settings.llm_model)
    return InterpreteLlm(adaptador, RegistroPrompts(RAIZ_BACKEND / "prompts"), "v1", timeout_s=45)


def test_el_proveedor_acepta_el_esquema_y_responde_el_contrato(interprete: InterpreteLlm) -> None:
    entrada = EntradaInterprete(
        texto="algo dulce por menos de 5 mil pa las 12 en el 19",
        ahora="2026-11-03T11:20-05:00",
        vocabulario=Vocabulario(
            categorias=list(CATEGORIAS),
            etiquetas=list(ETIQUETAS),
            productos_hoy=["brownie", "galletas de avena", "empanada de pollo"],
        ),
        puntos=[
            PuntoContexto(id="b19-entrada", nombre="Bloque 19 - entrada", alias=["el 19"]),
            PuntoContexto(id="b19-cafeteria", nombre="Bloque 19 - cafeteria", alias=["el 19"]),
        ],
        franjas_abiertas=[FranjaContexto(id="f-1200", inicio="12:00", fin="12:30")],
    )
    traza = Traza(componente="busqueda")
    interpretacion = interprete.interpretar(entrada, traza)
    consulta = interpretacion.consulta
    assert isinstance(consulta, ConsultaInterpretada)
    assert consulta.es_busqueda
    assert consulta.precio_max_unitario_cop == 5000
    assert traza.tokens_entrada > 0
    print("\nconsulta:", consulta.model_dump_json(exclude_defaults=True))
    print("tokens:", traza.tokens_entrada, traza.tokens_salida, traza.tokens_razonamiento)
    print("pasos:", [(p.nombre, p.decision) for p in traza.pasos])
