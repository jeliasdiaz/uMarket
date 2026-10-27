"""Lo que nunca sale hacia el modelo ni se guarda en el registro de busquedas.

Ley 1581 (PLAN-TECNICO.md §13): antes de enviar el texto al proveedor de LLM y de
guardarlo como dato de evals, se reemplazan correos y telefonos. Un precio
("5.000", "12000") no es un telefono: se exigen 7 digitos o mas seguidos.
"""

import re

_CORREO = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_TELEFONO = re.compile(r"(?<!\d)(?:\+?57[\s-]?)?(?:\d[\s-]?){7,}\d(?!\d)")


def redactar(texto: str) -> str:
    return _TELEFONO.sub("[dato]", _CORREO.sub("[dato]", texto))
