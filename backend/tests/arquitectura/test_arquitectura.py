"""Las reglas de dependencia que import-linter no expresa bien (PLAN-TECNICO.md §2.3).

Regla 3: un modulo de negocio solo importa la API publica de otro (su `__init__`).
         Excepcion: los adaptadores pueden leer las tablas de otros modulos
         (lecturas cruzadas, CQRS ligero).
Regla 5: ningun codigo fuera de `adaptadores/`, `arranque.py` y `bd/esquema.py`
         importa adaptadores. Solo la raiz de composicion los instancia.

Leen los imports con `ast`, como `test_pureza.py` en QuickDev: una regla en un
documento no es una garantia; una comprobacion que corre si.
"""

import ast
from collections.abc import Iterator
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2] / "src" / "umarket"
MODULOS = {"identidad", "campus", "catalogo", "pedidos", "reputacion", "busqueda", "notificaciones"}
PUEDEN_IMPORTAR_ADAPTADORES = {"arranque.py", "bd/esquema.py"}


def _imports(archivo: Path) -> Iterator[str]:
    arbol = ast.parse(archivo.read_text(encoding="utf-8"))
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            yield from (a.name for a in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module and nodo.level == 0:
            yield nodo.module


def _archivos() -> Iterator[tuple[str, Path]]:
    for archivo in RAIZ.rglob("*.py"):
        yield archivo.relative_to(RAIZ).as_posix(), archivo


def test_regla_3_solo_api_publica_entre_modulos() -> None:
    violaciones = []
    for relativo, archivo in _archivos():
        partes = relativo.split("/")
        propio = partes[0]
        if propio not in MODULOS or "adaptadores" in partes:
            continue
        for importado in _imports(archivo):
            trozos = importado.split(".")
            if (
                len(trozos) >= 3
                and trozos[0] == "umarket"
                and trozos[1] in MODULOS
                and trozos[1] != propio
            ):
                violaciones.append(f"{relativo} importa {importado}; usa `umarket.{trozos[1]}`")
    assert not violaciones, "\n".join(violaciones)


def test_regla_5_solo_la_raiz_de_composicion_conoce_adaptadores() -> None:
    violaciones = []
    for relativo, archivo in _archivos():
        if relativo in PUEDEN_IMPORTAR_ADAPTADORES or "/adaptadores/" in f"/{relativo}":
            continue
        for importado in _imports(archivo):
            if ".adaptadores" in importado and importado.startswith("umarket."):
                violaciones.append(f"{relativo} importa {importado}")
    assert not violaciones, "\n".join(violaciones)


def test_las_reglas_detectan_violaciones(tmp_path: Path) -> None:
    """Un test de arquitectura que nunca falla no prueba nada: se comprueba el detector."""
    falso = tmp_path / "x.py"
    falso.write_text(
        "from umarket.pedidos.adaptadores.sql import X\nimport umarket.catalogo.dominio\n"
    )
    assert list(_imports(falso)) == ["umarket.pedidos.adaptadores.sql", "umarket.catalogo.dominio"]
