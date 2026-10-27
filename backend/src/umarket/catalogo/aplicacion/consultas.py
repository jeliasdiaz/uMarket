"""Consultas publicas del catalogo (lo que ve el comprador)."""

from uuid import UUID
from zoneinfo import ZoneInfo

from umarket.catalogo.aplicacion.vistas import ResumenTienda, VistaTienda
from umarket.catalogo.puertos import ConsultasCatalogo
from umarket.compartido.dominio.errores import NoEncontrado
from umarket.compartido.dominio.reloj import Reloj


class ListarTiendas:
    def __init__(self, consultas: ConsultasCatalogo, reloj: Reloj, zona_horaria: str) -> None:
        self._consultas = consultas
        self._reloj = reloj
        self._zona = ZoneInfo(zona_horaria)

    def ejecutar(self, campus_id: str) -> list[ResumenTienda]:
        ahora = self._reloj.ahora()
        resumenes = self._consultas.listar_tiendas(
            campus_id, ahora.astimezone(self._zona).date(), ahora
        )
        return sorted(resumenes, key=lambda r: (*r.reputacion.orden, r.nombre))


class VerTienda:
    def __init__(self, consultas: ConsultasCatalogo, reloj: Reloj, zona_horaria: str) -> None:
        self._consultas = consultas
        self._reloj = reloj
        self._zona = ZoneInfo(zona_horaria)

    def ejecutar(self, slug: str) -> VistaTienda:
        ahora = self._reloj.ahora()
        vista = self._consultas.ver_tienda(slug, ahora.astimezone(self._zona).date(), ahora)
        if vista is None:
            raise NoEncontrado("tienda_no_encontrada", "Esa tienda no existe o esta cerrada.")
        return vista


class TiendaDeUsuario:
    def __init__(self, consultas: ConsultasCatalogo) -> None:
        self._consultas = consultas

    def ejecutar(self, usuario_id: UUID) -> str | None:
        return self._consultas.slug_de_vendedor(usuario_id)
