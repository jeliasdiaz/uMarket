"""La unidad de trabajo SQL: una sesion, una transaccion.

Cada modulo la extiende con sus repositorios en `_al_abrir`. Todos comparten la
misma sesion, asi que lo que se escribe dentro del `with` se confirma o se
revierte junto: crear el pedido, reservar el stock y dejar el evento en el
outbox es una sola transaccion.
"""

from types import TracebackType
from typing import Self

from sqlalchemy.orm import Session, sessionmaker

from umarket.bd.plataforma import BuzonEventosSql


class UnidadSql:
    def __init__(self, fabrica: sessionmaker[Session]) -> None:
        self._fabrica = fabrica
        self._sesion: Session | None = None

    @property
    def sesion(self) -> Session:
        if self._sesion is None:
            raise RuntimeError("La unidad de trabajo se usa dentro de un `with`.")
        return self._sesion

    def __enter__(self) -> Self:
        self._sesion = self._fabrica()
        self.eventos = BuzonEventosSql(self._sesion)
        self._al_abrir(self._sesion)
        return self

    def _al_abrir(self, sesion: Session) -> None:
        """Los modulos construyen aqui sus repositorios sobre `sesion`."""

    def __exit__(
        self,
        tipo: type[BaseException] | None,
        valor: BaseException | None,
        traza: TracebackType | None,
    ) -> None:
        sesion = self.sesion
        try:
            sesion.rollback()  # no-op si ya se confirmo
        finally:
            sesion.close()
            self._sesion = None

    def confirmar(self) -> None:
        self.sesion.commit()
