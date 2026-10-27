"""El dominio de pedidos sin base de datos: maquina de estados, entidad y reglas."""

from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest

from umarket.compartido.dominio.errores import Conflicto, NoAutorizado, ReglaIncumplida
from umarket.compartido.dominio.reglas import Validador
from umarket.pedidos.dominio.estados import (
    ABIERTOS,
    TRANSICIONES,
    Accion,
    Actor,
    Estado,
    acciones_posibles,
)
from umarket.pedidos.dominio.pedido import ALFABETO_CODIGO, ItemPedido, Pedido
from umarket.pedidos.dominio.reglas import (
    ContextoPedido,
    Limites,
    LineaSolicitada,
    OfertaEnTurno,
    SolicitudPedido,
    reglas_pedido,
)

AHORA = datetime(2026, 11, 3, 16, 20, tzinfo=UTC)
VENDEDOR, COMPRADOR, OTRO = uuid4(), uuid4(), uuid4()


def _pedido(estado: Estado = Estado.PENDIENTE, **cambios: object) -> Pedido:
    base: dict[str, object] = {
        "id": uuid4(),
        "codigo": "K7P",
        "campus_id": "c",
        "tienda_id": uuid4(),
        "vendedor_id": VENDEDOR,
        "comprador_id": COMPRADOR,
        "turno_id": uuid4(),
        "fecha": date(2026, 11, 3),
        "franja_id": "f-1200",
        "punto_id": "b19",
        "items": (ItemPedido(uuid4(), "Pollo", 3000, 2), ItemPedido(uuid4(), "Queso", 3000, 1)),
        "estado": estado,
        "creado_en": AHORA,
        "vence_en": AHORA + timedelta(minutes=30),
        "actualizado_en": AHORA,
    }
    return Pedido(**{**base, **cambios})  # type: ignore[arg-type]


class TestPedido:
    def test_el_total_lo_calcula_la_entidad(self) -> None:
        assert _pedido().total_cop == 9000

    def test_no_hay_pedido_vacio(self) -> None:
        with pytest.raises(ReglaIncumplida):
            _pedido(items=())

    def test_alfabeto_sin_caracteres_ambiguos(self) -> None:
        assert not set("0O1IL2Z5S8B") & set(ALFABETO_CODIGO)

    def test_actor(self) -> None:
        p = _pedido()
        assert p.actor_de(VENDEDOR) is Actor.VENDEDOR
        assert p.actor_de(COMPRADOR) is Actor.COMPRADOR
        with pytest.raises(NoAutorizado):
            p.actor_de(OTRO)

    def test_estado_efectivo_de_un_pendiente_vencido(self) -> None:
        p = _pedido()
        assert p.estado_efectivo(AHORA) is Estado.PENDIENTE
        assert p.estado_efectivo(AHORA + timedelta(minutes=30)) is Estado.VENCIDO


class TestMaquinaDeEstados:
    @pytest.mark.parametrize(("desde", "accion"), list(TRANSICIONES))
    def test_cada_transicion_valida_lleva_a_su_destino(self, desde: Estado, accion: Accion) -> None:
        transicion = TRANSICIONES[(desde, accion)]
        actor = next(iter(transicion.actores))
        p = _pedido(desde, llegada_en=AHORA - timedelta(minutes=15))
        despues, t = p.aplicar(accion, actor, AHORA)
        assert despues.estado is t.hacia

    @pytest.mark.parametrize("desde", list(Estado))
    @pytest.mark.parametrize("accion", list(Accion))
    def test_toda_transicion_fuera_de_la_tabla_es_invalida(
        self, desde: Estado, accion: Accion
    ) -> None:
        if (desde, accion) in TRANSICIONES:
            return
        with pytest.raises(Conflicto) as error:
            _pedido(desde).aplicar(accion, Actor.VENDEDOR, AHORA)
        assert error.value.tipo == "transicion_invalida"

    def test_los_estados_finales_no_tienen_salida(self) -> None:
        for estado in set(Estado) - ABIERTOS:
            assert not any(e == estado for e, _ in TRANSICIONES)

    def test_el_comprador_no_puede_aprobar(self) -> None:
        with pytest.raises(NoAutorizado):
            _pedido().aplicar(Accion.APROBAR, Actor.COMPRADOR, AHORA)

    def test_aprobar_despues_de_30_minutos(self) -> None:
        with pytest.raises(Conflicto) as error:
            _pedido().aplicar(Accion.APROBAR, Actor.VENDEDOR, AHORA + timedelta(minutes=30))
        assert error.value.tipo == "pedido_vencido"

    def test_no_asistio_exige_esperar(self) -> None:
        llegada = AHORA
        p = _pedido(Estado.EN_PUNTO, llegada_en=llegada)
        with pytest.raises(ReglaIncumplida):
            p.aplicar(Accion.NO_ASISTIO, Actor.VENDEDOR, llegada + timedelta(minutes=9))
        despues, t = p.aplicar(Accion.NO_ASISTIO, Actor.VENDEDOR, llegada + timedelta(minutes=10))
        assert despues.estado is Estado.NO_ASISTIO
        assert t.libera_stock

    def test_llegue_registra_la_hora(self) -> None:
        despues, _ = _pedido(Estado.APROBADO).aplicar(Accion.LLEGUE, Actor.VENDEDOR, AHORA)
        assert despues.llegada_en == AHORA

    def test_acciones_posibles_por_actor(self) -> None:
        assert set(acciones_posibles(Estado.PENDIENTE, Actor.VENDEDOR)) == {
            Accion.APROBAR,
            Accion.RECHAZAR,
        }
        assert acciones_posibles(Estado.PENDIENTE, Actor.COMPRADOR) == [Accion.CANCELAR]
        assert acciones_posibles(Estado.ENTREGADO, Actor.VENDEDOR) == []


# -- reglas: cada una con un caso que la dispara y otro sin falso positivo ------

PROD = uuid4()


def _contexto(**cambios: object) -> ContextoPedido:
    base: dict[str, object] = {
        "tienda_id": uuid4(),
        "vendedor_id": VENDEDOR,
        "campus_id": "c",
        "fecha": date(2026, 11, 3),
        "franja_id": "f-1200",
        "franja_fin": AHORA + timedelta(hours=1),
        "punto_id": "b19",
        "ofertas": {PROD: OfertaEnTurno(PROD, "Pollo", 3000, True, 5)},
        "pedidos_abiertos_del_comprador": 0,
        "inasistencias_del_comprador": 0,
        "ahora": AHORA,
        "zona": ZoneInfo("America/Bogota"),
        "limites": Limites(),
    }
    return ContextoPedido(**{**base, **cambios})  # type: ignore[arg-type]


def _solicitud(
    producto: UUID = PROD, cantidad: int = 2, comprador: UUID = COMPRADOR
) -> SolicitudPedido:
    return SolicitudPedido(comprador, uuid4(), (LineaSolicitada(producto, cantidad),))


VALIDADOR = Validador(reglas_pedido("pedido-v1"))

CASOS_QUE_DISPARAN = [
    ("producto_del_turno", _solicitud(producto=uuid4()), _contexto()),
    (
        "producto_del_turno",
        _solicitud(),
        _contexto(ofertas={PROD: OfertaEnTurno(PROD, "Pollo", 3000, False, 5)}),
    ),
    ("turno_vencido", _solicitud(), _contexto(franja_fin=AHORA)),
    ("cantidad_invalida", _solicitud(cantidad=0), _contexto()),
    ("cantidad_invalida", _solicitud(cantidad=21), _contexto()),
    ("pedido_a_si_mismo", _solicitud(comprador=VENDEDOR), _contexto()),
    ("demasiados_pedidos_abiertos", _solicitud(), _contexto(pedidos_abiertos_del_comprador=2)),
    ("comprador_bloqueado", _solicitud(), _contexto(inasistencias_del_comprador=3)),
]


@pytest.mark.parametrize(("regla", "solicitud", "contexto"), CASOS_QUE_DISPARAN)
def test_la_regla_se_dispara(
    regla: str, solicitud: SolicitudPedido, contexto: ContextoPedido
) -> None:
    assert [h.regla_id for h in VALIDADOR.validar(solicitud, contexto)] == [regla]


@pytest.mark.parametrize(
    ("descripcion", "solicitud", "contexto"),
    [
        ("pedido normal", _solicitud(), _contexto()),
        ("cantidad en el limite", _solicitud(cantidad=20), _contexto()),
        (
            "un pedido abierto todavia deja pedir",
            _solicitud(),
            _contexto(pedidos_abiertos_del_comprador=1),
        ),
        (
            "dos inasistencias todavia dejan pedir",
            _solicitud(),
            _contexto(inasistencias_del_comprador=2),
        ),
        (
            "un minuto antes de que acabe la franja",
            _solicitud(),
            _contexto(franja_fin=AHORA + timedelta(minutes=1)),
        ),
    ],
)
def test_sin_falsos_positivos(
    descripcion: str, solicitud: SolicitudPedido, contexto: ContextoPedido
) -> None:
    assert VALIDADOR.validar(solicitud, contexto) == [], descripcion


def test_conjunto_inexistente() -> None:
    with pytest.raises(KeyError, match="pedido-v1"):
        reglas_pedido("pedido-v9")
