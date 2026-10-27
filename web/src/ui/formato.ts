/** Formatos de presentacion. Solo presentacion: los valores vienen del backend. */

const PESOS = new Intl.NumberFormat("es-CO", {
  style: "currency",
  currency: "COP",
  maximumFractionDigits: 0,
});

export function pesos(valor: number): string {
  return PESOS.format(valor).replace(/\s/g, "");
}

export function hora(iso: string): string {
  return new Date(iso).toLocaleTimeString("es-CO", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "America/Bogota",
  });
}

export function minutosRestantes(hasta: string, ahora: Date = new Date()): number {
  return Math.max(0, Math.ceil((new Date(hasta).getTime() - ahora.getTime()) / 60000));
}

export const NOMBRE_ESTADO: Record<string, string> = {
  pendiente: "Esperando al vendedor",
  aprobado: "Aprobado",
  rechazado: "Rechazado",
  vencido: "Vencido",
  cancelado: "Cancelado",
  en_punto: "El vendedor llego",
  entregado: "Entregado",
  no_asistio: "No asistio",
};

export const NOMBRE_ACCION: Record<string, string> = {
  aprobar: "Aprobar",
  rechazar: "Rechazar",
  cancelar: "Cancelar",
  llegue: "Llegue",
  entregar: "Entregado",
  no_asistio: "No vino",
  vencer: "Vencer",
};
