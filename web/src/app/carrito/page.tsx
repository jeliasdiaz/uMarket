"use client";

import { useMutation } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { api, datos } from "@/api/cliente";
import { guardarCarrito, useCarrito } from "@/modulos/carrito/almacen";
import { aPedido, cambiarCantidad, subtotalInformativo } from "@/modulos/carrito/carrito";
import { useSesion } from "@/modulos/identidad/sesion";
import { Aviso, Boton, Tarjeta } from "@/ui/componentes";
import { pesos } from "@/ui/formato";

export default function PaginaCarrito() {
  const carrito = useCarrito();
  const { data: usuario } = useSesion();
  const router = useRouter();

  const confirmar = useMutation({
    mutationFn: () => {
      if (!carrito) throw new Error("Carrito vacío");
      // La clave del carrito hace que un doble toque cree UN solo pedido.
      return datos(api.POST("/v1/pedidos", { body: aPedido(carrito), params: { header: { "idempotency-key": carrito.clave } } }));
    },
    onSuccess: (pedido) => {
      guardarCarrito(null);
      router.push(`/pedido/${pedido.id}`);
    },
  });

  if (!carrito || carrito.lineas.length === 0) {
    return (
      <div className="space-y-3">
        <h1 className="text-xl font-bold">Tu carrito</h1>
        <Aviso>Está vacío. Busca algo que se te antoje.</Aviso>
        <Link href="/" className="text-emerald-800 underline">
          Ir a buscar
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Tu pedido a {carrito.tienda.nombre}</h1>
      <Tarjeta>
        <p className="text-sm text-stone-600">
          Lo recibes en <strong>{carrito.turno.punto_nombre}</strong>, franja <strong>{carrito.turno.franja_etiqueta}</strong>. Pagas en
          persona: QR de Bre-B o efectivo.
        </p>
        <ul className="mt-3 divide-y divide-stone-100">
          {carrito.lineas.map((l) => (
            <li key={l.producto_id} className="flex items-center justify-between gap-2 py-2 text-sm">
              <span>{l.nombre}</span>
              <span className="flex items-center gap-2">
                <button
                  aria-label={`Quitar uno de ${l.nombre}`}
                  className="h-8 w-8 rounded-lg bg-stone-100 font-bold"
                  onClick={() => guardarCarrito(cambiarCantidad(carrito, l.producto_id, l.cantidad - 1))}
                >
                  −
                </button>
                <span aria-live="polite" className="w-6 text-center">
                  {l.cantidad}
                </span>
                <button
                  aria-label={`Agregar uno de ${l.nombre}`}
                  className="h-8 w-8 rounded-lg bg-stone-100 font-bold disabled:opacity-40"
                  disabled={l.cantidad >= l.disponible}
                  onClick={() => guardarCarrito(cambiarCantidad(carrito, l.producto_id, l.cantidad + 1))}
                >
                  +
                </button>
                <span className="w-20 text-right">{pesos(l.precio_cop * l.cantidad)}</span>
              </span>
            </li>
          ))}
        </ul>
        <p className="mt-3 flex justify-between border-t border-stone-200 pt-3 font-semibold">
          <span>Subtotal</span>
          <span>{pesos(subtotalInformativo(carrito))}</span>
        </p>
        <p className="text-xs text-stone-500">El total final lo confirma la tienda con los precios del catálogo.</p>
      </Tarjeta>
      {confirmar.error && <Aviso tono="error">{confirmar.error.message}</Aviso>}
      {usuario ? (
        <Boton className="w-full py-3" disabled={confirmar.isPending} onClick={() => confirmar.mutate()}>
          {confirmar.isPending ? "Enviando…" : "Confirmar pedido"}
        </Boton>
      ) : (
        <Link href="/entrar?volver=/carrito" className="block rounded-xl bg-emerald-700 py-3 text-center font-semibold text-white">
          Entra con tu correo institucional para pedir
        </Link>
      )}
      <Boton variante="suave" className="w-full" onClick={() => guardarCarrito(null)}>
        Vaciar carrito
      </Boton>
    </div>
  );
}
