"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { api, datos } from "@/api/cliente";
import { BotonAvisos } from "@/modulos/avisos/BotonAvisos";
import { TarjetaPedido } from "@/modulos/pedidos/TarjetaPedido";
import { Aviso, Cargando } from "@/ui/componentes";

export default function Bandeja() {
  // Polling cada 10 s ademas del push (PLAN-TECNICO §10). Pasar a SSE tiene su disparador en §17.
  const bandeja = useQuery({
    queryKey: ["bandeja"],
    queryFn: () => datos(api.GET("/v1/vendedor/pedidos")),
    refetchInterval: 10_000,
  });

  const pendientes = bandeja.data?.filter((p) => p.acciones.length > 0) ?? [];
  const cerrados = bandeja.data?.filter((p) => p.acciones.length === 0) ?? [];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Pedidos</h1>
        <Link href="/vendedor/tienda" className="text-sm font-medium text-emerald-800 underline">
          Productos y turnos
        </Link>
      </div>
      <BotonAvisos />
      {bandeja.isLoading && <Cargando />}
      {bandeja.error && <Aviso tono="error">{bandeja.error.message}</Aviso>}
      {bandeja.data && pendientes.length === 0 && <Aviso>No tienes pedidos por atender. Se actualiza solo.</Aviso>}
      <ul className="space-y-3">
        {pendientes.map((p) => (
          <li key={p.id}>
            <TarjetaPedido pedido={p} vista="vendedor" />
          </li>
        ))}
      </ul>
      {cerrados.length > 0 && (
        <details>
          <summary className="cursor-pointer text-sm text-stone-600">Atendidos ({cerrados.length})</summary>
          <ul className="mt-2 space-y-3">
            {cerrados.map((p) => (
              <li key={p.id}>
                <TarjetaPedido pedido={p} vista="vendedor" />
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
