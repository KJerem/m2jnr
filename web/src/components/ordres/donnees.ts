"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { OrdreDetail, UtilisateurResume } from "@/lib/ordres";
import type { Page } from "@/lib/clients";
import type { Vehicule } from "@/lib/vehicules";

/** Plafond de l'API pour une page de véhicules (GET /vehicules?taille=). */
export const TAILLE_CHOIX_VEHICULES = 1000;

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

/** Véhicules proposés dans les listes de choix (OT, rendez-vous) : une seule grande page. */
export function useVehicules() {
  return useQuery({
    queryKey: ["vehicules", "choix"],
    queryFn: async ({ signal }) => (await apiFetch<Page<Vehicule>>(`/vehicules?taille=${TAILLE_CHOIX_VEHICULES}`, { signal })).elements,
  });
}
