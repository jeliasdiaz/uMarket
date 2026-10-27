"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { api, datos } from "@/api/cliente";
import { Aviso, Cargando } from "@/ui/componentes";
import { NOMBRE_ESTADO, pesos } from "@/ui/formato";

export default function MisPedidos() {
  const pedidos = useQuery({ queryKey: ["mis-pedidos"], queryFn: () => datos(api.GET("/v1/pedidos")) });

  if (pedidos.isLoading) return <Cargando />;
  if (pedidos.error) return <Aviso tono="error">{pedidos.error.message}</Aviso>;

  return (
    <div className="space-y-3">
      <h1 className="text-xl font-bold">Mis pedidos</h1>
      {pedidos.data?.length === 0 && <Aviso>Todavía no has pedido nada.</Aviso>}
      <ul className="space-y-2">
        {pedidos.data?.map((p) => (
          <li key={p.id}>
            <Link href={`/pedido/${p.id}`} className="flex items-center justify-between rounded-xl bg-white p-3 text-sm ring-1 ring-stone-200 hover:ring-emerald-700">
              <span>
                <span className="font-mono font-bold">{p.codigo}</span> · {p.tienda_nombre}
                <span className="block text-xs text-stone-500">
                  {p.fecha} · {p.franja_etiqueta}
                </span>
              </span>
              <span className="text-right">
                {pesos(p.total_cop)}
                <span className="block text-xs text-stone-500">{NOMBRE_ESTADO[p.estado]}</span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
