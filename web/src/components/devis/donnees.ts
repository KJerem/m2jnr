"use client";

import { useQuery, type QueryClient } from "@tanstack/react-query";
import { ApiError, apiFetch } from "@/lib/api";
import type { DevisDetail, DevisEntree, StatutDevis } from "@/lib/devis";

/** Devis courant d'un OT (le devis non refusé, à défaut le dernier refusé ; null s'il n'en a pas). */
export const cleDevisOrdre = (ordreId: number) => ["devis", "ordre", ordreId] as const;

export function useDevisOrdre(ordreId: number) {
  return useQuery({
    queryKey: cleDevisOrdre(ordreId),
    queryFn: async ({ signal }) => {
      try {
        return await apiFetch<DevisDetail>(`/ordres/${ordreId}/devis`, { signal });
      } catch (erreur) {
        // « Aucun devis pour cet ordre de travail. » : un état normal, pas une erreur.
        if (erreur instanceof ApiError && erreur.status === 404 && erreur.code === "introuvable") return null;
        throw erreur;
      }
    },
  });
}

/** Story S4.2 : « envoye », « accepte » ou « refuse ». */
export function changerStatutDevis(devisId: number, nouveau: StatutDevis) {
  return apiFetch<DevisDetail>(`/devis/${devisId}/statut`, { method: "POST", body: { nouveau } });
}

export function enregistrerDevis(ordreId: number, devis: DevisDetail | null, entree: DevisEntree) {
  return devis
    ? apiFetch<DevisDetail>(`/devis/${devis.id}`, { method: "PUT", body: entree })
    : apiFetch<DevisDetail>(`/ordres/${ordreId}/devis`, { method: "POST", body: entree });
}

/**
 * À appeler après toute écriture sur un devis ou une facture : recharge les listes « Devis &
 * factures », la fiche de l'OT (lien vers sa facture) et le tableau de bord (facturé du jour,
 * « Facture à établir »). Le devis de la fiche est mis à jour par l'appelant avec la réponse.
 */
export function rafraichirApresDevis(queryClient: QueryClient): Promise<void> {
  return Promise.all([
    queryClient.invalidateQueries({ queryKey: ["devis"], predicate: (q) => q.queryKey[1] !== "ordre" }),
    queryClient.invalidateQueries({ queryKey: ["factures"] }),
    queryClient.invalidateQueries({ queryKey: ["ordres", "fiche"] }),
    queryClient.invalidateQueries({ queryKey: ["tableau-de-bord"] }),
    queryClient.invalidateQueries({ queryKey: ["recherche"] }),
  ]).then(() => undefined);
}
