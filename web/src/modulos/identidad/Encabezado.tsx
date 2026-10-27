"use client";

import Link from "next/link";

import { unidades } from "@/modulos/carrito/carrito";
import { useCarrito } from "@/modulos/carrito/almacen";

import { useSalir, useSesion } from "./sesion";

export function Encabezado() {
  const { data: usuario } = useSesion();
  const salir = useSalir();
  const carrito = useCarrito();
  const enCarrito = unidades(carrito);

  return (
    <header className="sticky top-0 z-10 border-b border-stone-200 bg-white/95 backdrop-blur">
      <nav aria-label="Principal" className="mx-auto flex max-w-3xl items-center gap-3 px-4 py-3 text-sm">
        <Link href="/" className="text-lg font-bold text-emerald-800">
          uMarket
        </Link>
        <span className="flex-1" />
        <Link href="/carrito" className="font-medium text-stone-700 hover:text-emerald-800">
          Carrito{enCarrito > 0 && <span className="ml-1 rounded-full bg-emerald-700 px-2 text-white">{enCarrito}</span>}
        </Link>
        {usuario ? (
          <>
            <Link href="/pedidos" className="font-medium text-stone-700 hover:text-emerald-800">
              Mis pedidos
            </Link>
            <Link href={usuario.tienda_slug ? "/vendedor" : "/vendedor/tienda"} className="font-medium text-stone-700 hover:text-emerald-800">
              {usuario.tienda_slug ? "Mi tienda" : "Vender"}
            </Link>
            <button onClick={() => salir.mutate()} className="text-stone-500 hover:text-stone-800">
              Salir
            </button>
          </>
        ) : (
          <Link href="/entrar" className="rounded-lg bg-emerald-700 px-3 py-1.5 font-semibold text-white">
            Entrar
          </Link>
        )}
      </nav>
    </header>
  );
}
