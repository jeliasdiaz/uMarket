"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";

import { api, type Consulta, datos, type Resultado } from "@/api/cliente";
import { useCarrito } from "@/modulos/carrito/almacen";
import { agregarAlCarrito } from "@/modulos/carrito/agregar";
import { Aviso, Boton, Cargando, Estrellas, Tarjeta } from "@/ui/componentes";
import { pesos } from "@/ui/formato";

import { CajaBusqueda } from "./CajaBusqueda";

const RELAJADO: Record<string, string> = {
  punto: "el punto",
  franja: "la hora",
  precio: "el precio",
};

/** La consulta sin el filtro de ese campo. Lo mismo que `quitar()` del backend. */
function sinFiltro(consulta: Consulta, campo: string): Consulta {
  if (campo.startsWith("items.")) {
    const indice = Number(campo.split(".")[1]);
    return { ...consulta, items: (consulta.items ?? []).filter((_, i) => i !== indice) };
  }
  if (campo === "orden") return { ...consulta, orden: "relevancia" };
  return { ...consulta, [campo]: null };
}

export function Resultados() {
  const q = useSearchParams().get("q") ?? "";
  const carrito = useCarrito();
  // El refinado pertenece a UNA consulta: si cambia q, deja de aplicar sin efectos.
  const [refinado, setRefinado] = useState<{ q: string; resultado: Resultado } | null>(null);
  const [mensaje, setMensaje] = useState<string | null>(null);

  const busqueda = useQuery({
    queryKey: ["busqueda", q],
    queryFn: () => datos(api.POST("/v1/busquedas", { body: { texto: q } })),
    enabled: q.length > 0,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  const refinar = useMutation({
    mutationFn: ({ id, consulta }: { id: string; consulta: Consulta }) =>
      datos(api.POST("/v1/busquedas/{busqueda_id}/filtros", { params: { path: { busqueda_id: id } }, body: { consulta } })),
    onSuccess: (resultado) => setRefinado({ q, resultado }),
  });

  const r = refinado?.q === q ? refinado.resultado : busqueda.data;

  return (
    <div className="space-y-4">
      <CajaBusqueda key={q} inicial={q} />
      {busqueda.isLoading && <Cargando texto="Buscando quién lo tiene…" />}
      {busqueda.error && <Aviso tono="error">{busqueda.error.message}</Aviso>}
      {mensaje && <Aviso tono="exito">{mensaje}</Aviso>}
      {r && (
        <>
          {r.filtros.length > 0 && (
            <div className="flex flex-wrap items-center gap-2 text-sm" aria-label="Filtros entendidos">
              <span className="text-stone-600">Entendimos:</span>
              {r.filtros.map((f) => (
                <button
                  key={f.campo}
                  onClick={() => refinar.mutate({ id: r.busqueda_id, consulta: sinFiltro(r.consulta, f.campo) })}
                  className="rounded-full bg-emerald-50 px-3 py-1 text-emerald-900 ring-1 ring-emerald-200 hover:bg-emerald-100"
                  aria-label={`Quitar filtro ${f.etiqueta}`}
                >
                  {f.etiqueta} <span aria-hidden>×</span>
                </button>
              ))}
            </div>
          )}
          {r.pregunta_punto.length > 0 && (
            <Tarjeta>
              <p className="text-sm font-medium">¿En cuál punto?</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {r.pregunta_punto.map((p) => (
                  <Boton
                    key={p.id}
                    variante="secundario"
                    onClick={() =>
                      refinar.mutate({
                        id: r.busqueda_id,
                        consulta: { ...r.consulta, punto_id: p.id, punto_candidatos: [] },
                      })
                    }
                  >
                    {p.nombre}
                  </Boton>
                ))}
              </div>
            </Tarjeta>
          )}
          {r.relajados.length > 0 && r.tiendas.length > 0 && (
            <Aviso>
              No encontramos todo lo que pediste; quitamos {r.relajados.map((x) => RELAJADO[x] ?? x).join(" y ")}. Esto es lo más parecido:
            </Aviso>
          )}
          {r.tiendas.length === 0 && <Aviso>Nadie lo tiene disponible ahora. Prueba con otra cosa u otra hora.</Aviso>}
          <ul className="space-y-3">
            {r.tiendas.map((t, posicion) => (
              <li key={`${t.tienda_id}-${t.turno_id}`}>
                <Tarjeta>
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <Link
                        href={`/t/${t.slug}`}
                        className="font-semibold hover:underline"
                        onClick={() =>
                          api.POST("/v1/busquedas/{busqueda_id}/clics", {
                            params: { path: { busqueda_id: r.busqueda_id } },
                            body: { tienda_id: t.tienda_id, posicion },
                          })
                        }
                      >
                        {t.nombre}
                      </Link>
                      <p className="text-xs text-stone-600">
                        {t.franja_etiqueta} · {t.punto_nombre}
                      </p>
                    </div>
                    <Estrellas promedio={t.promedio} resenas={t.resenas} />
                  </div>
                  <ul className="mt-3 divide-y divide-stone-100">
                    {t.productos.map((p) => (
                      <li key={p.producto_id} className="flex items-center justify-between gap-2 py-2 text-sm">
                        <span>
                          {p.nombre} <span className="text-stone-500">· quedan {p.disponible}</span>
                        </span>
                        <span className="flex items-center gap-2">
                          <span className="font-medium">{pesos(p.precio_cop)}</span>
                          <Boton
                            variante="secundario"
                            className="px-3 py-1.5"
                            aria-label={`Agregar ${p.cantidad_sugerida} ${p.nombre}`}
                            onClick={() => {
                              const ok = agregarAlCarrito(
                                carrito,
                                {
                                  tienda: { slug: t.slug, nombre: t.nombre },
                                  turno: { id: t.turno_id, franja_etiqueta: t.franja_etiqueta, punto_nombre: t.punto_nombre },
                                  origen: "busqueda",
                                  busqueda_id: r.busqueda_id,
                                },
                                { producto_id: p.producto_id, nombre: p.nombre, precio_cop: p.precio_cop, disponible: p.disponible },
                                p.cantidad_sugerida,
                              );
                              if (ok) {
                                setMensaje(`Agregaste ${p.cantidad_sugerida} × ${p.nombre}.`);
                                api.POST("/v1/busquedas/{busqueda_id}/clics", {
                                  params: { path: { busqueda_id: r.busqueda_id } },
                                  body: { tienda_id: t.tienda_id, producto_id: p.producto_id, posicion },
                                });
                              }
                            }}
                          >
                            + {p.cantidad_sugerida > 1 ? p.cantidad_sugerida : ""}
                          </Boton>
                        </span>
                      </li>
                    ))}
                  </ul>
                </Tarjeta>
              </li>
            ))}
          </ul>
          {carrito && carrito.lineas.length > 0 && (
            <Link href="/carrito" className="block rounded-xl bg-emerald-700 py-3 text-center font-semibold text-white">
              Ver carrito y elegir cómo recibirlo
            </Link>
          )}
        </>
      )}
    </div>
  );
}
