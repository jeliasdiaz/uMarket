"""El lado SQL de la busqueda: contexto del campus, ofertas y registro.

Solo devuelve ofertas REALES: productos activos, con stock disponible, en turnos
de hoy cuya franja no ha pasado. El modelo nunca toca esta consulta: solo aporta
filtros que el codigo ya verifico.
"""

from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import insert, select, text
from sqlalchemy.orm import Session, sessionmaker

from umarket.bd.plataforma import guardar_traza
from umarket.busqueda.adaptadores.tablas import busqueda_clics, busquedas
from umarket.busqueda.aplicacion.vistas import Oferta, RegistroBusqueda
from umarket.busqueda.dominio.contrato import ConsultaInterpretada, ItemBuscado
from umarket.busqueda.puertos import ContextoCampusBusqueda
from umarket.campus import Franja, PuntoEncuentro
from umarket.campus.adaptadores.tablas import campus, franjas, puntos_encuentro
from umarket.compartido.dominio.texto import normalizar
from umarket.ia.traza import Traza

UMBRAL_TRIGRAMAS = 0.5

_SQL_ABIERTA = "timezone(c.zona_horaria, tu.fecha + f.hora_fin) > :ahora"

_SQL_OFERTAS = f"""
select p.id as producto_id, p.nombre, p.categoria, p.etiquetas, p.precio_cop,
       s.total - s.reservado as disponible,
       tu.id as turno_id, tu.fecha, tu.franja_id, f.hora_inicio, f.hora_fin,
       tu.punto_id, pe.nombre as punto_nombre,
       ti.id as tienda_id, ti.slug as tienda_slug, ti.nombre as tienda_nombre,
       m.resenas, m.suma_estrellas,
       {{relevancia}} as relevancia
from stock_turno s
  join productos p on p.id = s.producto_id and p.activo
  join turnos tu on tu.id = s.turno_id
  join tiendas ti on ti.id = tu.tienda_id and ti.activa
  join campus c on c.id = ti.campus_id
  join franjas f on f.id = tu.franja_id
  join puntos_encuentro pe on pe.id = tu.punto_id
  left join metricas_tienda m on m.tienda_id = ti.id
where ti.campus_id = :campus and tu.fecha = :fecha and {_SQL_ABIERTA}
  and s.total - s.reservado >= :minimo
  {{filtros}}
order by relevancia desc, p.precio_cop
limit :limite
"""


def _condicion_item(item: ItemBuscado, params: dict[str, Any]) -> tuple[str, str]:
    """(condicion WHERE, expresion de relevancia) para un item buscado."""
    partes: list[str] = []
    relevancia: list[str] = []
    if item.termino:
        params["t"] = item.termino
        params["tn"] = normalizar(item.termino)
        partes.append(
            "(p.busqueda @@ plainto_tsquery('es_sin_tildes', :t) "
            f"or word_similarity(:tn, p.nombre_normalizado) >= {UMBRAL_TRIGRAMAS})"
        )
        relevancia.append(
            "coalesce(ts_rank(p.busqueda, plainto_tsquery('es_sin_tildes', :t)), 0) * 2"
            " + word_similarity(:tn, p.nombre_normalizado)"
        )
    if item.categoria:
        params["cat"] = item.categoria.value
        partes.append("p.categoria = :cat")
        relevancia.append("case when p.categoria = :cat then 0.5 else 0 end")
    condicion = " or ".join(partes)
    if item.etiquetas:
        params["etq"] = [e.value for e in item.etiquetas]
        etiquetas = "p.etiquetas && cast(:etq as text[])"
        # Con producto o categoria, las etiquetas restringen ("empanada vegetariana");
        # solas, son el criterio ("algo dulce").
        condicion = f"({condicion}) and {etiquetas}" if condicion else etiquetas
        relevancia.append(
            "0.3 * cardinality(array(select unnest(p.etiquetas) intersect "
            "select unnest(cast(:etq as text[]))))"
        )
    return condicion, " + ".join(relevancia) or "0"


def _oferta(f: Any, item: int | None) -> Oferta:
    resenas = f["resenas"] or 0
    return Oferta(
        producto_id=f["producto_id"],
        nombre=f["nombre"],
        categoria=f["categoria"],
        etiquetas=tuple(f["etiquetas"]),
        precio_cop=f["precio_cop"],
        disponible=f["disponible"],
        turno_id=f["turno_id"],
        fecha=f["fecha"],
        franja_id=f["franja_id"],
        franja_etiqueta=f"{f['hora_inicio']:%H:%M}–{f['hora_fin']:%H:%M}",
        punto_id=f["punto_id"],
        punto_nombre=f["punto_nombre"],
        tienda_id=f["tienda_id"],
        tienda_slug=f["tienda_slug"],
        tienda_nombre=f["tienda_nombre"],
        promedio=round(f["suma_estrellas"] / resenas, 2) if resenas else None,
        resenas=resenas,
        relevancia=float(f["relevancia"] or 0),
        item=item,
    )


class BuscadorOfertasSql:
    def __init__(self, fabrica: sessionmaker[Session]) -> None:
        self._fabrica = fabrica

    def buscar(
        self,
        consulta: ConsultaInterpretada,
        campus_id: str,
        fecha: date,
        ahora: datetime,
        limite: int,
    ) -> list[Oferta]:
        base: dict[str, Any] = {
            "campus": campus_id,
            "fecha": fecha,
            "ahora": ahora,
            "limite": limite,
        }
        filtros: list[str] = []
        topes = [v for v in (consulta.precio_max_unitario_cop, consulta.presupuesto_total_cop) if v]
        if topes:
            base["precio_max"] = min(topes)
            filtros.append("and p.precio_cop <= :precio_max")
        if consulta.franja_id:
            base["franja"] = consulta.franja_id
            filtros.append("and tu.franja_id = :franja")
        puntos = [consulta.punto_id] if consulta.punto_id else consulta.punto_candidatos
        if puntos:
            base["puntos"] = puntos
            filtros.append("and tu.punto_id = any(cast(:puntos as text[]))")

        mejores: dict[tuple[UUID, UUID], Oferta] = {}
        with self._fabrica() as s:
            if not any(i.termino or i.categoria or i.etiquetas for i in consulta.items):
                sql = _SQL_OFERTAS.format(relevancia="0", filtros="\n  ".join(filtros))
                filas = s.execute(text(sql), {**base, "minimo": 1}).mappings()
                return [_oferta(f, None) for f in filas]
            for indice, item in enumerate(consulta.items):
                if not (item.termino or item.categoria or item.etiquetas):
                    continue
                params = {**base, "minimo": max(1, min(item.cantidad or 1, 50))}
                condicion, relevancia = _condicion_item(item, params)
                sql = _SQL_OFERTAS.format(
                    relevancia=relevancia,
                    filtros="\n  ".join([*filtros, f"and ({condicion})"]),
                )
                for f in s.execute(text(sql), params).mappings():
                    oferta = _oferta(f, indice)
                    clave = (oferta.producto_id, oferta.turno_id)
                    if clave not in mejores or mejores[clave].relevancia < oferta.relevancia:
                        mejores[clave] = oferta
        return sorted(mejores.values(), key=lambda o: (-o.relevancia, o.precio_cop))[:limite]


class LectorContextoBusquedaSql:
    def __init__(self, fabrica: sessionmaker[Session]) -> None:
        self._fabrica = fabrica

    def contexto(self, campus_id: str, ahora: datetime) -> ContextoCampusBusqueda:
        with self._fabrica() as s:
            zona = s.execute(
                select(campus.c.zona_horaria).where(campus.c.id == campus_id)
            ).scalar_one_or_none()
            if zona is None:
                raise LookupError(f"Campus desconocido: {campus_id}")
            fecha = ahora.astimezone(ZoneInfo(zona)).date()
            puntos = [
                PuntoEncuentro(
                    f["id"],
                    f["campus_id"],
                    f["nombre"],
                    f["descripcion"],
                    f["foto_url"],
                    tuple(f["alias"]),
                    f["activo"],
                )
                for f in s.execute(
                    select(puntos_encuentro).where(
                        puntos_encuentro.c.campus_id == campus_id, puntos_encuentro.c.activo
                    )
                ).mappings()
            ]
            todas = [
                Franja(f["id"], f["campus_id"], f["hora_inicio"], f["hora_fin"])
                for f in s.execute(
                    select(franjas)
                    .where(franjas.c.campus_id == campus_id)
                    .order_by(franjas.c.hora_inicio)
                ).mappings()
            ]
            abiertas = [f for f in todas if not f.ha_pasado(fecha, ahora, ZoneInfo(zona))]
            productos = list(
                s.execute(
                    text(
                        f"""
                        select distinct p.nombre_normalizado
                        from stock_turno s
                          join productos p on p.id = s.producto_id and p.activo
                          join turnos tu on tu.id = s.turno_id
                          join tiendas ti on ti.id = tu.tienda_id and ti.activa
                          join campus c on c.id = ti.campus_id
                          join franjas f on f.id = tu.franja_id
                        where ti.campus_id = :campus and tu.fecha = :fecha
                          and {_SQL_ABIERTA} and s.total > s.reservado
                        order by 1 limit 300
                        """
                    ),
                    {"campus": campus_id, "fecha": fecha, "ahora": ahora},
                ).scalars()
            )
        return ContextoCampusBusqueda(campus_id, zona, fecha, puntos, abiertas, productos)


class RegistroBusquedasSql:
    def __init__(self, fabrica: sessionmaker[Session]) -> None:
        self._fabrica = fabrica

    def registrar(self, registro: RegistroBusqueda, traza: Traza) -> None:
        datos_traza = traza.a_dict()
        tokens = traza.tokens_entrada + traza.tokens_salida + traza.tokens_razonamiento
        with self._fabrica() as s, s.begin():
            guardar_traza(s, datos_traza, traza.duracion_s)
            s.execute(
                insert(busquedas).values(
                    id=registro.id,
                    campus_id=registro.campus_id,
                    usuario_id=registro.usuario_id,
                    texto=registro.texto,
                    interprete=registro.interprete,
                    consulta=registro.consulta.model_dump(mode="json"),
                    anulados=list(registro.anulados),
                    relajados=list(registro.relajados),
                    n_tiendas=registro.n_tiendas,
                    n_productos=registro.n_productos,
                    latencia_ms=registro.latencia_ms,
                    tokens=tokens,
                    costo_usd=traza.costo_usd,
                    run_id=traza.run_id,
                    creada_en=registro.creada_en,
                )
            )

    def texto_de(self, busqueda_id: UUID) -> str | None:
        with self._fabrica() as s:
            return s.execute(
                select(busquedas.c.texto).where(busquedas.c.id == busqueda_id)
            ).scalar_one_or_none()

    def registrar_clic(
        self,
        busqueda_id: UUID,
        tienda_id: UUID,
        producto_id: UUID | None,
        posicion: int,
        en: datetime,
    ) -> None:
        with self._fabrica() as s, s.begin():
            s.execute(
                insert(busqueda_clics).values(
                    id=uuid4(),
                    busqueda_id=busqueda_id,
                    tienda_id=tienda_id,
                    producto_id=producto_id,
                    posicion=posicion,
                    creado_en=en,
                )
            )
