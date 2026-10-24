"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useSession } from "@/components/session/useSession";
import { useToast } from "@/components/ui/Toast";
import { apiFetch } from "@/lib/api";
import { basculerTache, type OrdreDetail } from "@/lib/ordres";
import { LIBELLE_OT, type StatutOT } from "@/lib/statuts";
import { cleOrdre } from "./donnees";

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
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["ordres"], predicate: (q) => q.queryKey[1] !== "fiche" }),
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
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["ordres"], predicate: (q) => q.queryKey[1] !== "fiche" }),
  });
}
