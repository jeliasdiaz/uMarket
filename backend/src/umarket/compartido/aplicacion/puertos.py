"""Puertos que comparten todos los casos de uso.

`UnidadDeTrabajo`: una transaccion. Cada modulo define la suya extendiendo este
protocolo con los repositorios que necesita (ISP): `pedidos` pide pedidos,
stock y buzon; `catalogo` pide tiendas y productos. El adaptador SQL de cada uno
comparte una sola sesion, asi que todo lo que se escribe dentro del `with` se
confirma o se revierte junto.

`BuzonEventos`: donde un caso de uso deja sus eventos. En SQL es la tabla
`eventos_salida` (outbox), en la misma transaccion que el cambio que los causa.
"""

from types import TracebackType
from typing import Protocol, Self

from umarket.compartido.dominio.eventos import Evento


class UnidadDeTrabajo(Protocol):
    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        tipo: type[BaseException] | None,
        valor: BaseException | None,
        traza: TracebackType | None,
    ) -> None:
        """Revierte todo lo que no se haya confirmado."""
        ...

    def confirmar(self) -> None: ...


class BuzonEventos(Protocol):
    def publicar(self, evento: Evento) -> None: ...
