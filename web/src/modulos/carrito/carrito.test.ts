import { describe, expect, it } from "vitest";

import { aPedido, agregar, cambiarCantidad, esDeOtroTurno, subtotalInformativo, unidades, vacio } from "./carrito";

const TIENDA = { slug: "dona-rosa", nombre: "Doña Rosa" };
const TURNO = { id: "t1", franja_etiqueta: "12:00–12:30", punto_nombre: "Bloque 19" };
const POLLO = { producto_id: "p1", nombre: "Empanada de pollo", precio_cop: 3000, disponible: 3 };

describe("carrito", () => {
  it("agrega y suma la misma linea", () => {
    const c = agregar(agregar(vacio(TIENDA, TURNO), POLLO), POLLO);
    expect(c.lineas).toHaveLength(1);
    expect(c.lineas[0].cantidad).toBe(2);
    expect(unidades(c)).toBe(2);
  });

  it("nunca supera lo disponible", () => {
    const c = agregar(vacio(TIENDA, TURNO), POLLO, 10);
    expect(c.lineas[0].cantidad).toBe(3);
  });

  it("cambiar a cero quita la linea", () => {
    const c = cambiarCantidad(agregar(vacio(TIENDA, TURNO), POLLO), "p1", 0);
    expect(c.lineas).toHaveLength(0);
  });

  it("el subtotal es informativo y el pedido viaja SIN precios", () => {
    const c = agregar(vacio(TIENDA, TURNO, "busqueda", "b1"), POLLO, 2);
    expect(subtotalInformativo(c)).toBe(6000);
    const pedido = aPedido(c);
    expect(pedido).toEqual({
      turno_id: "t1",
      items: [{ producto_id: "p1", cantidad: 2 }],
      origen: "busqueda",
      busqueda_id: "b1",
    });
    expect(JSON.stringify(pedido)).not.toContain("precio");
  });

  it("detecta un producto de otro turno", () => {
    const c = agregar(vacio(TIENDA, TURNO), POLLO);
    expect(esDeOtroTurno(c, "t2")).toBe(true);
    expect(esDeOtroTurno(c, "t1")).toBe(false);
    expect(esDeOtroTurno(null, "t2")).toBe(false);
  });

  it("cada carrito nuevo tiene su propia clave de idempotencia", () => {
    expect(vacio(TIENDA, TURNO).clave).not.toBe(vacio(TIENDA, TURNO).clave);
  });
});
