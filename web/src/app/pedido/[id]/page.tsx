import { Suspense } from "react";

import { EstadoPedido } from "@/modulos/pedidos/EstadoPedido";
import { Cargando } from "@/ui/componentes";

export default function PaginaPedido() {
  return (
    <Suspense fallback={<Cargando />}>
      <EstadoPedido />
    </Suspense>
  );
}
