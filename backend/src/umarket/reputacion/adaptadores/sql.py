from datetime import datetime
from uuid import UUID

from sqlalchemy import insert, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from umarket.bd.uow import UnidadSql
from umarket.catalogo import Reputacion
from umarket.reputacion.adaptadores.tablas import calificaciones, metricas_tienda
from umarket.reputacion.dominio.modelos import Calificacion, Metricas, PoliticaRanking
from umarket.reputacion.puertos import PedidoCalificable, ResenaVista


class RepositorioReputacionSql:
    def __init__(self, sesion: Session) -> None:
        self._s = sesion

    def pedido(self, pedido_id: UUID) -> PedidoCalificable | None:
        fila = (
            self._s.execute(
                text("select id, tienda_id, comprador_id, estado from pedidos where id = :id"),
                {"id": pedido_id},
            )
            .mappings()
            .first()
        )
        if fila is None:
            return None
        return PedidoCalificable(
            fila["id"], fila["tienda_id"], fila["comprador_id"], fila["estado"]
        )

    def ya_calificado(self, pedido_id: UUID) -> bool:
        consulta = select(calificaciones.c.id).where(calificaciones.c.pedido_id == pedido_id)
        return self._s.execute(consulta).first() is not None

    def agregar(self, calificacion: Calificacion) -> None:
        self._s.execute(
            insert(calificaciones).values(
                id=calificacion.id,
                pedido_id=calificacion.pedido_id,
                tienda_id=calificacion.tienda_id,
                comprador_id=calificacion.comprador_id,
                estrellas=calificacion.estrellas,
                comentario=calificacion.comentario,
                creada_en=calificacion.creada_en,
            )
        )

    def contar(self, tienda_id: UUID) -> Metricas:
        fila = (
            self._s.execute(
                text(
                    """
                    select
                      (select count(*) from calificaciones where tienda_id = :t) as resenas,
                      (select coalesce(sum(estrellas), 0) from calificaciones
                        where tienda_id = :t) as suma_estrellas,
                      (select count(*) from pedidos
                        where tienda_id = :t and estado = 'entregado') as entregas,
                      (select count(*) from pedidos
                        where tienda_id = :t and estado = 'vencido') as vencidos,
                      (select count(*) from transiciones_pedido tp
                         join pedidos p on p.id = tp.pedido_id
                        where p.tienda_id = :t and tp.accion = 'cancelar'
                          and tp.actor = 'vendedor') as cancelados_por_vendedor
                    """
                ),
                {"t": tienda_id},
            )
            .mappings()
            .one()
        )
        return Metricas(**dict(fila))

    def guardar_metricas(self, tienda_id: UUID, metricas: Metricas, en: datetime) -> None:
        valores = {**metricas.__dict__, "actualizado_en": en}
        self._s.execute(
            pg_insert(metricas_tienda)
            .values(tienda_id=tienda_id, **valores)
            .on_conflict_do_update(index_elements=["tienda_id"], set_=valores)
        )

    def resenas_por_slug(self, slug: str, limite: int) -> list[ResenaVista]:
        filas = self._s.execute(
            text(
                """
                select ca.estrellas, ca.comentario, ca.creada_en
                from calificaciones ca join tiendas t on t.id = ca.tienda_id
                where t.slug = :slug order by ca.creada_en desc limit :limite
                """
            ),
            {"slug": slug, "limite": limite},
        ).mappings()
        return [ResenaVista(f["estrellas"], f["comentario"], f["creada_en"]) for f in filas]


class UnidadReputacionSql(UnidadSql):
    def _al_abrir(self, sesion: Session) -> None:
        self.reputacion = RepositorioReputacionSql(sesion)


class FuenteReputacionSql:
    """Implementa `FuenteReputacion` del catalogo con la politica de ranking vigente."""

    def __init__(self, politica: PoliticaRanking) -> None:
        self._politica = politica

    def de_tienda(self, sesion: Session, tienda_id: UUID) -> Reputacion:
        fila = (
            sesion.execute(select(metricas_tienda).where(metricas_tienda.c.tienda_id == tienda_id))
            .mappings()
            .first()
        )
        m = (
            Metricas()
            if fila is None
            else Metricas(
                resenas=fila["resenas"],
                suma_estrellas=fila["suma_estrellas"],
                entregas=fila["entregas"],
                vencidos=fila["vencidos"],
                cancelados_por_vendedor=fila["cancelados_por_vendedor"],
            )
        )
        return Reputacion(
            promedio=m.promedio,
            resenas=m.resenas,
            entregas=m.entregas,
            porcentaje_cumplido=m.porcentaje_cumplido,
            rankeable=self._politica.rankeable(m),
            orden=self._politica.clave(m),
        )
