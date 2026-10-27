from pathlib import Path

import pytest

from umarket.ia.prompts import PromptIntegrityError, RegistroPrompts, sha256_de
from umarket.ia.puerto import LlmResponse, UsoTokens
from umarket.ia.traza import Traza


def _escribir_prompt(directorio: Path, cuerpo: str, sha: str | None = None) -> None:
    (directorio / "busqueda").mkdir(parents=True, exist_ok=True)
    (directorio / "busqueda" / "v1.md").write_text(
        "---\nversion: v1\ncomponente: busqueda\nestado: sin_medir\nschema_version: v1\n"
        f"rules_version: consulta-v1\nsha256: {sha or sha256_de(cuerpo)}\n---{cuerpo}",
        encoding="utf-8",
    )


def test_carga_un_prompt_sellado(tmp_path: Path) -> None:
    _escribir_prompt(tmp_path, "\nEres el interprete.\n")
    registro = RegistroPrompts(tmp_path)
    assert registro.texto("busqueda", "v1") == "\nEres el interprete.\n"
    assert registro.metadatos("busqueda", "v1")["rules_version"] == "consulta-v1"


def test_un_cambio_sin_resellar_falla_al_cargar(tmp_path: Path) -> None:
    _escribir_prompt(tmp_path, "\nEres el interprete.\n", sha="0" * 64)
    with pytest.raises(PromptIntegrityError, match="version nueva"):
        RegistroPrompts(tmp_path)


def test_version_inexistente_lista_las_disponibles(tmp_path: Path) -> None:
    _escribir_prompt(tmp_path, "\nX\n")
    with pytest.raises(KeyError, match="v1"):
        RegistroPrompts(tmp_path).texto("busqueda", "v9")


def test_la_traza_suma_tokens_y_costo() -> None:
    traza = Traza(componente="busqueda")
    traza.registrar_llamada(
        LlmResponse(
            data={},
            raw_text="",
            model="gemini-2.5-flash-lite",
            provider="gemini",
            usage=UsoTokens(entrada=1_000_000, salida=0),
        )
    )
    assert traza.tokens_entrada == 1_000_000
    assert traza.costo_usd == pytest.approx(0.10)
    assert traza.a_dict()["proveedor"] == "gemini"


def test_un_costo_desconocido_contamina_el_total_a_none() -> None:
    traza = Traza(componente="busqueda")
    traza.registrar_llamada(
        LlmResponse(data={}, raw_text="", model="sin-precio", usage=UsoTokens(salida=10))
    )
    assert traza.costo_usd is None


def test_una_respuesta_de_cache_no_cuesta() -> None:
    traza = Traza(componente="busqueda")
    traza.registrar_llamada(
        LlmResponse(
            data={},
            raw_text="",
            model="gemini-2.5-flash-lite",
            from_cache=True,
            usage=UsoTokens(salida=99),
        )
    )
    assert traza.tokens_salida == 0
