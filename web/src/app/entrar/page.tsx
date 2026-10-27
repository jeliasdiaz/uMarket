import type { Metadata } from "next";
import { Suspense } from "react";

import { FormEntrar } from "@/modulos/identidad/FormEntrar";
import { Cargando, Tarjeta } from "@/ui/componentes";

export const metadata: Metadata = { title: "Entrar" };

export default function PaginaEntrar() {
  return (
    <div className="mx-auto max-w-sm space-y-4">
      <h1 className="text-xl font-bold">Entrar a uMarket</h1>
      <p className="text-sm text-stone-600">Sin contraseñas: te enviamos un código a tu correo de la universidad.</p>
      <Tarjeta>
        <Suspense fallback={<Cargando />}>
          <FormEntrar />
        </Suspense>
      </Tarjeta>
    </div>
  );
}
