"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { api, datos } from "@/api/cliente";
import { useCarrito } from "@/modulos/carrito/almacen";
import { agregarAlCarrito } from "@/modulos/carrito/agregar";
import { Aviso, Boton, Cargando, Estrellas, Tarjeta } from "@/ui/componentes";
import { pesos } from "@/ui/formato";

export function VistaTienda({ slug }: { slug: string }) {
  const carrito = useCarrito();
  const [mensaje, setMensaje] = useState<string | null>(null);
  const tienda = useQuery({
    queryKey: ["tienda", slug],
    queryFn: () => datos(api.GET("/v1/tiendas/{slug}", { params: { path: { slug } } })),
    refetchInterval: 30_000,
  });
  const resenas = useQuery({
    queryKey: ["resenas", slug],
    queryFn: () => datos(api.GET("/v1/tiendas/{slug}/resenas", { params: { path: { slug } } })),
  });

  if (tienda.isLoading) return <Cargando texto="Cargando tienda…" />;
  if (tienda.error || !tienda.data) return <Aviso tono="error">{tienda.error?.message ?? "No encontramos la tienda."}</Aviso>;
  const t = tienda.data;
  const productos = new Map(t.productos.map((p) => [p.id, p]));
  const abiertos = t.turnos.filter((turno) => turno.abierto);

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-bold">{t.nombre}</h1>
        <p className="text-sm text-stone-600">{t.descripcion}</p>
        <p className="mt-1 flex gap-3 text-xs text-stone-600">
          <Estrellas promedio={t.reputacion.promedio} resenas={t.reputacion.resenas} />
          {t.reputacion.porcentaje_cumplido != null && <span>{t.reputacion.porcentaje_cumplido}% de entregas cumplidas</span>}
        </p>
      </header>
      {mensaje && <Aviso tono="exito">{mensaje}</Aviso>}
      {abiertos.length === 0 && <Aviso>Esta tienda no tiene turnos abiertos ahora. Vuelve más tarde.</Aviso>}
      {abiertos.map((turno) => (
        <Tarjeta key={turno.id}>
          <h2 className="font-semibold">
            {turno.franja_etiqueta} · {turno.punto_nombre}
          </h2>
          <ul className="mt-2 divide-y divide-stone-100">
            {turno.ofertas.map((oferta) => {
              const p = productos.get(oferta.producto_id);
              if (!p) return null;
              return (
                <li key={p.id} className="flex items-center justify-between gap-2 py-2 text-sm">
                  <span>
                    {p.nombre}
                    <span className="block text-xs text-stone-500">
                      {oferta.disponible > 0 ? `Quedan ${oferta.disponible}` : "Agotado"}
                      {p.etiquetas.length > 0 && ` · ${p.etiquetas.join(", ")}`}
                    </span>
                  </span>
                  <span className="flex items-center gap-2">
                    <span className="font-medium">{pesos(p.precio_cop)}</span>
                    <Boton
                      variante="secundario"
                      className="px-3 py-1.5"
                      disabled={oferta.disponible === 0}
                      aria-label={`Agregar ${p.nombre}`}
                      onClick={() => {
                        const ok = agregarAlCarrito(
                          carrito,
                          {
                            tienda: { slug: t.slug, nombre: t.nombre },
                            turno: { id: turno.id, franja_etiqueta: turno.franja_etiqueta, punto_nombre: turno.punto_nombre },
                          },
                          { producto_id: p.id, nombre: p.nombre, precio_cop: p.precio_cop, disponible: oferta.disponible },
                        );
                        if (ok) setMensaje(`Agregaste ${p.nombre}.`);
                      }}
                    >
                      +
                    </Boton>
                  </span>
                </li>
              );
            })}
          </ul>
        </Tarjeta>
      ))}
      {carrito && carrito.lineas.length > 0 && (
        <Link href="/carrito" className="block rounded-xl bg-emerald-700 py-3 text-center font-semibold text-white">
          Ver carrito
        </Link>
      )}
      <section aria-labelledby="titulo-resenas" className="space-y-2">
        <h2 id="titulo-resenas" className="font-semibold">
          Reseñas
        </h2>
        {resenas.data?.length ? (
          <ul className="space-y-2">
            {resenas.data.map((r, i) => (
              <li key={i} className="rounded-xl bg-white p-3 text-sm ring-1 ring-stone-200">
                <span aria-label={`${r.estrellas} de 5`}>{"★".repeat(r.estrellas)}</span> {r.comentario}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-stone-500">Aún no hay reseñas. Solo califica quien recibió un pedido.</p>
        )}
      </section>
    </div>
  );
}
