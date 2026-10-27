"""Los contratos versionados no pueden divergir del codigo."""

import json

from scripts.exportar_contratos import CONTRATOS, generar, serializar
from umarket.busqueda.dominio.contrato import ConsultaInterpretada
from umarket.busqueda.dominio.reglas import reglas_consulta


def test_los_contratos_generados_estan_al_dia() -> None:
    """Falla si alguien cambia un modelo o una ruta sin regenerar `contratos/` (golden)."""
    for nombre, contenido in generar().items():
        actual = (CONTRATOS / nombre).read_text("utf-8")
        assert actual == serializar(contenido), (
            f"{nombre} desactualizado: corre scripts/exportar_contratos.py"
        )


def test_el_contrato_de_producto_declara_los_mismos_campos_que_el_modelo() -> None:
    producto = json.loads((CONTRATOS / "busqueda" / "producto.json").read_text("utf-8"))
    assert set(producto["output_fields"]) == set(ConsultaInterpretada.model_fields)


def test_cada_validacion_declarada_es_una_regla_registrada() -> None:
    producto = json.loads((CONTRATOS / "busqueda" / "producto.json").read_text("utf-8"))
    registradas = {r.id for r in reglas_consulta("consulta-v1")}
    assert set(producto["system_validations"]) == registradas
