"""API publica del modulo busqueda."""

from umarket.busqueda.aplicacion.casos import (
    Buscar,
    ConfigBusqueda,
    RefinarBusqueda,
    RegistrarClic,
)
from umarket.busqueda.aplicacion.interpretes import InterpreteConRespaldo, InterpretePorPalabras
from umarket.busqueda.aplicacion.vistas import ResultadoBusqueda, TiendaEncontrada
from umarket.busqueda.dominio.contrato import (
    SCHEMA_VERSION,
    ConsultaInterpretada,
    EntradaInterprete,
)
from umarket.busqueda.dominio.reglas import reglas_consulta
from umarket.busqueda.puertos import InterpreteConsulta

__all__ = [
    "SCHEMA_VERSION",
    "Buscar",
    "ConfigBusqueda",
    "ConsultaInterpretada",
    "EntradaInterprete",
    "InterpreteConRespaldo",
    "InterpreteConsulta",
    "InterpretePorPalabras",
    "RefinarBusqueda",
    "RegistrarClic",
    "ResultadoBusqueda",
    "TiendaEncontrada",
    "reglas_consulta",
]
