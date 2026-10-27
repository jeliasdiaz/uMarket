"""Que aviso recibe quien, ante cada evento.

Las plantillas son un registro por tipo de evento: un aviso nuevo es una entrada
nueva (punto de extension "reaccion a un evento", PLAN-TECNICO.md §3). El canal
(push, correo, WhatsApp el dia que exista) es otra cosa: un adaptador.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from uuid import UUID

from umarket.compartido.dominio.eventos import Evento, Json


@dataclass(frozen=True)
class Aviso:
    usuario_id: UUID
    titulo: str
    cuerpo: str
    url: str


def _pesos(valor: Json) -> str:
    return f"${int(valor):,}".replace(",", ".") if isinstance(valor, int) else ""


def _uuid(d: Mapping[str, Json], clave: str) -> UUID:
    return UUID(str(d[clave]))


def _al_comprador(titulo: str, cuerpo: str) -> Callable[[Mapping[str, Json]], list[Aviso]]:
    def plantilla(d: Mapping[str, Json]) -> list[Aviso]:
        return [
            Aviso(
                _uuid(d, "comprador_id"),
                titulo.format(**d),
                cuerpo.format(**d),
                f"/pedido/{d['pedido_id']}",
            )
        ]

    return plantilla


def _creado(d: Mapping[str, Json]) -> list[Aviso]:
    return [
        Aviso(
            _uuid(d, "vendedor_id"),
            f"Nuevo pedido {d['codigo']}",
            f"Total {_pesos(d['total_cop'])}. Apruebalo antes de 30 minutos.",
            "/vendedor",
        )
    ]


def _cancelado(d: Mapping[str, Json]) -> list[Aviso]:
    """Se avisa a la otra parte: quien cancelo ya lo sabe."""
    destino = "vendedor_id" if d.get("actor") == "comprador" else "comprador_id"
    url = "/vendedor" if destino == "vendedor_id" else f"/pedido/{d['pedido_id']}"
    return [
        Aviso(_uuid(d, destino), f"Pedido {d['codigo']} cancelado", str(d.get("motivo") or ""), url)
    ]


PLANTILLAS: dict[str, Callable[[Mapping[str, Json]], list[Aviso]]] = {
    "pedido.creado": _creado,
    "pedido.aprobado": _al_comprador(
        "Pedido {codigo} aprobado", "Te esperan en el punto, en tu franja."
    ),
    "pedido.rechazado": _al_comprador("Pedido {codigo} rechazado", "El vendedor no pudo tomarlo."),
    "pedido.vencido": _al_comprador(
        "El vendedor no respondio a tiempo", "Tu pedido {codigo} se cancelo solo."
    ),
    "pedido.cancelado": _cancelado,
    "pedido.vendedor_llego": _al_comprador(
        "Tu vendedor llego", "Ve al punto y di tu codigo: {codigo}."
    ),
    "pedido.entregado": _al_comprador("¿Que tal tu pedido?", "Califica la tienda: ayuda a otros."),
}


def avisos_de(evento: Evento) -> list[Aviso]:
    plantilla = PLANTILLAS.get(evento.tipo)
    return [] if plantilla is None else plantilla(evento.datos)
