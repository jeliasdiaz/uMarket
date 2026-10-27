"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { api, datos } from "@/api/cliente";
import { Aviso, Cargando, Estrellas, Tarjeta } from "@/ui/componentes";

export function ListaTiendas() {
  const { data: tiendas, isLoading, error } = useQuery({
    queryKey: ["tiendas"],
    queryFn: () => datos(api.GET("/v1/tiendas")),
  });

  if (isLoading) return <Cargando texto="Cargando tiendas…" />;
  if (error) return <Aviso tono="error">{error.message}</Aviso>;
  if (!tiendas?.length) return <Aviso>Todavía no hay tiendas en tu campus.</Aviso>;

  return (
    <ul className="grid gap-3 sm:grid-cols-2">
      {tiendas.map((t) => (
        <li key={t.id}>
          <Link href={`/t/${t.slug}`} className="block focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-700">
            <Tarjeta className="h-full transition hover:ring-emerald-700">
              <h3 className="font-semibold">{t.nombre}</h3>
              <p className="line-clamp-2 text-sm text-stone-600">{t.descripcion}</p>
              <p className="mt-2 flex items-center justify-between text-xs text-stone-600">
                <Estrellas promedio={t.reputacion.promedio} resenas={t.reputacion.resenas} />
                <span>{t.turnos_abiertos_hoy > 0 ? `${t.turnos_abiertos_hoy} turno(s) hoy` : "Sin turnos hoy"}</span>
              </p>
            </Tarjeta>
          </Link>
        </li>
      ))}
    </ul>
  );
}
