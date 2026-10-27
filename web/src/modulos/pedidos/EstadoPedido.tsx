"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";

import { api, datos } from "@/api/cliente";
import { Aviso, Cargando } from "@/ui/componentes";

import { Calificar } from "./Calificar";
import { TarjetaPedido } from "./TarjetaPedido";

const PISTA: Record<string, string> = {
  pendiente: "Le avisamos al vendedor. Tiene 30 minutos para aprobarlo.",
  aprobado: "¡Aprobado! Ve al punto en tu franja. Te avisamos cuando llegue el vendedor.",
  en_punto: "El vendedor llegó. Di tu código y paga con Bre-B o en efectivo.",
  entregado: "¡Listo! Tu calificación ayuda a otros estudiantes.",
  vencido: "El vendedor no respondió a tiempo. Prueba con otra tienda.",
};

export function EstadoPedido() {
  const { id } = useParams<{ id: string }>();
  const pedido = useQuery({
    queryKey: ["pedido", id],
    queryFn: () => datos(api.GET("/v1/pedidos/{pedido_id}", { params: { path: { pedido_id: id } } })),
    // Polling mientras el pedido esta abierto; los avisos push llegan aparte.
    refetchInterval: (q) => (["pendiente", "aprobado", "en_punto"].includes(q.state.data?.estado ?? "") ? 10_000 : false),
  });

  if (pedido.isLoading) return <Cargando />;
  if (pedido.error || !pedido.data) return <Aviso tono="error">{pedido.error?.message ?? "No encontramos el pedido."}</Aviso>;
  const p = pedido.data;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Tu pedido</h1>
      {PISTA[p.estado] && <Aviso tono={p.estado === "vencido" ? "error" : "info"}>{PISTA[p.estado]}</Aviso>}
      <TarjetaPedido pedido={p} vista="comprador" />
      {p.estado === "entregado" && !p.calificado && <Calificar pedidoId={p.id} />}
    </div>
  );
}
