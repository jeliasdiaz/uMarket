"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, datos, ErrorApi, type Usuario } from "@/api/cliente";

/** El usuario de la sesion, o null si no hay. La cookie la maneja el navegador. */
export function useSesion() {
  return useQuery({
    queryKey: ["sesion"],
    queryFn: async (): Promise<Usuario | null> => {
      try {
        return await datos(api.GET("/v1/yo"));
      } catch (error) {
        if (error instanceof ErrorApi && error.estado === 401) return null;
        throw error;
      }
    },
    staleTime: 60_000,
  });
}

export function useSalir() {
  const cliente = useQueryClient();
  return useMutation({
    mutationFn: () => datos(api.POST("/v1/auth/salir")),
    onSuccess: () => cliente.setQueryData(["sesion"], null),
  });
}
