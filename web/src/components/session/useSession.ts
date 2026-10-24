"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { PAGE_CONNEXION, type SessionReponse } from "@/lib/session";

export const SESSION_KEY = ["session"] as const;

/** Session courante lue sur /api/auth/me ; un 401 renvoie vers la page de connexion. */
export function useSession() {
  const query = useQuery({
    queryKey: SESSION_KEY,
    queryFn: ({ signal }) => apiFetch<SessionReponse>("/auth/me", { signal }),
    staleTime: 5 * 60_000,
  });
  return { ...query, utilisateur: query.data?.utilisateur ?? null };
}

/**
 * Déconnexion : on quitte d'abord les pages connectées, le cache est vidé à l'arrivée sur
 * /connexion (voir LoginForm). Vider le cache ici relancerait les requêtes encore affichées,
 * dont /auth/me : le 401 renverrait vers /connexion?suivant=<page quittée>, et la personne
 * suivante atterrirait sur la page de l'utilisateur précédent.
 */
export function useDeconnexion() {
  const router = useRouter();
  return useMutation({
    mutationFn: () => apiFetch<void>("/auth/logout", { method: "POST", redirigerSi401: false }),
    onSettled: () => {
      router.replace(PAGE_CONNEXION);
    },
  });
}
