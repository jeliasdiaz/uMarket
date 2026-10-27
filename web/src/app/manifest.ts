import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "uMarket · La tienda del campus",
    short_name: "uMarket",
    description: "Pide a estudiantes que venden en tu campus. Pagas en persona.",
    start_url: "/",
    display: "standalone",
    background_color: "#fafaf9",
    theme_color: "#047857",
    lang: "es-CO",
    icons: [{ src: "/icono.svg", sizes: "any", type: "image/svg+xml" }],
  };
}
