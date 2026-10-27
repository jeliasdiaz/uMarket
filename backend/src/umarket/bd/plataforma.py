"""Tablas de plataforma: el outbox de eventos y las trazas de IA.

`eventos_salida` es el outbox (PLAN-TECNICO.md §2.6): un caso de uso deja aqui
sus eventos en la misma transaccion que el cambio que los causa, y el worker los
despacha. Si la transaccion se revierte, el evento tambien: nunca se avisa de un
pedido que no existe.
"""

import json
from typing import Any
from uuid import uuid4

from sqlalchemy import Column, DateTime, Index, Integer, Numeric, Table, Text, func, insert, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Session

from umarket.bd.metadatos import metadatos
from umarket.compartido.dominio.eventos import Evento

eventos_salida = Table(
    "eventos_salida",
    metadatos,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("tipo", Text, nullable=False),
    Column("datos", JSONB, nullable=False),
    Column("ocurrido_en", DateTime(timezone=True), nullable=False),
    Column("creado_en", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("procesado_en", DateTime(timezone=True)),
    Column("intentos", Integer, nullable=False, server_default="0"),
    Column("ultimo_error", Text),
    Index(
        "ix_eventos_salida_pendientes",
        "creado_en",
        postgresql_where=text("procesado_en IS NULL"),
    ),
)

trazas_ia = Table(
    "trazas_ia",
    metadatos,
    Column("run_id", Text, primary_key=True),
    Column("componente", Text, nullable=False),
    Column("modelo", Text, nullable=False, server_default=""),
    Column("proveedor", Text, nullable=False, server_default=""),
    Column("prompt_version", Text, nullable=False, server_default=""),
    Column("tokens_total", Integer, nullable=False, server_default="0"),
    Column("costo_usd", Numeric(12, 6)),
    Column("duracion_s", Numeric(10, 4), nullable=False, server_default="0"),
    Column("traza", JSONB, nullable=False),
    Column("creado_en", DateTime(timezone=True), nullable=False, server_default=func.now()),
)


class BuzonEventosSql:
    """Implementa `BuzonEventos` sobre la sesion de la unidad de trabajo."""

    def __init__(self, sesion: Session) -> None:
        self._sesion = sesion

    def publicar(self, evento: Evento) -> None:
        self._sesion.execute(
            insert(eventos_salida).values(
                id=uuid4(),
                tipo=evento.tipo,
                datos=json.loads(json.dumps(evento.datos, default=str)),
                ocurrido_en=evento.ocurrido_en,
            )
        )


def guardar_traza(sesion: Session, traza: dict[str, Any], duracion_s: float) -> None:
    tokens = traza.get("tokens", {})
    sesion.execute(
        insert(trazas_ia).values(
            run_id=traza["run_id"],
            componente=traza["componente"],
            modelo=traza.get("modelo", ""),
            proveedor=traza.get("proveedor", ""),
            prompt_version=traza.get("prompt_version", ""),
            tokens_total=sum(int(v) for v in tokens.values()),
            costo_usd=traza.get("costo_usd"),
            duracion_s=duracion_s,
            traza=traza,
        )
    )
