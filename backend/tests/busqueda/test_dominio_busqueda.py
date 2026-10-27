"""Busqueda sin base de datos: parsers, interprete por palabras, reglas, correccion, filtros."""

import json

import pytest
from hypothesis import given
from hypothesis import strategies as st

from umarket.busqueda.dominio.contrato import (
    ConsultaInterpretada,
    EntradaInterprete,
    FranjaContexto,
    ItemBuscado,
    Menciones,
    PuntoContexto,
    Vocabulario,
)
from umarket.busqueda.dominio.correccion import PoliticaCorreccionConsulta
from umarket.busqueda.dominio.filtros import describir, quitar
from umarket.busqueda.dominio.palabras import interpretar_por_palabras
from umarket.busqueda.dominio.parseo import (
    Relacion,
    parsear_cantidades,
    parsear_hora,
    parsear_montos,
)
from umarket.busqueda.dominio.privacidad import redactar
from umarket.busqueda.dominio.reglas import ContextoConsulta, reglas_consulta
from umarket.catalogo import Categoria, Etiqueta
from umarket.compartido.dominio.reglas import Validador
from umarket.ia.adaptadores.gemini import esquema_para_gemini


class TestParsers:
    @pytest.mark.parametrize(
        ("texto", "valor", "relacion"),
        [
            ("menos de 5 mil", 5000, Relacion.MAXIMO),
            ("5k", 5000, Relacion.MAXIMO),
            ("hasta $4.500", 4500, Relacion.MAXIMO),
            ("cinco mil pesos", 5000, Relacion.MAXIMO),
            ("un almuerzo de 12.000", 12000, Relacion.MAXIMO),
            ("tengo 10 mil", 10000, Relacion.PRESUPUESTO),
        ],
    )
    def test_montos(self, texto: str, valor: int, relacion: Relacion) -> None:
        (monto,) = parsear_montos(texto)
        assert (monto.valor, monto.relacion) == (valor, relacion)

    @pytest.mark.parametrize("texto", ["a las 12", "2 empanadas", "precio 0", "dos de pollo"])
    def test_numeros_que_no_son_plata(self, texto: str) -> None:
        assert parsear_montos(texto) == []

    @pytest.mark.parametrize(
        ("texto", "hora"),
        [
            ("pa las 12", 12),
            ("a las 4", 16),
            ("a las 4 de la tarde", 16),
            ("12:30", 12),
            ("pa ya", None),
        ],
    )
    def test_horas(self, texto: str, hora: int | None) -> None:
        mencion = parsear_hora(texto)
        assert mencion is not None and mencion.hora == hora

    def test_cantidades(self) -> None:
        assert [(n, cosa) for n, cosa, _ in parsear_cantidades("2 de pollo y una de queso")] == [
            (2, "pollo"),
            (1, "queso"),
        ]
        assert [(n, c) for n, c, _ in parsear_cantidades("media docena de bunuelos")] == [
            (6, "bunuelos")
        ]

    @given(st.text(max_size=200))
    def test_los_parsers_nunca_revientan(self, texto: str) -> None:
        parsear_montos(texto)
        parsear_hora(texto)
        parsear_cantidades(texto)


def test_privacidad_quita_correos_y_telefonos_pero_no_precios() -> None:
    texto = "escribeme a ana@demo.edu.co o al 300 123 4567, algo de 12.000"
    assert redactar(texto) == "escribeme a [dato] o al [dato], algo de 12.000"


def _entrada(texto: str) -> EntradaInterprete:
    return EntradaInterprete(
        texto=texto,
        ahora="2026-11-03T11:20-05:00",
        vocabulario=Vocabulario(categorias=[], etiquetas=[], productos_hoy=[]),
        puntos=[
            PuntoContexto(id="b19-entrada", nombre="Bloque 19 - entrada", alias=["el 19"]),
            PuntoContexto(id="b19-cafeteria", nombre="Bloque 19 - cafeteria", alias=["el 19"]),
            PuntoContexto(id="biblioteca", nombre="Biblioteca", alias=["la biblio"]),
        ],
        franjas_abiertas=[
            FranjaContexto(id="f-1200", inicio="12:00", fin="12:30"),
            FranjaContexto(id="f-1600", inicio="16:00", fin="16:30"),
        ],
    )


class TestInterpretePorPalabras:
    def test_varios_items_con_cantidad_y_franja(self) -> None:
        q = interpretar_por_palabras(_entrada("2 empanadas y un jugo pa las 12"))
        assert [(i.termino, i.cantidad) for i in q.items] == [("empanada", 2), ("jugo", 1)]
        assert q.items[0].categoria is Categoria.EMPANADAS
        assert q.franja_id == "f-1200"

    def test_punto_ambiguo_se_declara(self) -> None:
        q = interpretar_por_palabras(_entrada("algo en el 19"))
        assert q.punto_id is None
        assert q.punto_candidatos == ["b19-entrada", "b19-cafeteria"]

    def test_pa_ya_es_la_primera_franja_abierta(self) -> None:
        assert interpretar_por_palabras(_entrada("empanada pa ya")).franja_id == "f-1200"

    def test_etiqueta_del_vocabulario(self) -> None:
        q = interpretar_por_palabras(_entrada("algo dulce por menos de 5 mil"))
        assert q.items[0].etiquetas == [Etiqueta.DULCE]
        assert q.precio_max_unitario_cop == 5000

    def test_sus_menciones_pasan_su_propia_verificacion(self) -> None:
        """El baseline tambien se valida con consulta-v1: no puede hacer trampa."""
        for texto in ["tengo 10 mil pa almorzar", "2 de pollo y una de queso pa las 12 por el 19"]:
            entrada = _entrada(texto)
            q = interpretar_por_palabras(entrada)
            assert _validador().validar(q, _ctx(entrada)) == []


def _validador() -> Validador[ConsultaInterpretada, ContextoConsulta]:
    return Validador(reglas_consulta("consulta-v1"))


def _ctx(entrada: EntradaInterprete) -> ContextoConsulta:
    return ContextoConsulta(
        entrada.texto,
        frozenset(p.id for p in entrada.puntos),
        frozenset(f.id for f in entrada.franjas_abiertas),
    )


TEXTO = "algo dulce por menos de 5 mil pa las 12 en el 19"
CTX = _ctx(_entrada(TEXTO))
BUENA = ConsultaInterpretada(
    es_busqueda=True,
    items=[ItemBuscado(etiquetas=[Etiqueta.DULCE], mencion="algo dulce")],
    precio_max_unitario_cop=5000,
    franja_id="f-1200",
    punto_candidatos=["b19-entrada", "b19-cafeteria"],
    menciones=Menciones(precio="menos de 5 mil", franja="pa las 12", punto="el 19"),
)


@pytest.mark.parametrize(
    ("regla", "cambios"),
    [
        ("mencion_no_literal", {"items": [ItemBuscado(termino="x", mencion="algo salado")]}),
        ("monto_sin_respaldo", {"precio_max_unitario_cop": 4000}),
        ("monto_implausible", {"precio_max_unitario_cop": 0, "menciones": Menciones()}),
        ("punto_desconocido", {"punto_id": "la-luna"}),
        ("franja_cerrada", {"franja_id": "f-0700"}),
        (
            "cantidad_irrazonable",
            {"items": [ItemBuscado(termino="x", cantidad=99, mencion="dulce")]},
        ),
        (
            "consulta_inutilizable",
            {
                "items": [],
                "precio_max_unitario_cop": None,
                "franja_id": None,
                "punto_candidatos": [],
                "menciones": Menciones(),
            },
        ),
    ],
)
def test_cada_regla_se_dispara(regla: str, cambios: dict[str, object]) -> None:
    q = BUENA.model_copy(update=cambios)
    assert regla in {h.regla_id for h in _validador().validar(q, CTX)}


def test_la_consulta_buena_no_da_falsos_positivos() -> None:
    assert _validador().validar(BUENA, CTX) == []


def test_filtros_v1_no_exige_respaldo_literal() -> None:
    """Un filtro que el comprador puso a mano no tiene texto que lo respalde."""
    editada = BUENA.model_copy(update={"precio_max_unitario_cop": 8000})
    assert Validador(reglas_consulta("filtros-v1")).validar(editada, CTX) == []


class TestCorreccion:
    def test_anula_el_filtro_sin_respaldo_y_conserva_el_resto(self) -> None:
        q = BUENA.model_copy(update={"precio_max_unitario_cop": 4000})
        hallazgos = _validador().validar(q, CTX)
        c = PoliticaCorreccionConsulta().corregir(q, hallazgos, CTX)
        assert c.consulta.precio_max_unitario_cop is None
        assert c.consulta.franja_id == "f-1200"
        assert c.anulados == ("precio_max_unitario_cop",)
        assert not c.usar_respaldo

    def test_quita_el_item_inventado(self) -> None:
        q = BUENA.model_copy(
            update={"items": [*BUENA.items, ItemBuscado(termino="pizza", mencion="pizza")]}
        )
        c = PoliticaCorreccionConsulta().corregir(q, _validador().validar(q, CTX), CTX)
        assert [i.mencion for i in c.consulta.items] == ["algo dulce"]

    def test_consulta_inutil_pide_respaldo(self) -> None:
        vacia = ConsultaInterpretada(es_busqueda=True)
        c = PoliticaCorreccionConsulta().corregir(vacia, _validador().validar(vacia, CTX), CTX)
        assert c.usar_respaldo


def test_describir_y_quitar_filtros() -> None:
    filtros = describir(BUENA, {}, {"f-1200": "12:00–12:30"})
    assert [f.etiqueta for f in filtros] == ["dulce", "hasta $5.000", "12:00–12:30"]
    sin_precio = quitar(BUENA, "precio_max_unitario_cop")
    assert sin_precio.precio_max_unitario_cop is None
    assert quitar(BUENA, "items.0").items == []


def test_el_contrato_no_tiene_campos_para_manipular_precios_ni_tiendas() -> None:
    """La garantia estructural contra la inyeccion (PLAN-TECNICO.md §6.2)."""
    campos = json.dumps(ConsultaInterpretada.model_json_schema())
    for prohibido in ("tienda", "precio_venta", "stock", "vendedor", "posicion"):
        assert prohibido not in campos
    with pytest.raises(ValueError):
        ConsultaInterpretada.model_validate({"es_busqueda": True, "tienda_primero": "juan"})


def test_el_esquema_para_gemini_no_lleva_additional_properties() -> None:
    assert "additionalProperties" not in json.dumps(esquema_para_gemini(ConsultaInterpretada))
