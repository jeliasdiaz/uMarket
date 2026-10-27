import type { Metadata } from "next";
import { Suspense } from "react";

import { Resultados } from "@/modulos/busqueda/Resultados";
import { Cargando } from "@/ui/componentes";

export const metadata: Metadata = { title: "Buscar" };

export default function PaginaBuscar() {
  return (
    <Suspense fallback={<Cargando />}>
      <Resultados />
    </Suspense>
  );
}
