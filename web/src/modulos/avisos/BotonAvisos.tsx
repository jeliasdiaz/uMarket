"use client";

import { useState } from "react";

import { api, datos } from "@/api/cliente";
import { Aviso, Boton } from "@/ui/componentes";

function base64AUint8(base64: string): Uint8Array<ArrayBuffer> {
  const relleno = "=".repeat((4 - (base64.length % 4)) % 4);
  const crudo = atob((base64 + relleno).replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(crudo, (c) => c.charCodeAt(0));
}

/**
 * Activa los avisos push. En iPhone solo funcionan con la app instalada en la
 * pantalla de inicio (riesgo de PLAN-Y-DECISIONES §9): se explica aqui mismo.
 */
export function BotonAvisos() {
  const [estado, setEstado] = useState<"inicial" | "activo" | "error" | "no-soportado">("inicial");
  const [detalle, setDetalle] = useState("");

  async function activar() {
    if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
      setEstado("no-soportado");
      return;
    }
    try {
      const { clave } = await datos(api.GET("/v1/push/clave-publica"));
      if (!clave) throw new Error("El servidor no tiene avisos push configurados todavía.");
      if ((await Notification.requestPermission()) !== "granted") throw new Error("No diste permiso para avisos.");
      const registro = await navigator.serviceWorker.ready;
      const suscripcion = await registro.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: base64AUint8(clave),
      });
      const json = suscripcion.toJSON();
      await datos(
        api.POST("/v1/push/suscripciones", {
          body: { endpoint: json.endpoint ?? "", keys: { p256dh: json.keys?.p256dh ?? "", auth: json.keys?.auth ?? "" } },
        }),
      );
      setEstado("activo");
    } catch (e) {
      setEstado("error");
      setDetalle(e instanceof Error ? e.message : "No se pudo activar.");
    }
  }

  if (estado === "activo") return <Aviso tono="exito">Avisos activados: te avisamos de cada pedido nuevo.</Aviso>;
  return (
    <div className="space-y-2">
      <Boton variante="secundario" onClick={activar}>
        Activar avisos de pedidos
      </Boton>
      {estado === "no-soportado" && (
        <Aviso>Tu navegador no soporta avisos. En iPhone, agrega uMarket a la pantalla de inicio y ábrela desde ahí.</Aviso>
      )}
      {estado === "error" && <Aviso tono="error">{detalle}</Aviso>}
    </div>
  );
}
