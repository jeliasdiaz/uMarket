import type { Metadata } from "next";
import { cacheLife } from "next/cache";
import { Suspense } from "react";

import { VistaTienda } from "@/modulos/catalogo/VistaTienda";
import { Cargando } from "@/ui/componentes";

const API = process.env.UMARKET_API_URL ?? "http://localhost:8000";

/**
 * Nombre y descripcion de la tienda, para la vista previa del link en WhatsApp
 * (Open Graph). Cambian poco: se cachean unos minutos. El stock NO va aqui: lo
 * pide el cliente fresco.
 */
async function cabeceraTienda(slug: string): Promise<{ nombre: string; descripcion: string } | null> {
  "use cache";
  cacheLife("minutes");
  try {
    const r = await fetch(`${API}/v1/tiendas/${encodeURIComponent(slug)}`);
    if (!r.ok) return null;
    const t = (await r.json()) as { nombre: string; descripcion: string };
    return { nombre: t.nombre, descripcion: t.descripcion };
  } catch {
    return null;
  }
}

export async function generateMetadata({ params }: PageProps<"/t/[slug]">): Promise<Metadata> {
  const { slug } = await params;
  const t = await cabeceraTienda(slug);
  if (!t) return { title: "Tienda" };
  const descripcion = t.descripcion || `Pide en ${t.nombre} desde uMarket.`;
  return {
    title: t.nombre,
    description: descripcion,
    openGraph: { title: `${t.nombre} · uMarket`, description: descripcion, type: "website" },
  };
}

async function Contenido({ params }: { params: PageProps<"/t/[slug]">["params"] }) {
  const { slug } = await params;
  return <VistaTienda slug={slug} />;
}

export default function PaginaTienda(props: PageProps<"/t/[slug]">) {
  return (
    <Suspense fallback={<Cargando texto="Cargando tienda…" />}>
      <Contenido params={props.params} />
    </Suspense>
  );
}
