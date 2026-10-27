import { CajaBusqueda } from "@/modulos/busqueda/CajaBusqueda";
import { ListaTiendas } from "@/modulos/catalogo/ListaTiendas";

export default function Inicio() {
  return (
    <div className="space-y-6">
      <section className="rounded-3xl bg-emerald-800 p-5 text-white">
        <h1 className="text-2xl font-bold">La tienda de tu campus</h1>
        <p className="mt-1 text-sm text-emerald-50">
          Mira quién vende qué, dónde y a qué hora. Pides con clics y pagas en persona.
        </p>
        <div className="mt-4 rounded-2xl bg-white p-3 text-stone-900">
          <CajaBusqueda />
        </div>
      </section>
      <section aria-labelledby="titulo-tiendas" className="space-y-3">
        <h2 id="titulo-tiendas" className="text-lg font-semibold">
          Tiendas del campus
        </h2>
        <ListaTiendas />
      </section>
    </div>
  );
}
