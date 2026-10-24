"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { OrdreDetail, UtilisateurResume } from "@/lib/ordres";
import type { Vehicule } from "@/lib/vehicules";

/** Clés de cache partagées : invalider ["ordres"] rafraîchit listes, fiches et kanban. */
export const cleOrdre = (id: number) => ["ordres", "fiche", id] as const;

export function useOrdre(id: number) {
  return useQuery({
    queryKey: cleOrdre(id),
    queryFn: ({ signal }) => apiFetch<OrdreDetail>(`/ordres/${id}`, { signal }),
  });
}

export function useMecaniciens() {
  return useQuery({
    queryKey: ["mecaniciens"],
    queryFn: ({ signal }) => apiFetch<UtilisateurResume[]>("/mecaniciens", { signal }),
    staleTime: 5 * 60_000,
  });
}

export function useVehicules() {
  return useQuery({
    queryKey: ["vehicules", "liste"],
    queryFn: ({ signal }) => apiFetch<Vehicule[]>("/vehicules", { signal }),
  });
}
