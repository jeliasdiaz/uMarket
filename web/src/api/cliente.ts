/**
 * El cliente de la API, tipado desde el OpenAPI del backend.
 *
 * Ningun tipo de la API se escribe a mano: `esquema.d.ts` se genera con
 * `npm run api:tipos` desde `backend/contratos/openapi.json`, y la CI falla si
 * quedo desactualizado. El frontend MUESTRA; las decisiones (precios, totales,
 * stock, estados) las toma el backend.
 */
import createClient from "openapi-fetch";

import type { components, paths } from "./esquema";

export type Esquemas = components["schemas"];
export type Pedido = Esquemas["PedidoDTO"];
export type Tienda = Esquemas["TiendaDTO"];
export type MiTienda = Esquemas["MiTiendaDTO"];
export type ResumenTienda = Esquemas["ResumenTiendaDTO"];
export type Resultado = Esquemas["ResultadoBusquedaDTO"];
export type Consulta = Esquemas["ConsultaInterpretada"];
export type Usuario = Esquemas["UsuarioDTO"];
export type Campus = Esquemas["CampusDTO"];
export type Accion = Esquemas["Accion"];
export type Producto = Esquemas["ProductoDTO"];
export type Turno = Esquemas["TurnoDTO"];

export const api = createClient<paths>({ baseUrl: "/api", credentials: "include" });

/** Un error de dominio del backend (RFC 9457). `tipo` es estable; `detail`, para personas. */
export class ErrorApi extends Error {
  constructor(
    readonly estado: number,
    readonly tipo: string,
    mensaje: string,
    readonly detalles: Record<string, unknown> = {},
  ) {
    super(mensaje);
  }
}

type Respuesta<T> = { data?: T; error?: unknown; response: Response };

/** Desenvuelve la respuesta de openapi-fetch: devuelve los datos o lanza `ErrorApi`. */
export async function datos<T>(promesa: Promise<Respuesta<T>>): Promise<T> {
  const { data, error, response } = await promesa;
  if (response.ok) return data as T;
  const cuerpo = (error ?? {}) as { tipo?: string; detail?: unknown; detalles?: Record<string, unknown> };
  const mensaje =
    typeof cuerpo.detail === "string"
      ? cuerpo.detail
      : response.status === 422
        ? "Revisa los datos del formulario."
        : "Algo salio mal. Intenta otra vez.";
  throw new ErrorApi(response.status, cuerpo.tipo ?? "error", mensaje, cuerpo.detalles ?? {});
}
