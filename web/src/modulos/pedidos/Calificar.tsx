"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api, datos } from "@/api/cliente";
import { Aviso, Boton, Tarjeta } from "@/ui/componentes";

export function Calificar({ pedidoId }: { pedidoId: string }) {
  const cliente = useQueryClient();
  const [estrellas, setEstrellas] = useState(5);
  const [comentario, setComentario] = useState("");
  const enviar = useMutation({
    mutationFn: () => datos(api.POST("/v1/calificaciones", { body: { pedido_id: pedidoId, estrellas, comentario } })),
    onSuccess: () => cliente.invalidateQueries({ queryKey: ["pedido", pedidoId] }),
  });

  return (
    <Tarjeta>
      <form
        className="space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
          enviar.mutate();
        }}
      >
        <fieldset>
          <legend className="text-sm font-semibold">¿Cómo te fue?</legend>
          <div className="mt-1 flex gap-1">
            {[1, 2, 3, 4, 5].map((n) => (
              <button
                key={n}
                type="button"
                aria-label={`${n} estrellas`}
                aria-pressed={n <= estrellas}
                onClick={() => setEstrellas(n)}
                className={`text-2xl ${n <= estrellas ? "text-amber-500" : "text-stone-300"}`}
              >
                ★
              </button>
            ))}
          </div>
        </fieldset>
        <label htmlFor="comentario" className="block text-sm font-semibold">
          Comentario (opcional)
        </label>
        <textarea id="comentario" maxLength={280} value={comentario} onChange={(e) => setComentario(e.target.value)} className="w-full rounded-xl border border-stone-300 p-2" />
        {enviar.error && <Aviso tono="error">{enviar.error.message}</Aviso>}
        <Boton type="submit" disabled={enviar.isPending}>
          Calificar
        </Boton>
      </form>
    </Tarjeta>
  );
}
