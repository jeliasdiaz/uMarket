"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Boton } from "@/ui/componentes";

const EJEMPLOS = ["algo dulce por menos de 5 mil", "2 empanadas pa las 12", "algo sin carne"];

export function CajaBusqueda({ inicial = "" }: { inicial?: string }) {
  const router = useRouter();
  const [texto, setTexto] = useState(inicial);

  function buscar(valor: string) {
    const limpio = valor.trim();
    if (limpio) router.push(`/buscar?q=${encodeURIComponent(limpio)}`);
  }

  return (
    <form
      role="search"
      onSubmit={(e) => {
        e.preventDefault();
        buscar(texto);
      }}
      className="space-y-2"
    >
      <label htmlFor="busqueda" className="block text-sm font-semibold text-stone-700">
        ¿Qué se te antoja?
      </label>
      <div className="flex gap-2">
        <input
          id="busqueda"
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          maxLength={200}
          placeholder="Escribe como le dirías a un amigo"
          className="min-w-0 flex-1 rounded-xl border border-stone-300 bg-white px-3 py-2.5 text-base focus:border-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-700/30"
        />
        <Boton type="submit">Buscar</Boton>
      </div>
      <p className="flex flex-wrap gap-2 text-xs text-stone-600">
        Prueba:
        {EJEMPLOS.map((ejemplo) => (
          <button key={ejemplo} type="button" onClick={() => buscar(ejemplo)} className="underline decoration-dotted hover:text-emerald-800">
            {ejemplo}
          </button>
        ))}
      </p>
    </form>
  );
}
