"""La raiz de composicion: el UNICO lugar que instancia adaptadores concretos.

Lee `Settings`, arma los adaptadores (SQL, LLM, correo, push) y los casos de uso,
y los entrega en un `Contenedor` (API) o un `Worker`. Cambiar un adaptador por
otro (Gemini por otro proveedor, palabras clave por intencion) se decide aqui,
por configuracion.

    uvicorn umarket.arranque:app --factory     # API
    umarket-worker                             # worker
"""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from fastapi import FastAPI
from sqlalchemy.orm import Session, sessionmaker

from umarket.bd.motor import crear_fabrica_sesiones, crear_motor, verificar_conexion
from umarket.busqueda import (
    Buscar,
    ConfigBusqueda,
    InterpreteConRespaldo,
    InterpreteConsulta,
    InterpretePorPalabras,
    RefinarBusqueda,
    RegistrarClic,
    reglas_consulta,
)
from umarket.busqueda.adaptadores.interprete_llm import InterpreteLlm
from umarket.busqueda.adaptadores.sql import (
    BuscadorOfertasSql,
    LectorContextoBusquedaSql,
    RegistroBusquedasSql,
)
from umarket.busqueda.http import router as router_busqueda
from umarket.campus import ObtenerCampus
from umarket.campus.adaptadores.sql import UnidadCampusSql
from umarket.campus.http import router as router_campus
from umarket.catalogo import (
    CrearTienda,
    DuplicarTurnos,
    EditarStock,
    GuardarProducto,
    ListarTiendas,
    PublicarTurno,
    TiendaDeUsuario,
    VerMiTienda,
    VerTienda,
)
from umarket.catalogo.adaptadores.sql import ConsultasCatalogoSql, UnidadCatalogoSql
from umarket.catalogo.http import router as router_catalogo
from umarket.compartido.dominio.reloj import Reloj, RelojSistema
from umarket.config import RAIZ_BACKEND, Settings
from umarket.contenedor import Contenedor
from umarket.http.app import crear_app
from umarket.ia.adaptadores import ConfigLlm, build_llm
from umarket.ia.prompts import RegistroPrompts
from umarket.ia.puerto import LlmPort
from umarket.identidad import (
    CerrarSesion,
    PoliticaAcceso,
    ResolverSesion,
    SolicitarCodigo,
    VerificarCodigo,
)
from umarket.identidad.adaptadores.externos import (
    EnviadorCorreoConsola,
    GeneradorSecretosFijo,
    GeneradorSecretosSeguro,
)
from umarket.identidad.adaptadores.sql import UnidadIdentidadSql
from umarket.identidad.http import router as router_identidad
from umarket.notificaciones import PLANTILLAS, GestionarSuscripciones, NotificarEvento
from umarket.notificaciones.adaptadores.canales import (
    CanalRegistro,
    CanalWebPush,
    UnidadNotificacionesSql,
)
from umarket.notificaciones.http import router as router_avisos
from umarket.notificaciones.puertos import CanalNotificacion
from umarket.pedidos import (
    ActuarSobrePedido,
    ConsultarPedidos,
    CrearPedido,
    Limites,
    PoliticaPedidos,
    VencerPedidos,
    reglas_pedido,
)
from umarket.pedidos.adaptadores.sql import (
    ConsultasPedidosSql,
    GeneradorCodigosAleatorio,
    UnidadPedidosSql,
)
from umarket.pedidos.http import router as router_pedidos
from umarket.reputacion import Calificar, RecalcularMetricas, ResenasDeTienda, politica_ranking
from umarket.reputacion.adaptadores.sql import FuenteReputacionSql, UnidadReputacionSql
from umarket.reputacion.http import router as router_reputacion
from umarket.worker.despachador import DespachadorEventos, Manejador

ROUTERS = (
    router_identidad,
    router_campus,
    router_catalogo,
    router_reputacion,
    router_pedidos,
    router_avisos,
    router_busqueda,
)


def _politica_pedidos(settings: Settings) -> PoliticaPedidos:
    return PoliticaPedidos(
        minutos_para_aprobar=settings.minutos_para_aprobar,
        limites=Limites(
            max_unidades_por_item=settings.max_unidades_por_item,
            pedidos_abiertos=settings.limite_pedidos_abiertos,
            inasistencias=settings.max_inasistencias,
        ),
    )


def config_llm(settings: Settings) -> ConfigLlm:
    return ConfigLlm(
        proveedor=settings.llm_provider,
        modelo=settings.llm_model,
        gemini_api_key=settings.gemini_api_key,
        replay_path=settings.llm_replay_path,
        tope_total_s=settings.busqueda_timeout_s,
        presupuesto_diario_usd=settings.llm_presupuesto_diario_usd,
        cache_dir=settings.llm_cache_dir,
    )


def interpretes_de(settings: Settings, llm: LlmPort | None = None) -> dict[str, InterpreteConsulta]:
    """El registro de interpretes (punto de extension, PLAN-TECNICO.md §3).

    El LLM solo se construye si se va a usar: en modo "palabras" no hace falta
    clave. "intencion" siempre lleva respaldo: si el modelo falla, responde el
    baseline.
    """
    palabras = InterpretePorPalabras()
    interpretes: dict[str, InterpreteConsulta] = {"palabras": palabras}
    if settings.busqueda_interprete in ("intencion", "ab") or llm is not None:
        modelo = InterpreteLlm(
            llm or build_llm(config_llm(settings)),
            RegistroPrompts(RAIZ_BACKEND / "prompts"),
            settings.prompt_busqueda,
            timeout_s=settings.busqueda_timeout_s,
        )
        interpretes["intencion"] = InterpreteConRespaldo(modelo, palabras)
    return interpretes


def construir(
    settings: Settings, reloj: Reloj | None = None, llm: LlmPort | None = None
) -> Contenedor:
    reloj = reloj or RelojSistema()
    motor = crear_motor(settings.database_url)
    fabrica = crear_fabrica_sesiones(motor)

    politica_acceso = PoliticaAcceso(
        secreto_servidor=settings.secreto_servidor,
        minutos_codigo=settings.minutos_codigo_acceso,
        max_intentos=settings.intentos_codigo_acceso,
        dias_sesion=settings.dias_sesion,
        version_terminos=settings.version_terminos,
    )
    secretos = (
        GeneradorSecretosFijo(settings.codigo_acceso_fijo)
        if settings.codigo_acceso_fijo
        else GeneradorSecretosSeguro()
    )

    def identidad() -> UnidadIdentidadSql:
        return UnidadIdentidadSql(fabrica)

    def campus() -> UnidadCampusSql:
        return UnidadCampusSql(fabrica)

    def catalogo() -> UnidadCatalogoSql:
        return UnidadCatalogoSql(fabrica)

    def pedidos() -> UnidadPedidosSql:
        return UnidadPedidosSql(fabrica)

    def reputacion() -> UnidadReputacionSql:
        return UnidadReputacionSql(fabrica)

    def notificaciones() -> UnidadNotificacionesSql:
        return UnidadNotificacionesSql(fabrica)

    ranking = politica_ranking(settings.ranking_version, settings.minimo_resenas_ranking)
    consultas_catalogo = ConsultasCatalogoSql(fabrica, reputacion=FuenteReputacionSql(ranking))
    # MVP de un campus: las consultas publicas usan la zona del campus por defecto.
    zona = settings.zona_horaria_por_defecto
    politica_pedidos = _politica_pedidos(settings)
    lector_busqueda = LectorContextoBusquedaSql(fabrica)
    buscador = BuscadorOfertasSql(fabrica)
    registro_busquedas = RegistroBusquedasSql(fabrica)

    return Contenedor(
        settings=settings,
        verificar_bd=lambda: verificar_conexion(motor),
        obtener_campus=ObtenerCampus(campus),
        solicitar_codigo=SolicitarCodigo(
            identidad, EnviadorCorreoConsola(), secretos, reloj, politica_acceso
        ),
        verificar_codigo=VerificarCodigo(identidad, secretos, reloj, politica_acceso),
        resolver_sesion=ResolverSesion(identidad, reloj, politica_acceso),
        cerrar_sesion=CerrarSesion(identidad, politica_acceso),
        tienda_de_usuario=TiendaDeUsuario(consultas_catalogo).ejecutar,
        listar_tiendas=ListarTiendas(consultas_catalogo, reloj, zona),
        ver_tienda=VerTienda(consultas_catalogo, reloj, zona),
        crear_tienda=CrearTienda(catalogo, reloj),
        ver_mi_tienda=VerMiTienda(catalogo, reloj),
        guardar_producto=GuardarProducto(catalogo),
        publicar_turno=PublicarTurno(catalogo, reloj),
        editar_stock=EditarStock(catalogo),
        duplicar_turnos=DuplicarTurnos(catalogo, reloj),
        crear_pedido=CrearPedido(
            pedidos,
            reglas_pedido(settings.reglas_pedido),
            GeneradorCodigosAleatorio(),
            reloj,
            politica_pedidos,
        ),
        actuar_sobre_pedido=ActuarSobrePedido(pedidos, reloj, politica_pedidos),
        consultar_pedidos=ConsultarPedidos(ConsultasPedidosSql(fabrica), reloj, zona),
        calificar=Calificar(reputacion, reloj),
        resenas_de_tienda=ResenasDeTienda(reputacion),
        suscripciones=GestionarSuscripciones(notificaciones),
        buscar=Buscar(
            interpretes_de(settings, llm),
            reglas_consulta(settings.reglas_consulta),
            lector_busqueda,
            buscador,
            registro_busquedas,
            reloj,
            ConfigBusqueda(settings.busqueda_interprete, settings.prompt_busqueda),
        ),
        refinar_busqueda=RefinarBusqueda(
            reglas_consulta("filtros-v1"), lector_busqueda, buscador, registro_busquedas, reloj
        ),
        registrar_clic=RegistrarClic(registro_busquedas, reloj),
    )


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Worker:
    vencer_pedidos: VencerPedidos
    despachador: DespachadorEventos


def canales_de(settings: Settings, fabrica: sessionmaker[Session]) -> list[CanalNotificacion]:
    """El registro siempre; Web Push solo si hay claves VAPID configuradas."""
    canales: list[CanalNotificacion] = [CanalRegistro()]
    if settings.vapid_clave_privada:
        canales.append(CanalWebPush(fabrica, settings.vapid_clave_privada, settings.vapid_contacto))
    return canales


def manejadores(
    notificar: NotificarEvento, recalcular: RecalcularMetricas
) -> dict[str, list[Manejador]]:
    """Que reacciona a cada evento. Una reaccion nueva es una linea aqui (OCP)."""
    registro: dict[str, list[Manejador]] = defaultdict(list)
    for tipo in PLANTILLAS:
        registro[tipo].append(notificar.manejar)
    for tipo in RecalcularMetricas.EVENTOS:
        registro[tipo].append(recalcular.manejar)
    return dict(registro)


def construir_worker(
    settings: Settings,
    reloj: Reloj | None = None,
    canales: Sequence[CanalNotificacion] | None = None,
) -> Worker:
    reloj = reloj or RelojSistema()
    fabrica = crear_fabrica_sesiones(crear_motor(settings.database_url))

    def pedidos() -> UnidadPedidosSql:
        return UnidadPedidosSql(fabrica)

    def reputacion() -> UnidadReputacionSql:
        return UnidadReputacionSql(fabrica)

    notificar = NotificarEvento(canales if canales is not None else canales_de(settings, fabrica))
    return Worker(
        vencer_pedidos=VencerPedidos(pedidos, reloj),
        despachador=DespachadorEventos(
            fabrica, manejadores(notificar, RecalcularMetricas(reputacion, reloj)), reloj
        ),
    )


def crear(settings: Settings, reloj: Reloj | None = None) -> FastAPI:
    return crear_app(construir(settings, reloj), ROUTERS)


def app() -> FastAPI:
    return crear(Settings())
