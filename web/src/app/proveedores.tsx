"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode, useEffect, useState } from "react";

export function Proveedores({ children }: { children: ReactNode }) {
  const [cliente] = useState(
    () =>
      new QueryClient({
        defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: true, staleTime: 5_000 } },
      }),
  );

  useEffect(() => {
    // El service worker recibe los avisos push (PWA). Si el navegador no lo
    // soporta, la app funciona igual: los avisos llegan al abrirla.
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch(() => undefined);
    }
  }, []);

  return <QueryClientProvider client={cliente}>{children}</QueryClientProvider>;
}
