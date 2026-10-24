"use client";

import { useMutation, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { useSession } from "@/components/session/useSession";
import { useToast } from "@/components/ui/Toast";
import { apiFetch } from "@/lib/api";
import { basculerTache, type OrdreDetail } from "@/lib/ordres";
import { LIBELLE_OT, type StatutOT } from "@/lib/statuts";
import { cleOrdre } from "./donnees";

/**
 * À appeler après toute écriture sur un OT (création, modification, statut, tâche) : recharge
 * toutes les vues qui l'affichent ailleurs que sur sa fiche (mise à jour par l'appelant avec la
 * réponse de l'API) — listes, kanban, « Mes travaux », planning et « Ensuite sur ce pont »,
 * rendez-vous à venir, fiche et historique du véhicule (kilométrage, interventions), tableau
 * de bord du gérant (indicateurs, interventions du jour, « À traiter »).
 */
export function rafraichirApresOrdre(queryClient: QueryClient): Promise<void> {
  return Promise.all([
    queryClient.invalidateQueries({ queryKey: ["ordres"], predicate: (q) => q.queryKey[1] !== "fiche" }),
    queryClient.invalidateQueries({ queryKey: ["planning"] }),
    queryClient.invalidateQueries({ queryKey: ["rendez-vous"] }),
    queryClient.invalidateQueries({ queryKey: ["vehicules"] }),
    queryClient.invalidateQueries({ queryKey: ["tableau-de-bord"] }),
  ]).then(() => undefined);
}

export function changerStatut(ordreId: number, nouveau: StatutOT) {
  return apiFetch<OrdreDetail>(`/ordres/${ordreId}/statut`, { method: "POST", body: { nouveau } });
}

export function messageStatut(ordre: Pick<OrdreDetail, "numero" | "statut">): string {
  return `${ordre.numero} : « ${LIBELLE_OT[ordre.statut]} ».`;
}

/** Fait avancer un OT d'une étape ; la fiche est mise à jour avec la réponse, les listes rechargées. */
export function useChangerStatut(options: { onSucces?: (ordre: OrdreDetail) => void } = {}) {
  const queryClient = useQueryClient();
  const notifier = useToast();
  return useMutation({
    mutationFn: ({ ordreId, nouveau }: { ordreId: number; nouveau: StatutOT }) => changerStatut(ordreId, nouveau),
    onSuccess: (ordre) => {
      queryClient.setQueryData(cleOrdre(ordre.id), ordre);
      notifier({ type: "success", message: messageStatut(ordre) });
      options.onSucces?.(ordre);
    },
    onError: (erreur) => notifier({ type: "error", message: erreur.message }),
    onSettled: () => rafraichirApresOrdre(queryClient),
  });
}

/** Coche ou décoche une tâche : mise à jour optimiste, annulée si l'API refuse. */
export function useBasculerTache(ordreId: number) {
  const queryClient = useQueryClient();
  const notifier = useToast();
  const { utilisateur } = useSession();
  const cle = cleOrdre(ordreId);
  return useMutation({
    mutationFn: ({ tacheId, terminee }: { tacheId: number; terminee: boolean }) =>
      apiFetch<OrdreDetail>(`/ordres/${ordreId}/taches/${tacheId}/${terminee ? "terminer" : "rouvrir"}`, { method: "POST" }),
    onMutate: async ({ tacheId, terminee }) => {
      await queryClient.cancelQueries({ queryKey: cle });
      const avant = queryClient.getQueryData<OrdreDetail>(cle);
      if (avant) {
        queryClient.setQueryData(cle, basculerTache(avant, tacheId, terminee, utilisateur ? { id: utilisateur.id, nom: utilisateur.nom } : null));
      }
      return { avant };
    },
    onError: (erreur, _variables, contexte) => {
      if (contexte?.avant) queryClient.setQueryData(cle, contexte.avant);
      notifier({ type: "error", message: erreur.message });
    },
    onSuccess: (ordre) => queryClient.setQueryData(cle, ordre),
    onSettled: () => rafraichirApresOrdre(queryClient),
  });
}
