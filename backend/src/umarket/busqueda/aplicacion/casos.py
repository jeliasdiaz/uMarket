"""Casos de uso de la busqueda: buscar, refinar sin modelo y registrar clics.

El flujo de `Buscar` (PLAN-TECNICO.md §6.1):

    texto -> redactar datos personales -> interpretar (Gemini o palabras clave)
          -> validar (consulta-v1) -> corregir (anular filtros sin respaldo)
          -> SQL: solo ofertas con stock en franjas abiertas
          -> relajacion determinista si no hay nada -> agrupar por tienda
          -> registrar busqueda y traza

El modelo SOLO interpreta. Los resultados, el stock, los precios y el orden los
pone el codigo; el comprador ve los filtros y decide.
"""

import hashlib
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from umarket.busqueda.aplicacion.interpretes import InterpretePorPalabras
from umarket.busqueda.aplicacion.vistas import (
    Oferta,
    OpcionPunto,
    ProductoEncontrado,
    RegistroBusqueda,
    ResultadoBusqueda,
    TiendaEncontrada,
)
from umarket.busqueda.dominio.contrato import (
    SCHEMA_VERSION,
    ConsultaInterpretada,
    EntradaInterprete,
    FranjaContexto,
    Orden,
    PuntoContexto,
    Vocabulario,
)
from umarket.busqueda.dominio.correccion import PoliticaCorreccionConsulta
from umarket.busqueda.dominio.filtros import describir
from umarket.busqueda.dominio.privacidad import redactar
from umarket.busqueda.dominio.reglas import ContextoConsulta
from umarket.busqueda.puertos import (
    BuscadorOfertas,
    ContextoCampusBusqueda,
    InterpreteConsulta,
    LectorContextoBusqueda,
    RegistroBusquedas,
)
from umarket.catalogo import CATEGORIAS, ETIQUETAS
from umarket.compartido.dominio.errores import NoEncontrado, ReglaIncumplida
from umarket.compartido.dominio.reglas import ConjuntoReglas, Validador
from umarket.compartido.dominio.reloj import Reloj
from umarket.ia.traza import Traza

LARGO_MAXIMO = 200
LIMITE_OFERTAS = 60
# Orden de relajacion: primero lo que mas restringe y menos importa.
RELAJACION = ("punto", "franja", "precio")


@dataclass(frozen=True)
class ConfigBusqueda:
    modo: str  # "palabras", "intencion" o "ab"
    prompt_version: str = ""


class Buscar:
    def __init__(
        self,
        interpretes: Mapping[str, InterpreteConsulta],
        reglas: ConjuntoReglas[ConsultaInterpretada, ContextoConsulta],
        lector: LectorContextoBusqueda,
        buscador: BuscadorOfertas,
        registro: RegistroBusquedas,
        reloj: Reloj,
        config: ConfigBusqueda,
    ) -> None:
        self._interpretes = interpretes
        self._validador = Validador(reglas)
        self._correccion = PoliticaCorreccionConsulta()
        self._lector = lector
        self._buscador = buscador
        self._registro = registro
        self._reloj = reloj
        self._config = config
        self._palabras = InterpretePorPalabras()

    def ejecutar(
        self, texto: str, campus_id: str, usuario_id: UUID | None = None, semilla: str = ""
    ) -> ResultadoBusqueda:
        return self.ejecutar_con_traza(texto, campus_id, usuario_id, semilla)[0]

    def ejecutar_con_traza(
        self, texto: str, campus_id: str, usuario_id: UUID | None = None, semilla: str = ""
    ) -> tuple[ResultadoBusqueda, Traza]:
        """Lo mismo que `ejecutar`, mas la traza. Los evals la usan: miden ESTE pipeline."""
        inicio = time.perf_counter()
        texto = redactar(" ".join(texto.split()))[:LARGO_MAXIMO]
        if not texto:
            raise ReglaIncumplida("busqueda_vacia", "Escribe que se te antoja.")
        ahora = self._reloj.ahora()
        ctx = self._lector.contexto(campus_id, ahora)
        entrada = entrada_para(texto, ctx, ahora)

        interprete = self._elegir(semilla or str(usuario_id or ""))
        traza = Traza(
            componente="busqueda",
            prompt_version=self._config.prompt_version if interprete.nombre != "palabras" else "",
            schema_version=SCHEMA_VERSION,
            rules_version=self._validador.version,
        )
        interpretacion = interprete.interpretar(entrada, traza)
        consulta, anulados, usar_respaldo = self._verificar(interpretacion.consulta, entrada, traza)
        origen = interpretacion.origen
        if usar_respaldo and origen != self._palabras.nombre:
            traza.paso("respaldo", "la consulta del modelo no tenia nada utilizable")
            interpretacion = self._palabras.interpretar(entrada, traza)
            consulta, anulados, _ = self._verificar(interpretacion.consulta, entrada, traza)
            origen = interpretacion.origen

        ofertas, relajados = self._buscar(consulta, ctx, ahora, traza)
        tiendas = agrupar(ofertas, consulta)
        resultado = ResultadoBusqueda(
            busqueda_id=uuid4(),
            interprete=origen,
            consulta=consulta,
            filtros=tuple(describir(consulta, *_nombres(ctx))),
            anulados=anulados,
            relajados=relajados,
            tiendas=tiendas,
            pregunta_punto=_pregunta_punto(consulta, ctx),
        )
        self._registro.registrar(
            RegistroBusqueda(
                id=resultado.busqueda_id,
                campus_id=campus_id,
                usuario_id=usuario_id,
                texto=texto,
                interprete=origen,
                consulta=consulta,
                anulados=anulados,
                relajados=relajados,
                n_tiendas=len(tiendas),
                n_productos=sum(len(t.productos) for t in tiendas),
                latencia_ms=int((time.perf_counter() - inicio) * 1000),
                creada_en=ahora,
            ),
            traza,
        )
        return resultado, traza

    def _elegir(self, semilla: str) -> InterpreteConsulta:
        if self._config.modo == "ab":
            par = int(hashlib.sha256(semilla.encode()).hexdigest(), 16) % 2
            return self._interpretes["intencion" if par else "palabras"]
        return self._interpretes[self._config.modo]

    def _verificar(
        self, consulta: ConsultaInterpretada, entrada: EntradaInterprete, traza: Traza
    ) -> tuple[ConsultaInterpretada, tuple[str, ...], bool]:
        contexto = contexto_reglas(entrada)
        hallazgos = self._validador.validar(consulta, contexto)
        correccion = self._correccion.corregir(consulta, hallazgos, contexto)
        traza.paso(
            "validar",
            f"{len(hallazgos)} hallazgo(s) con '{self._validador.version}'",
            hallazgos=[h.regla_id for h in hallazgos],
            anulados=list(correccion.anulados),
        )
        return correccion.consulta, correccion.anulados, correccion.usar_respaldo

    def _buscar(
        self,
        consulta: ConsultaInterpretada,
        ctx: ContextoCampusBusqueda,
        ahora: datetime,
        traza: Traza,
    ) -> tuple[list[Oferta], tuple[str, ...]]:
        return buscar_con_relajacion(self._buscador, consulta, ctx, ahora, traza)


class RefinarBusqueda:
    """Quitar un filtro vuelve a buscar SIN llamar al modelo (PLAN-TECNICO.md §6.5).

    Los filtros editados a mano no tienen texto que los respalde: se validan con
    `filtros-v1` (ids existentes, montos plausibles), no con `consulta-v1`.
    """

    def __init__(
        self,
        reglas: ConjuntoReglas[ConsultaInterpretada, ContextoConsulta],
        lector: LectorContextoBusqueda,
        buscador: BuscadorOfertas,
        registro: RegistroBusquedas,
        reloj: Reloj,
    ) -> None:
        self._validador = Validador(reglas)
        self._correccion = PoliticaCorreccionConsulta()
        self._lector = lector
        self._buscador = buscador
        self._registro = registro
        self._reloj = reloj

    def ejecutar(
        self, busqueda_id: UUID, consulta: ConsultaInterpretada, campus_id: str
    ) -> ResultadoBusqueda:
        texto = self._registro.texto_de(busqueda_id)
        if texto is None:
            raise NoEncontrado("busqueda_no_encontrada", "Esa busqueda no existe.")
        ahora = self._reloj.ahora()
        ctx = self._lector.contexto(campus_id, ahora)
        contexto = contexto_reglas(entrada_para(texto, ctx, ahora))
        hallazgos = self._validador.validar(consulta, contexto)
        correccion = self._correccion.corregir(consulta, hallazgos, contexto)
        traza = Traza(componente="busqueda.refinar", rules_version=self._validador.version)
        ofertas, relajados = buscar_con_relajacion(
            self._buscador, correccion.consulta, ctx, ahora, traza
        )
        return ResultadoBusqueda(
            busqueda_id=busqueda_id,
            interprete="filtros",
            consulta=correccion.consulta,
            filtros=tuple(describir(correccion.consulta, *_nombres(ctx))),
            anulados=correccion.anulados,
            relajados=relajados,
            tiendas=agrupar(ofertas, correccion.consulta),
            pregunta_punto=_pregunta_punto(correccion.consulta, ctx),
        )


class RegistrarClic:
    def __init__(self, registro: RegistroBusquedas, reloj: Reloj) -> None:
        self._registro = registro
        self._reloj = reloj

    def ejecutar(
        self, busqueda_id: UUID, tienda_id: UUID, producto_id: UUID | None, posicion: int
    ) -> None:
        if self._registro.texto_de(busqueda_id) is None:
            raise NoEncontrado("busqueda_no_encontrada", "Esa busqueda no existe.")
        self._registro.registrar_clic(
            busqueda_id, tienda_id, producto_id, posicion, self._reloj.ahora()
        )


# ---------------------------------------------------------------------------
# Piezas compartidas (tambien las usa el runner de evals)
# ---------------------------------------------------------------------------


def entrada_para(texto: str, ctx: ContextoCampusBusqueda, ahora: datetime) -> EntradaInterprete:
    return EntradaInterprete(
        texto=texto,
        ahora=ahora.astimezone(ZoneInfo(ctx.zona_horaria)).isoformat(timespec="minutes"),
        vocabulario=Vocabulario(
            categorias=list(CATEGORIAS),
            etiquetas=list(ETIQUETAS),
            productos_hoy=ctx.productos_hoy,
        ),
        puntos=[PuntoContexto(id=p.id, nombre=p.nombre, alias=list(p.alias)) for p in ctx.puntos],
        franjas_abiertas=[
            FranjaContexto(id=f.id, inicio=f"{f.hora_inicio:%H:%M}", fin=f"{f.hora_fin:%H:%M}")
            for f in ctx.franjas_abiertas
        ],
    )


def contexto_reglas(entrada: EntradaInterprete) -> ContextoConsulta:
    return ContextoConsulta(
        texto=entrada.texto,
        puntos=frozenset(p.id for p in entrada.puntos),
        franjas_abiertas=frozenset(f.id for f in entrada.franjas_abiertas),
    )


def buscar_con_relajacion(
    buscador: BuscadorOfertas,
    consulta: ConsultaInterpretada,
    ctx: ContextoCampusBusqueda,
    ahora: datetime,
    traza: Traza,
) -> tuple[list[Oferta], tuple[str, ...]]:
    """Si no hay nada, quita filtros en un orden fijo y dice cuales quito."""
    inicio = time.perf_counter()
    actual = consulta
    relajados: list[str] = []
    ofertas = buscador.buscar(actual, ctx.campus_id, ctx.fecha, ahora, LIMITE_OFERTAS)
    for filtro in RELAJACION:
        if ofertas:
            break
        siguiente = _sin(actual, filtro)
        if siguiente is None:
            continue
        actual = siguiente
        relajados.append(filtro)
        ofertas = buscador.buscar(actual, ctx.campus_id, ctx.fecha, ahora, LIMITE_OFERTAS)
    traza.paso(
        "buscar",
        f"{len(ofertas)} oferta(s)" + (f", relajado: {', '.join(relajados)}" if relajados else ""),
        time.perf_counter() - inicio,
        relajados=relajados,
    )
    return ofertas, tuple(relajados)


def _sin(consulta: ConsultaInterpretada, filtro: str) -> ConsultaInterpretada | None:
    if filtro == "punto" and (consulta.punto_id or consulta.punto_candidatos):
        return consulta.model_copy(update={"punto_id": None, "punto_candidatos": []})
    if filtro == "franja" and consulta.franja_id:
        return consulta.model_copy(update={"franja_id": None})
    if filtro == "precio" and (consulta.precio_max_unitario_cop or consulta.presupuesto_total_cop):
        return consulta.model_copy(
            update={"precio_max_unitario_cop": None, "presupuesto_total_cop": None}
        )
    return None


def agrupar(ofertas: list[Oferta], consulta: ConsultaInterpretada) -> tuple[TiendaEncontrada, ...]:
    """Una tarjeta por tienda y turno, con sus productos; las mas relevantes primero."""
    grupos: dict[tuple[UUID, UUID], list[Oferta]] = {}
    for o in ofertas:
        grupos.setdefault((o.tienda_id, o.turno_id), []).append(o)

    def cantidad(o: Oferta) -> int:
        pedida = consulta.items[o.item].cantidad if o.item is not None else None
        return max(1, min(pedida or 1, o.disponible))

    tarjetas: list[tuple[tuple[float, ...], TiendaEncontrada]] = []
    for grupo in grupos.values():
        grupo.sort(key=lambda o: (-o.relevancia, o.precio_cop))
        primera = grupo[0]
        if consulta.orden is Orden.PRECIO:
            clave: tuple[float, ...] = (min(o.precio_cop for o in grupo),)
        elif consulta.orden is Orden.CALIFICACION:
            clave = (-(primera.promedio or 0), -primera.resenas)
        else:
            clave = (-max(o.relevancia for o in grupo), -(primera.promedio or 0))
        tarjetas.append(
            (
                clave,
                TiendaEncontrada(
                    tienda_id=primera.tienda_id,
                    slug=primera.tienda_slug,
                    nombre=primera.tienda_nombre,
                    promedio=primera.promedio,
                    resenas=primera.resenas,
                    turno_id=primera.turno_id,
                    franja_etiqueta=primera.franja_etiqueta,
                    punto_id=primera.punto_id,
                    punto_nombre=primera.punto_nombre,
                    productos=tuple(
                        ProductoEncontrado(
                            o.producto_id, o.nombre, o.precio_cop, o.disponible, cantidad(o)
                        )
                        for o in grupo[:6]
                    ),
                ),
            )
        )
    tarjetas.sort(key=lambda t: (*t[0], t[1].nombre))
    return tuple(t for _, t in tarjetas)


def _nombres(ctx: ContextoCampusBusqueda) -> tuple[dict[str, str], dict[str, str]]:
    return (
        {p.id: p.nombre for p in ctx.puntos},
        {f.id: f.etiqueta for f in ctx.franjas_abiertas},
    )


def _pregunta_punto(
    consulta: ConsultaInterpretada, ctx: ContextoCampusBusqueda
) -> tuple[OpcionPunto, ...]:
    """Dos puntos posibles: se pregunta "¿en cual?" con botones; nunca se adivina."""
    if consulta.punto_id or len(consulta.punto_candidatos) < 2:
        return ()
    nombres = {p.id: p.nombre for p in ctx.puntos}
    return tuple(OpcionPunto(p, nombres.get(p, p)) for p in consulta.punto_candidatos)
