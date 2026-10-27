/** Componentes base. Accesibles: etiquetas visibles, foco visible, contraste AA. */
import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variante = "primario" | "secundario" | "peligro" | "suave";

const ESTILOS: Record<Variante, string> = {
  primario: "bg-emerald-700 text-white hover:bg-emerald-800 disabled:bg-emerald-300",
  secundario: "bg-white text-emerald-800 ring-1 ring-emerald-700 hover:bg-emerald-50",
  peligro: "bg-white text-red-700 ring-1 ring-red-700 hover:bg-red-50",
  suave: "bg-stone-100 text-stone-800 hover:bg-stone-200",
};

export function Boton({
  variante = "primario",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variante?: Variante }) {
  return (
    <button
      className={`rounded-xl px-4 py-2.5 text-sm font-semibold transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 disabled:cursor-not-allowed ${ESTILOS[variante]} ${className}`}
      {...props}
    />
  );
}

export function Tarjeta({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-2xl bg-white p-4 shadow-sm ring-1 ring-stone-200 ${className}`}>{children}</section>;
}

export function Aviso({ children, tono = "info" }: { children: ReactNode; tono?: "info" | "error" | "exito" }) {
  const colores = {
    info: "bg-sky-50 text-sky-900 ring-sky-200",
    error: "bg-red-50 text-red-900 ring-red-200",
    exito: "bg-emerald-50 text-emerald-900 ring-emerald-200",
  };
  return (
    <p role={tono === "error" ? "alert" : "status"} className={`rounded-xl px-3 py-2 text-sm ring-1 ${colores[tono]}`}>
      {children}
    </p>
  );
}

export function Cargando({ texto = "Cargando…" }: { texto?: string }) {
  return (
    <p role="status" className="animate-pulse py-6 text-center text-sm text-stone-500">
      {texto}
    </p>
  );
}

export function Estrellas({ promedio, resenas }: { promedio: number | null | undefined; resenas: number }) {
  if (!promedio || resenas === 0) return <span className="text-xs text-stone-500">Sin reseñas</span>;
  return (
    <span className="text-xs text-stone-700" aria-label={`${promedio} de 5 estrellas, ${resenas} reseñas`}>
      ★ {promedio.toFixed(1)} <span className="text-stone-500">({resenas})</span>
    </span>
  );
}
