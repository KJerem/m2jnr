"use client";

import type { QueryClient } from "@tanstack/react-query";
import { SESSION_KEY } from "@/components/session/useSession";

/**
 * À appeler après toute écriture sur un compte : liste et fiches des employés, mécaniciens
 * proposés à l'affectation d'un OT, tableau de bord (mécaniciens actifs, « Compte à
 * valider ») et session (le gérant peut modifier son propre nom).
 */
export function rafraichirApresCompte(queryClient: QueryClient): Promise<void> {
  return Promise.all([
    queryClient.invalidateQueries({ queryKey: ["utilisateurs"] }),
    queryClient.invalidateQueries({ queryKey: ["mecaniciens"] }),
    queryClient.invalidateQueries({ queryKey: ["tableau-de-bord"] }),
    queryClient.invalidateQueries({ queryKey: SESSION_KEY }),
  ]).then(() => undefined);
}

// Fiche qui vient d'être créée (« Nouvel employé ») : son titre reçoit le focus à l'arrivée,
// sinon il reste sur <body> après la navigation (revue du sprint 5).
let ficheCreee: number | null = null;

export function annoncerFicheCreee(id: number): void {
  ficheCreee = id;
}

/** Vrai une seule fois pour la fiche annoncée par `annoncerFicheCreee`. */
export function prendreFicheCreee(id: number): boolean {
  if (ficheCreee !== id) return false;
  ficheCreee = null;
  return true;
}
