"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api, datos, ErrorApi, type Esquemas, type MiTienda } from "@/api/cliente";
import { Aviso, Boton, Cargando, Tarjeta } from "@/ui/componentes";
import { pesos } from "@/ui/formato";

const CAMPO = "w-full rounded-xl border border-stone-300 bg-white px-3 py-2 focus:border-emerald-700 focus:outline-none";

function manana(hoy: string): string {
  const d = new Date(`${hoy}T12:00:00`);
  d.setDate(d.getDate() + 1);
  return d.toISOString().slice(0, 10);
}

export default function GestionTienda() {
  const cliente = useQueryClient();
  const tienda = useQuery({
    queryKey: ["mi-tienda"],
    queryFn: async (): Promise<MiTienda | null> => {
      try {
        return await datos(api.GET("/v1/vendedor/tienda"));
      } catch (e) {
        if (e instanceof ErrorApi && e.tipo === "sin_tienda") return null;
        throw e;
      }
    },
  });
  const refrescar = () => {
    cliente.invalidateQueries({ queryKey: ["mi-tienda"] });
    cliente.invalidateQueries({ queryKey: ["sesion"] });
  };

  if (tienda.isLoading) return <Cargando />;
  if (tienda.error) return <Aviso tono="error">{tienda.error.message}</Aviso>;
  if (!tienda.data) return <CrearTienda alCrear={refrescar} />;
  return <Panel tienda={tienda.data} alCambiar={refrescar} />;
}

function CrearTienda({ alCrear }: { alCrear: () => void }) {
  const [nombre, setNombre] = useState("");
  const [descripcion, setDescripcion] = useState("");
  const crear = useMutation({
    mutationFn: () => datos(api.POST("/v1/vendedor/tienda", { body: { nombre, descripcion } })),
    onSuccess: alCrear,
  });
  return (
    <Tarjeta>
      <form
        className="space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
          crear.mutate();
        }}
      >
        <h1 className="text-xl font-bold">Crea tu tienda</h1>
        <label htmlFor="nombre-tienda" className="block text-sm font-semibold">
          Nombre
        </label>
        <input id="nombre-tienda" required minLength={2} maxLength={60} value={nombre} onChange={(e) => setNombre(e.target.value)} className={CAMPO} />
        <label htmlFor="descripcion-tienda" className="block text-sm font-semibold">
          Descripción
        </label>
        <input id="descripcion-tienda" maxLength={280} value={descripcion} onChange={(e) => setDescripcion(e.target.value)} className={CAMPO} />
        {crear.error && <Aviso tono="error">{crear.error.message}</Aviso>}
        <Boton type="submit" disabled={crear.isPending}>
          Crear tienda
        </Boton>
      </form>
    </Tarjeta>
  );
}

function Panel({ tienda, alCambiar }: { tienda: MiTienda; alCambiar: () => void }) {
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">{tienda.nombre}</h1>
      <Productos tienda={tienda} alCambiar={alCambiar} />
      <Turnos tienda={tienda} alCambiar={alCambiar} />
    </div>
  );
}

function Productos({ tienda, alCambiar }: { tienda: MiTienda; alCambiar: () => void }) {
  const vocabulario = useQuery({ queryKey: ["vocabulario"], queryFn: () => datos(api.GET("/v1/vocabulario")) });
  const [nombre, setNombre] = useState("");
  const [precio, setPrecio] = useState("");
  const [categoria, setCategoria] = useState<Esquemas["Categoria"]>("otros");
  const [etiquetas, setEtiquetas] = useState<Esquemas["Etiqueta"][]>([]);
  const crear = useMutation({
    mutationFn: () =>
      datos(api.POST("/v1/vendedor/productos", { body: { nombre, categoria, etiquetas, precio_cop: Number(precio), descripcion: "", activo: true } })),
    onSuccess: () => {
      setNombre("");
      setPrecio("");
      setEtiquetas([]);
      alCambiar();
    },
  });
  const alternar = useMutation({
    mutationFn: (p: Esquemas["ProductoDTO"]) =>
      datos(
        api.PUT("/v1/vendedor/productos/{producto_id}", {
          params: { path: { producto_id: p.id } },
          body: { nombre: p.nombre, descripcion: p.descripcion, categoria: p.categoria, etiquetas: p.etiquetas, precio_cop: p.precio_cop, activo: !p.activo },
        }),
      ),
    onSuccess: alCambiar,
  });

  return (
    <Tarjeta>
      <h2 className="font-semibold">Productos</h2>
      <ul className="mt-2 divide-y divide-stone-100 text-sm">
        {tienda.productos.map((p) => (
          <li key={p.id} className="flex items-center justify-between py-2">
            <span className={p.activo ? "" : "text-stone-400 line-through"}>
              {p.nombre} · {pesos(p.precio_cop)}
              <span className="block text-xs text-stone-500">
                {p.categoria}
                {p.etiquetas.length > 0 && ` · ${p.etiquetas.join(", ")}`}
              </span>
            </span>
            <Boton variante="suave" className="px-3 py-1" onClick={() => alternar.mutate(p)}>
              {p.activo ? "Ocultar" : "Mostrar"}
            </Boton>
          </li>
        ))}
      </ul>
      <form
        className="mt-3 space-y-2 border-t border-stone-100 pt-3"
        onSubmit={(e) => {
          e.preventDefault();
          crear.mutate();
        }}
      >
        <p className="text-sm font-semibold">Nuevo producto</p>
        <label className="block text-xs text-stone-600" htmlFor="producto-nombre">
          Nombre
        </label>
        <input id="producto-nombre" required minLength={2} maxLength={60} value={nombre} onChange={(e) => setNombre(e.target.value)} className={CAMPO} />
        <div className="flex gap-2">
          <div className="flex-1">
            <label className="block text-xs text-stone-600" htmlFor="producto-precio">
              Precio (COP)
            </label>
            <input id="producto-precio" required type="number" min={100} max={500000} value={precio} onChange={(e) => setPrecio(e.target.value)} className={CAMPO} />
          </div>
          <div className="flex-1">
            <label className="block text-xs text-stone-600" htmlFor="producto-categoria">
              Categoría
            </label>
            <select id="producto-categoria" value={categoria} onChange={(e) => setCategoria(e.target.value as Esquemas["Categoria"])} className={CAMPO}>
              {vocabulario.data?.categorias.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </div>
        </div>
        <fieldset className="flex flex-wrap gap-3 text-sm">
          <legend className="text-xs text-stone-600">Etiquetas (ayudan a que te encuentren)</legend>
          {vocabulario.data?.etiquetas.map((e) => (
            <label key={e} className="flex items-center gap-1">
              <input
                type="checkbox"
                checked={etiquetas.includes(e)}
                onChange={() => setEtiquetas((actual) => (actual.includes(e) ? actual.filter((x) => x !== e) : [...actual, e].slice(0, 4)))}
              />
              {e}
            </label>
          ))}
        </fieldset>
        {crear.error && <Aviso tono="error">{crear.error.message}</Aviso>}
        <Boton type="submit" disabled={crear.isPending}>
          Agregar producto
        </Boton>
      </form>
    </Tarjeta>
  );
}

function Turnos({ tienda, alCambiar }: { tienda: MiTienda; alCambiar: () => void }) {
  const campus = useQuery({ queryKey: ["campus"], queryFn: () => datos(api.GET("/v1/campus/actual")) });
  const [fecha, setFecha] = useState(tienda.hoy);
  const [franja, setFranja] = useState("");
  const [punto, setPunto] = useState("");
  const [stock, setStock] = useState<Record<string, string>>({});
  const activos = tienda.productos.filter((p) => p.activo);
  const nombres = new Map(tienda.productos.map((p) => [p.id, p.nombre]));

  const publicar = useMutation({
    mutationFn: () =>
      datos(
        api.POST("/v1/vendedor/turnos", {
          body: {
            fecha,
            franja_id: franja || campus.data?.franjas[0]?.id || "",
            punto_id: punto || campus.data?.puntos[0]?.id || "",
            stock: Object.entries(stock)
              .filter(([, v]) => Number(v) > 0)
              .map(([producto_id, v]) => ({ producto_id, total: Number(v) })),
          },
        }),
      ),
    onSuccess: () => {
      setStock({});
      alCambiar();
    },
  });
  const duplicar = useMutation({
    mutationFn: () => datos(api.POST("/v1/vendedor/turnos/duplicar", { body: { desde: tienda.hoy, hacia: manana(tienda.hoy) } })),
    onSuccess: alCambiar,
  });

  return (
    <Tarjeta>
      <h2 className="font-semibold">Turnos</h2>
      <p className="text-xs text-stone-600">Un turno dice dónde estarás, en qué franja y con cuánto stock.</p>
      <ul className="mt-2 space-y-2 text-sm">
        {tienda.turnos.map((t) => (
          <li key={t.id} className={`rounded-xl p-2 ring-1 ring-stone-200 ${t.abierto ? "" : "opacity-60"}`}>
            <p className="font-medium">
              {t.fecha} · {t.franja_etiqueta} · {t.punto_nombre}
            </p>
            <p className="text-xs text-stone-600">
              {t.ofertas.map((o) => `${nombres.get(o.producto_id)}: ${o.disponible}/${o.total}`).join(" · ")}
            </p>
          </li>
        ))}
      </ul>
      <Boton variante="suave" className="mt-2" disabled={duplicar.isPending} onClick={() => duplicar.mutate()}>
        Repetir los turnos de hoy mañana
      </Boton>
      {duplicar.isSuccess && <p className="mt-1 text-xs text-stone-600">{duplicar.data.length} turno(s) copiado(s).</p>}
      <form
        className="mt-3 space-y-2 border-t border-stone-100 pt-3"
        onSubmit={(e) => {
          e.preventDefault();
          publicar.mutate();
        }}
      >
        <p className="text-sm font-semibold">Publicar turno</p>
        <div className="grid grid-cols-3 gap-2">
          <div>
            <label className="block text-xs text-stone-600" htmlFor="turno-fecha">
              Día
            </label>
            <input id="turno-fecha" type="date" value={fecha} min={tienda.hoy} onChange={(e) => setFecha(e.target.value)} className={CAMPO} />
          </div>
          <div>
            <label className="block text-xs text-stone-600" htmlFor="turno-franja">
              Franja
            </label>
            <select id="turno-franja" value={franja} onChange={(e) => setFranja(e.target.value)} className={CAMPO}>
              {campus.data?.franjas.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.etiqueta}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-stone-600" htmlFor="turno-punto">
              Punto
            </label>
            <select id="turno-punto" value={punto} onChange={(e) => setPunto(e.target.value)} className={CAMPO}>
              {campus.data?.puntos.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.nombre}
                </option>
              ))}
            </select>
          </div>
        </div>
        {activos.map((p) => (
          <label key={p.id} className="flex items-center justify-between gap-2 text-sm">
            {p.nombre}
            <input
              type="number"
              min={0}
              max={500}
              placeholder="0"
              aria-label={`Unidades de ${p.nombre}`}
              value={stock[p.id] ?? ""}
              onChange={(e) => setStock((s) => ({ ...s, [p.id]: e.target.value }))}
              className="w-24 rounded-lg border border-stone-300 px-2 py-1"
            />
          </label>
        ))}
        {activos.length === 0 && <Aviso>Agrega productos antes de publicar un turno.</Aviso>}
        {publicar.error && <Aviso tono="error">{publicar.error.message}</Aviso>}
        <Boton type="submit" disabled={publicar.isPending || activos.length === 0}>
          Publicar turno
        </Boton>
      </form>
    </Tarjeta>
  );
}
