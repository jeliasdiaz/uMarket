"""El despachador del outbox (PLAN-TECNICO.md §2.6).

Lee los eventos pendientes de `eventos_salida` con SKIP LOCKED (dos workers no
toman el mismo), los entrega a los manejadores registrados para su tipo y los
marca procesados. Si un manejador falla, el evento se reintenta en la siguiente
vuelta hasta `max_intentos`; despues queda marcado con su ultimo error para que
una persona lo mire.

La entrega es "al menos una vez": los manejadores deben ser idempotentes. Las
metricas lo son porque se recalculan; un aviso push repetido es aceptable.
"""

import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from umarket.bd.plataforma import eventos_salida
from umarket.compartido.dominio.eventos import Evento
from umarket.compartido.dominio.reloj import Reloj

log = logging.getLogger("umarket.worker")

type Manejador = Callable[[Evento], None]


@dataclass(frozen=True)
class ResultadoDespacho:
    procesados: int
    fallidos: int


class DespachadorEventos:
    def __init__(
        self,
        fabrica: sessionmaker[Session],
        manejadores: Mapping[str, Sequence[Manejador]],
        reloj: Reloj,
        max_intentos: int = 5,
    ) -> None:
        self._fabrica = fabrica
        self._manejadores = manejadores
        self._reloj = reloj
        self._max_intentos = max_intentos

    def procesar(self, lote: int = 50) -> ResultadoDespacho:
        procesados = fallidos = 0
        with self._fabrica() as s, s.begin():
            filas = list(
                s.execute(
                    select(eventos_salida)
                    .where(
                        eventos_salida.c.procesado_en.is_(None),
                        eventos_salida.c.intentos < self._max_intentos,
                    )
                    .order_by(eventos_salida.c.creado_en)
                    .limit(lote)
                    .with_for_update(skip_locked=True)
                ).mappings()
            )
            for fila in filas:
                evento = Evento(fila["tipo"], fila["datos"], fila["ocurrido_en"])
                try:
                    for manejador in self._manejadores.get(evento.tipo, ()):
                        manejador(evento)
                except Exception as exc:
                    fallidos += 1
                    intentos = fila["intentos"] + 1
                    log.exception("Fallo el manejo de %s (intento %s)", evento.tipo, intentos)
                    s.execute(
                        update(eventos_salida)
                        .where(eventos_salida.c.id == fila["id"])
                        .values(
                            intentos=intentos,
                            ultimo_error=f"{type(exc).__name__}: {exc}"[:500],
                            procesado_en=(
                                self._reloj.ahora() if intentos >= self._max_intentos else None
                            ),
                        )
                    )
                    continue
                procesados += 1
                s.execute(
                    update(eventos_salida)
                    .where(eventos_salida.c.id == fila["id"])
                    .values(procesado_en=self._reloj.ahora())
                )
        return ResultadoDespacho(procesados, fallidos)
