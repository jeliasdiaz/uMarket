import type { Metadata, Viewport } from "next";

import { Encabezado } from "@/modulos/identidad/Encabezado";

import "./globals.css";
import { Proveedores } from "./proveedores";

export const metadata: Metadata = {
  title: { default: "uMarket · La tienda del campus", template: "%s · uMarket" },
  description: "Escribe lo que se te antoja y mira quién lo tiene en tu campus, dónde y a qué hora.",
  applicationName: "uMarket",
};

export const viewport: Viewport = { themeColor: "#047857", width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="es-CO" className="h-full antialiased">
      <body className="min-h-full bg-stone-50 text-stone-900">
        <Proveedores>
          <Encabezado />
          <main className="mx-auto max-w-3xl px-4 py-5">{children}</main>
        </Proveedores>
      </body>
    </html>
  );
}
