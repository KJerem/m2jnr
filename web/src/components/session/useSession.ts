"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
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

export function useDeconnexion() {
  const client = useQueryClient();
  const router = useRouter();
  return useMutation({
    mutationFn: () => apiFetch<void>("/auth/logout", { method: "POST", redirigerSi401: false }),
    onSettled: () => {
      client.clear();
      router.replace(PAGE_CONNEXION);
    },
  });
}
