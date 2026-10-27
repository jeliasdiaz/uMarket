"""Evals de la busqueda por intencion (PLAN-TECNICO.md §11; disciplina de QuickDev).

Mide EL pipeline desplegado: `Buscar`, armado por la raiz de composicion real,
contra el catalogo fixture en un Postgres de evals y con el reloj fijo en las
11:20 del 3 de noviembre de 2026. Cada corrida escribe su propio directorio en
`evals/resultados/` y nunca pisa otra (ADR-0007 de QuickDev).

    python -m evals correr --interprete palabras                    # baseline, n=1
    python -m evals correr --interprete intencion --n 3             # Gemini en vivo
    python -m evals correr --interprete intencion --replay <crudo>  # sin red
    python -m evals comparar <dir_baseline> <dir_after>             # puerta de entrada

Cada consulta del dataset dice que productos son relevantes y que filtros se
esperan. Por cada corrida se mide:
  - acierto@5: algun producto relevante entre los 5 primeros;
  - filtros_ok: los filtros esperados coinciden con la consulta final;
  - inventados: filtros que la consulta trae y el dataset dice que no deberia
    (en la consulta final y en el CRUDO del modelo: la diferencia separa "fallo el
    prompt" de "lo salvo el validador");
  - respaldo, latencia de interpretacion, tokens y costo.
"""

import csv
import json
import os
import statistics
import subprocess
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text

from evals.fixture import sembrar_fixture
from scripts.sembrar_datos import sembrar_campus
from umarket.arranque import construir
from umarket.busqueda import Buscar, ResultadoBusqueda
from umarket.compartido.dominio.reloj import RelojFijo
from umarket.config import RAIZ_BACKEND, Settings
from umarket.ia.adaptadores import ConfigLlm, build_llm
from umarket.ia.adaptadores.fake import FakeLlm
from umarket.ia.puerto import LlmPort, LlmRequest, LlmResponse
from umarket.ia.traza import Traza

RAIZ_EVALS = Path(__file__).resolve().parent
DATASET = RAIZ_EVALS / "datos" / "consultas.jsonl"
RESULTADOS = RAIZ_EVALS / "resultados"
URL_EVALS = os.environ.get(
    "DATABASE_URL_EVALS", "postgresql+psycopg://umarket:umarket@localhost:5433/umarket_evals"
)
FECHA = date(2026, 11, 3)
INSTANTE = datetime(2026, 11, 3, 16, 20, tzinfo=UTC)  # 11:20 en Bogota
CAMPOS_COMPARABLES = (
    "precio_max_unitario_cop",
    "presupuesto_total_cop",
    "franja_id",
    "punto_id",
    "punto_candidatos",
)


@dataclass(frozen=True)
class Caso:
    id: str
    conjunto: str
    categoria: str
    texto: str
    relevantes: list[str]
    filtros: dict[str, Any]
    hipotesis: str


def cargar_casos(conjunto: str = "todo") -> list[Caso]:
    casos = [
        Caso(**json.loads(linea)) for linea in DATASET.read_text("utf-8").splitlines() if linea
    ]
    return [c for c in casos if conjunto == "todo" or c.conjunto == conjunto]


def preparar_bd(url: str = URL_EVALS) -> tuple[Engine, dict[str, Any]]:
    motor = create_engine(url)
    with motor.begin() as c:
        c.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        c.execute(text("CREATE SCHEMA public"))
    cfg = Config(str(RAIZ_BACKEND / "alembic.ini"))
    cfg.attributes["url"] = url
    command.upgrade(cfg, "head")
    sembrar_campus(motor)
    return motor, sembrar_fixture(motor, FECHA)


class Grabador:
    """Envuelve el LLM y guarda payload y salida de cada llamada: es el `crudo.json`."""

    def __init__(self, inner: LlmPort) -> None:
        self.inner = inner
        self.llamadas: list[tuple[dict[str, Any], dict[str, Any]]] = []

    def complete_json(self, request: LlmRequest) -> LlmResponse:
        respuesta = self.inner.complete_json(request)
        self.llamadas.append((request.payload, respuesta.data))
        return respuesta


@dataclass
class Fila:
    caso: str
    corrida: int
    conjunto: str
    categoria: str
    interprete_usado: str
    acierto5: bool
    filtros_ok: bool
    inventados: list[str]
    inventados_crudo: list[str]
    respaldo: bool
    sin_resultados: bool
    latencia_interpretar_s: float
    tokens: int
    costo_usd: float | None
    top5: list[str] = field(default_factory=list[str])


def _valor(consulta: dict[str, Any], campo: str) -> Any:
    valor = consulta.get(campo)
    return sorted(valor) if isinstance(valor, list) else valor


def _inventados(consulta: dict[str, Any] | None, esperado: dict[str, Any]) -> list[str]:
    if consulta is None:
        return []
    return [
        campo
        for campo, esperado_valor in esperado.items()
        if esperado_valor in (None, []) and _valor(consulta, campo) not in (None, [])
    ]


def evaluar(
    caso: Caso, corrida: int, r: ResultadoBusqueda, traza: Traza, nombres: dict[Any, str]
) -> Fila:
    productos = [p.producto_id for t in r.tiendas for p in t.productos]
    top5 = [nombres.get(p, str(p)) for p in productos[:5]]
    comodin = "*" in caso.relevantes
    acierto = bool(productos) if comodin else bool(set(caso.relevantes) & set(top5))
    final = r.consulta.model_dump(mode="json")
    crudo = next((p.metadatos.get("crudo") for p in traza.pasos if p.nombre == "interpretar"), None)
    return Fila(
        caso=caso.id,
        corrida=corrida,
        conjunto=caso.conjunto,
        categoria=caso.categoria,
        interprete_usado=r.interprete,
        acierto5=acierto,
        filtros_ok=all(
            _valor(final, c) == (sorted(v) if isinstance(v, list) else v)
            for c, v in caso.filtros.items()
        ),
        inventados=_inventados(final, caso.filtros),
        inventados_crudo=_inventados(crudo if isinstance(crudo, dict) else None, caso.filtros),
        respaldo=any(p.nombre == "respaldo" for p in traza.pasos),
        sin_resultados=not productos,
        latencia_interpretar_s=round(
            sum(p.duracion_s for p in traza.pasos if p.nombre == "interpretar"), 3
        ),
        tokens=traza.tokens_entrada + traza.tokens_salida + traza.tokens_razonamiento,
        costo_usd=traza.costo_usd,
        top5=top5,
    )


def _git_sha() -> str:
    try:
        salida = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        )
        return salida.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "sin-commit"


def correr(
    interprete: str,
    n: int,
    conjunto: str,
    replay: Path | None,
    timeout_s: float,
    reglas: str | None = None,
    resultados: Path = RESULTADOS,
    url: str = URL_EVALS,
) -> Path:
    motor, claves = preparar_bd(url)
    nombres = {v: k for k, v in claves.items()}
    settings = Settings(
        entorno="test",
        database_url=url,
        busqueda_interprete="intencion" if interprete == "intencion" else "palabras",
        busqueda_timeout_s=timeout_s,
    )
    if reglas:
        settings = settings.model_copy(update={"reglas_consulta": reglas})
    grabador: Grabador | None = None
    llm: LlmPort | None = None
    if interprete == "intencion":
        if replay is not None:
            base: LlmPort = FakeLlm.desde_archivo(replay, model="replay")
        else:
            # Sin cache: medir es muestrear (ADR-0012 de QuickDev).
            base = build_llm(
                ConfigLlm(
                    proveedor=settings.llm_provider,
                    modelo=settings.llm_model,
                    gemini_api_key=settings.gemini_api_key,
                    reintentos=1,
                    tope_total_s=timeout_s,
                    presupuesto_diario_usd=settings.llm_presupuesto_diario_usd,
                )
            )
        grabador = Grabador(base)
        llm = grabador
    buscar: Buscar = construir(settings, RelojFijo(INSTANTE), llm=llm).buscar

    filas: list[Fila] = []
    crudo: dict[str, Any] = {}
    for caso in cargar_casos(conjunto):
        for i in range(1, n + 1):
            antes = len(grabador.llamadas) if grabador else 0
            resultado, traza = buscar.ejecutar_con_traza(caso.texto, "campus-demo")
            filas.append(evaluar(caso, i, resultado, traza, nombres))
            if grabador and len(grabador.llamadas) > antes:
                payload, salida = grabador.llamadas[-1]
                crudo[f"{caso.id}_run{i}"] = {"payload": payload, "output_crudo": salida}
    motor.dispose()

    modo = interprete if interprete == "palabras" else f"{interprete}-{settings.prompt_busqueda}"
    sufijo = "-replay" if replay else ""
    destino = (
        resultados
        / f"{datetime.now(UTC):%Y-%m-%d}-busqueda-{modo}-{settings.reglas_consulta}{sufijo}"
    )
    destino.mkdir(parents=True, exist_ok=True)
    resumen = resumir(filas)
    manifiesto = {
        "interprete": interprete,
        "prompt_version": settings.prompt_busqueda if interprete == "intencion" else None,
        "reglas": settings.reglas_consulta,
        "modelo": "replay"
        if replay
        else (settings.llm_model if interprete == "intencion" else None),
        "proveedor": settings.llm_provider if interprete == "intencion" else None,
        "n": n,
        "conjunto": conjunto,
        "timeout_s": timeout_s,
        "replay_de": str(replay) if replay else None,
        "git_sha": _git_sha(),
        "fecha": datetime.now(UTC).isoformat(timespec="seconds"),
        "dataset": "SINTETICO (semilla del equipo); se reemplaza con consultas reales de la Fase 0",
        "resumen": resumen,
    }
    (destino / "manifiesto.json").write_text(
        json.dumps(manifiesto, indent=2, ensure_ascii=False), "utf-8"
    )
    if crudo:
        (destino / "crudo.json").write_text(
            json.dumps(crudo, indent=1, ensure_ascii=False), "utf-8"
        )
    with (destino / "resultados.csv").open("w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=list(asdict(filas[0])))
        escritor.writeheader()
        for fila in filas:
            escritor.writerow(
                {k: json.dumps(v) if isinstance(v, list) else v for k, v in asdict(fila).items()}
            )
    (destino / "resumen.md").write_text(_markdown(manifiesto, filas), "utf-8")
    return destino


def _p95(valores: list[float]) -> float:
    if not valores:
        return 0.0
    ordenados = sorted(valores)
    return ordenados[min(len(ordenados) - 1, round(0.95 * (len(ordenados) - 1)))]


def resumir(filas: list[Fila]) -> dict[str, Any]:
    def bloque(fs: list[Fila]) -> dict[str, Any]:
        latencias = [f.latencia_interpretar_s for f in fs]
        costos = [f.costo_usd for f in fs]
        return {
            "corridas": len(fs),
            "acierto5": round(sum(f.acierto5 for f in fs) / len(fs), 3),
            "filtros_ok": round(sum(f.filtros_ok for f in fs) / len(fs), 3),
            "inventados": sum(len(f.inventados) for f in fs),
            "inventados_crudo": sum(len(f.inventados_crudo) for f in fs),
            "respaldo": round(sum(f.respaldo for f in fs) / len(fs), 3),
            "sin_resultados": sum(f.sin_resultados for f in fs),
            "latencia_p50_s": round(statistics.median(latencias), 3),
            "latencia_p95_s": round(_p95(latencias), 3),
            "tokens_promedio": round(statistics.mean(f.tokens for f in fs), 1),
            "costo_total_usd": None
            if any(c is None for c in costos)
            else round(sum(c or 0 for c in costos), 6),
        }

    por: dict[str, list[Fila]] = defaultdict(list)
    for f in filas:
        por[f"categoria:{f.categoria}"].append(f)
        por[f"conjunto:{f.conjunto}"].append(f)
    return {"global": bloque(filas), **{k: bloque(v) for k, v in sorted(por.items())}}


def _markdown(manifiesto: dict[str, Any], filas: list[Fila]) -> str:
    r = manifiesto["resumen"]
    lineas = [
        f"# Eval de busqueda: {manifiesto['interprete']}"
        + (
            f" (prompt {manifiesto['prompt_version']}, {manifiesto['modelo']})"
            if manifiesto["prompt_version"]
            else ""
        ),
        "",
        f"- Fecha: {manifiesto['fecha']} · git: {manifiesto['git_sha']} · "
        f"n = {manifiesto['n']} · reglas: {manifiesto['reglas']}",
        f"- Dataset: {manifiesto['dataset']}",
        "",
        "| Grupo | corridas | acierto@5 | filtros ok | inventados (final / crudo) "
        "| respaldo | p50 s | p95 s | costo USD |",
        "| --- | --: | --: | --: | --: | --: | --: | --: | --: |",
    ]
    for grupo, b in r.items():
        lineas.append(
            f"| {grupo} | {b['corridas']} | {b['acierto5']:.0%} | {b['filtros_ok']:.0%} | "
            f"{b['inventados']} / {b['inventados_crudo']} | {b['respaldo']:.0%} | "
            f"{b['latencia_p50_s']} | {b['latencia_p95_s']} | {b['costo_total_usd']} |"
        )
    lineas += [
        "",
        "## Fallos",
        "",
        "| caso | corrida | acierto@5 | filtros | inventados | top 5 |",
        "| --- | --: | --- | --- | --- | --- |",
    ]
    for f in filas:
        if not (f.acierto5 and f.filtros_ok and not f.inventados):
            lineas.append(
                f"| {f.caso} | {f.corrida} | {'si' if f.acierto5 else 'NO'} | "
                f"{'ok' if f.filtros_ok else 'NO'} | {', '.join(f.inventados) or '-'} | "
                f"{', '.join(f.top5[:3])} |"
            )
    return "\n".join(lineas) + "\n"


# ---------------------------------------------------------------------------
# Comparacion: la puerta de entrada de Gemini (PLAN-Y-DECISIONES.md §4.3)
# ---------------------------------------------------------------------------

UMBRAL_PUNTOS = 0.15
UMBRAL_P95_S = 2.0


def comparar(baseline: Path, after: Path) -> tuple[bool, str]:
    b = json.loads((baseline / "manifiesto.json").read_text("utf-8"))["resumen"]
    manifiesto_after = json.loads((after / "manifiesto.json").read_text("utf-8"))
    a = manifiesto_after["resumen"]
    # Un replay no tiene latencia real: se usa la de la corrida en vivo que reproduce.
    origen_latencia = after
    if manifiesto_after.get("replay_de"):
        origen_latencia = Path(manifiesto_after["replay_de"]).parent
    latencias = json.loads((origen_latencia / "manifiesto.json").read_text("utf-8"))["resumen"]
    clave = "conjunto:test" if "conjunto:test" in a and "conjunto:test" in b else "global"
    delta = a[clave]["acierto5"] - b[clave]["acierto5"]
    adversarial = a.get("categoria:adversarial", {}).get("inventados", 0)
    p95 = latencias["global"]["latencia_p95_s"]
    condiciones = [
        (
            f"acierto@5 ({clave}) sube >= {UMBRAL_PUNTOS:.0%}: {b[clave]['acierto5']:.0%} -> "
            f"{a[clave]['acierto5']:.0%} ({delta:+.0%})",
            delta >= UMBRAL_PUNTOS,
        ),
        (f"cero filtros inventados en adversariales: {adversarial}", adversarial == 0),
        (
            f"p95 de interpretacion <= {UMBRAL_P95_S}s: {p95}s (de {origen_latencia.name})",
            p95 <= UMBRAL_P95_S,
        ),
    ]
    texto = "\n".join(f"  [{'OK' if ok else 'NO'}] {d}" for d, ok in condiciones)
    pasa = all(ok for _, ok in condiciones)
    return (
        pasa,
        texto
        + f"\n  => Gemini {'ENTRA' if pasa else 'NO entra'} (umbral de PLAN-Y-DECISIONES §4.3)",
    )
