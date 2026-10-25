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
