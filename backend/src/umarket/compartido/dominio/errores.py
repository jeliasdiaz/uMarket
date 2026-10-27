"""Errores del dominio.

Responsabilidad: dar a cada fallo de negocio un `tipo` estable que viaje hasta el
frontend sin cambiar de significado.

Lo que NO le corresponde: saber de HTTP. La traduccion de cada familia de error
a un codigo de estado vive en un solo lugar, `umarket/http/errores.py`.
"""


class ErrorDominio(Exception):
    """Base de todos los errores de negocio.

    `tipo` es un identificador estable (`sin_stock`, `pedido_vencido`): el
    frontend decide que mostrar a partir de el, asi que cambiarlo es un cambio
    de contrato. `mensaje` es para personas y puede mejorar de redaccion.
    """

    def __init__(self, tipo: str, mensaje: str, **detalles: object) -> None:
        super().__init__(mensaje)
        self.tipo = tipo
        self.mensaje = mensaje
        self.detalles = detalles


class NoEncontrado(ErrorDominio):
    """Lo que se busca no existe, o no es visible para quien lo pide."""


class NoAutenticado(ErrorDominio):
    """Hace falta una sesion valida."""


class NoAutorizado(ErrorDominio):
    """Hay sesion, pero esa persona no puede hacer esto."""


class ReglaIncumplida(ErrorDominio):
    """Una regla de negocio bloqueo la operacion."""


class Conflicto(ErrorDominio):
    """El estado cambio entre que se leyo y se quiso escribir (stock, transiciones)."""


class LimiteExcedido(ErrorDominio):
    """Demasiados intentos o peticiones en poco tiempo."""
