/**
 * El carrito: logica pura, sin React, testeada con Vitest.
 *
 * Un pedido es para UN turno (una tienda, una franja, un punto). Agregar algo de
 * otro turno empieza un carrito nuevo: la interfaz lo avisa antes.
 *
 * El subtotal es solo informativo. El pedido viaja SIN precios: el backend pone
 * el precio de catalogo y calcula el total (PLAN-TECNICO.md §5.2).
 */

export type LineaCarrito = {
  producto_id: string;
  nombre: string;
  precio_cop: number;
  cantidad: number;
  disponible: number;
};

export type Carrito = {
  clave: string;
  tienda: { slug: string; nombre: string };
  turno: { id: string; franja_etiqueta: string; punto_nombre: string };
  lineas: LineaCarrito[];
  origen: "tienda" | "busqueda";
  busqueda_id: string | null;
};

export type NuevoPedido = {
  turno_id: string;
  items: { producto_id: string; cantidad: number }[];
  origen: "tienda" | "busqueda";
  busqueda_id: string | null;
};

const MAX_POR_ITEM = 20;

function nuevaClave(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `c-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function acotar(cantidad: number, disponible: number): number {
  return Math.max(0, Math.min(cantidad, disponible, MAX_POR_ITEM));
}

export function vacio(
  tienda: Carrito["tienda"],
  turno: Carrito["turno"],
  origen: Carrito["origen"] = "tienda",
  busqueda_id: string | null = null,
): Carrito {
  return { clave: nuevaClave(), tienda, turno, lineas: [], origen, busqueda_id };
}

export function esDeOtroTurno(carrito: Carrito | null, turnoId: string): boolean {
  return carrito !== null && carrito.lineas.length > 0 && carrito.turno.id !== turnoId;
}

/** Agrega unidades a una linea (o la crea). Nunca supera lo disponible. */
export function agregar(carrito: Carrito, linea: Omit<LineaCarrito, "cantidad">, cantidad = 1): Carrito {
  const existente = carrito.lineas.find((l) => l.producto_id === linea.producto_id);
  const total = acotar((existente?.cantidad ?? 0) + cantidad, linea.disponible);
  if (total === 0) return carrito;
  const lineas = existente
    ? carrito.lineas.map((l) => (l.producto_id === linea.producto_id ? { ...l, ...linea, cantidad: total } : l))
    : [...carrito.lineas, { ...linea, cantidad: total }];
  return { ...carrito, lineas };
}

/** Cambia la cantidad; en 0 quita la linea. */
export function cambiarCantidad(carrito: Carrito, productoId: string, cantidad: number): Carrito {
  const lineas = carrito.lineas
    .map((l) => (l.producto_id === productoId ? { ...l, cantidad: acotar(cantidad, l.disponible) } : l))
    .filter((l) => l.cantidad > 0);
  return { ...carrito, lineas };
}

export function subtotalInformativo(carrito: Carrito): number {
  return carrito.lineas.reduce((suma, l) => suma + l.precio_cop * l.cantidad, 0);
}

export function unidades(carrito: Carrito | null): number {
  return carrito?.lineas.reduce((suma, l) => suma + l.cantidad, 0) ?? 0;
}

/** El cuerpo de POST /v1/pedidos. Sin precios ni total, a proposito. */
export function aPedido(carrito: Carrito): NuevoPedido {
  return {
    turno_id: carrito.turno.id,
    items: carrito.lineas.map((l) => ({ producto_id: l.producto_id, cantidad: l.cantidad })),
    origen: carrito.origen,
    busqueda_id: carrito.busqueda_id,
  };
}
