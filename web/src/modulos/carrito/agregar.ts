"use client";

import { agregar, type Carrito, esDeOtroTurno, type LineaCarrito, vacio } from "./carrito";
import { guardarCarrito } from "./almacen";

type Destino = {
  tienda: Carrito["tienda"];
  turno: Carrito["turno"];
  origen?: Carrito["origen"];
  busqueda_id?: string | null;
};

/** Agrega al carrito; si es de otro turno, pregunta antes de empezar uno nuevo. */
export function agregarAlCarrito(
  actual: Carrito | null,
  destino: Destino,
  linea: Omit<LineaCarrito, "cantidad">,
  cantidad = 1,
): boolean {
  if (esDeOtroTurno(actual, destino.turno.id)) {
    const seguir = window.confirm(
      `Tu carrito es de ${actual?.tienda.nombre} (${actual?.turno.franja_etiqueta}). ` +
        "Un pedido es para una sola tienda y franja. ¿Empezar un carrito nuevo?",
    );
    if (!seguir) return false;
  }
  const base =
    actual && !esDeOtroTurno(actual, destino.turno.id) && actual.lineas.length > 0
      ? actual
      : vacio(destino.tienda, destino.turno, destino.origen ?? "tienda", destino.busqueda_id ?? null);
  guardarCarrito(agregar(base, linea, cantidad));
  return true;
}
