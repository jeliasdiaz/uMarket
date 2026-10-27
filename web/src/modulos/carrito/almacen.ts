"use client";

/**
 * El carrito compartido entre paginas, guardado en localStorage.
 *
 * localStorage puede fallar (modo privado, almacenamiento bloqueado): todo acceso
 * va en try/catch y, si falla, el carrito vive solo en memoria.
 */
import { useSyncExternalStore } from "react";

import type { Carrito } from "./carrito";

const CLAVE = "umarket.carrito.v1";
const oyentes = new Set<() => void>();
let actual: Carrito | null = null;
let leido = false;

function leer(): Carrito | null {
  if (!leido && typeof window !== "undefined") {
    leido = true;
    try {
      const crudo = window.localStorage.getItem(CLAVE);
      actual = crudo ? (JSON.parse(crudo) as Carrito) : null;
    } catch {
      actual = null;
    }
  }
  return actual;
}

export function guardarCarrito(carrito: Carrito | null): void {
  actual = carrito;
  leido = true;
  try {
    if (carrito) window.localStorage.setItem(CLAVE, JSON.stringify(carrito));
    else window.localStorage.removeItem(CLAVE);
  } catch {
    // Sin almacenamiento: el carrito sigue en memoria mientras la pestana viva.
  }
  oyentes.forEach((oyente) => oyente());
}

function suscribir(oyente: () => void): () => void {
  oyentes.add(oyente);
  return () => oyentes.delete(oyente);
}

export function useCarrito(): Carrito | null {
  return useSyncExternalStore(suscribir, leer, () => null);
}
