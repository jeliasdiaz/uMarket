"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { api, datos } from "@/api/cliente";
import { Aviso, Boton } from "@/ui/componentes";

const CAMPO =
  "w-full rounded-xl border border-stone-300 bg-white px-3 py-2.5 focus:border-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-700/30";

export function FormEntrar() {
  const router = useRouter();
  const volver = useSearchParams().get("volver");
  const cliente = useQueryClient();
  const [correo, setCorreo] = useState("");
  const [codigo, setCodigo] = useState("");
  const [nombre, setNombre] = useState("");
  const [acepta, setAcepta] = useState(false);
  const [enviado, setEnviado] = useState(false);

  const pedir = useMutation({
    mutationFn: () => datos(api.POST("/v1/auth/codigo", { body: { correo } })),
    onSuccess: () => setEnviado(true),
  });
  const verificar = useMutation({
    mutationFn: () =>
      datos(api.POST("/v1/auth/verificar", { body: { correo, codigo, nombre: nombre || null, acepta_terminos: acepta } })),
    onSuccess: (usuario) => {
      cliente.setQueryData(["sesion"], usuario);
      // Solo rutas internas: un "volver" externo seria una redireccion abierta.
      router.push(volver?.startsWith("/") && !volver.startsWith("//") ? volver : "/");
    },
  });

  if (!enviado) {
    return (
      <form
        className="space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
          pedir.mutate();
        }}
      >
        <label htmlFor="correo" className="block text-sm font-semibold">
          Tu correo institucional
        </label>
        <input id="correo" type="email" required value={correo} onChange={(e) => setCorreo(e.target.value)} className={CAMPO} placeholder="nombre@universidad.edu.co" />
        {pedir.error && <Aviso tono="error">{pedir.error.message}</Aviso>}
        <Boton type="submit" className="w-full" disabled={pedir.isPending}>
          Enviarme un código
        </Boton>
      </form>
    );
  }

  return (
    <form
      className="space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        verificar.mutate();
      }}
    >
      <Aviso tono="exito">Te enviamos un código de 6 dígitos a {correo}.</Aviso>
      <label htmlFor="codigo" className="block text-sm font-semibold">
        Código
      </label>
      <input id="codigo" inputMode="numeric" pattern="\d{6}" maxLength={6} required value={codigo} onChange={(e) => setCodigo(e.target.value)} className={CAMPO} autoComplete="one-time-code" />
      <label htmlFor="nombre" className="block text-sm font-semibold">
        Tu nombre (si es tu primera vez)
      </label>
      <input id="nombre" value={nombre} onChange={(e) => setNombre(e.target.value)} maxLength={60} className={CAMPO} />
      <label className="flex items-start gap-2 text-sm">
        <input type="checkbox" checked={acepta} onChange={(e) => setAcepta(e.target.checked)} className="mt-1" />
        <span>Autorizo el tratamiento de mis datos personales según la Ley 1581 de 2012 para usar uMarket.</span>
      </label>
      {verificar.error && <Aviso tono="error">{verificar.error.message}</Aviso>}
      <Boton type="submit" className="w-full" disabled={verificar.isPending}>
        Entrar
      </Boton>
      <button type="button" className="text-sm text-stone-600 underline" onClick={() => setEnviado(false)}>
        Usar otro correo
      </button>
    </form>
  );
}
