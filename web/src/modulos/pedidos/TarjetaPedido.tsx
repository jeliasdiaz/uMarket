"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";

import { type Accion, api, datos, type Pedido } from "@/api/cliente";
import { Aviso, Boton, Tarjeta } from "@/ui/componentes";
import { hora, minutosRestantes, NOMBRE_ACCION, NOMBRE_ESTADO, pesos } from "@/ui/formato";

const PIDEN_MOTIVO: Accion[] = ["rechazar", "cancelar"];

/** Un pedido con SOLO las acciones que el backend dice que este usuario puede tomar. */
export function TarjetaPedido({ pedido, vista }: { pedido: Pedido; vista: "comprador" | "vendedor" }) {
  const cliente = useQueryClient();
  const actuar = useMutation({
    mutationFn: ({ accion, motivo }: { accion: Accion; motivo: string | null }) =>
      datos(
        api.POST("/v1/pedidos/{pedido_id}/{accion}", {
          params: { path: { pedido_id: pedido.id, accion } },
          body: { motivo },
        }),
      ),
    onSuccess: (actualizado) => {
      cliente.setQueryData(["pedido", pedido.id], actualizado);
      cliente.invalidateQueries({ queryKey: ["bandeja"] });
      cliente.invalidateQueries({ queryKey: ["mis-pedidos"] });
    },
  });

  return (
    <Tarjeta>
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-xs uppercase tracking-wide text-stone-500">Código</p>
          <p className="font-mono text-2xl font-bold tracking-widest">{pedido.codigo}</p>
        </div>
        <span className="rounded-full bg-stone-100 px-3 py-1 text-xs font-semibold">{NOMBRE_ESTADO[pedido.estado] ?? pedido.estado}</span>
      </div>
      <p className="mt-2 text-sm text-stone-700">
        {vista === "vendedor" ? (
          <>Para {pedido.comprador_nombre}</>
        ) : (
          <Link href={`/t/${pedido.tienda_slug}`} className="underline">
            {pedido.tienda_nombre}
          </Link>
        )}{" "}
        · {pedido.franja_etiqueta} · {pedido.punto_nombre}
      </p>
      <ul className="mt-2 text-sm">
        {pedido.items.map((i) => (
          <li key={i.producto_id} className="flex justify-between">
            <span>
              {i.cantidad} × {i.nombre}
            </span>
            <span>{pesos(i.precio_unitario_cop * i.cantidad)}</span>
          </li>
        ))}
      </ul>
      <p className="mt-2 flex justify-between border-t border-stone-100 pt-2 font-semibold">
        <span>Total</span>
        <span>{pesos(pedido.total_cop)}</span>
      </p>
      {pedido.estado === "pendiente" && (
        <p className="mt-1 text-xs text-stone-600">Vence a las {hora(pedido.vence_en)} ({minutosRestantes(pedido.vence_en)} min) si el vendedor no responde.</p>
      )}
      {pedido.motivo && <p className="mt-1 text-xs text-stone-600">Motivo: {pedido.motivo}</p>}
      {actuar.error && <div className="mt-2"><Aviso tono="error">{actuar.error.message}</Aviso></div>}
      {pedido.acciones.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {pedido.acciones.map((accion) => (
            <Boton
              key={accion}
              variante={PIDEN_MOTIVO.includes(accion) || accion === "no_asistio" ? "peligro" : "primario"}
              disabled={actuar.isPending}
              onClick={() => {
                const motivo = PIDEN_MOTIVO.includes(accion) ? window.prompt("¿Por qué? (opcional)") : null;
                actuar.mutate({ accion, motivo });
              }}
            >
              {NOMBRE_ACCION[accion] ?? accion}
            </Boton>
          ))}
        </div>
      )}
    </Tarjeta>
  );
}
