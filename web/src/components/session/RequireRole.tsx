"use client";

import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import type { Role } from "@/lib/session";
import { useSession } from "./useSession";

/**
 * Garde d'affichage pour les pages réservées à certains rôles : un mécanicien qui ouvre une page
 * de gérant est envoyé sur /403. C'est un confort d'interface ; la vraie barrière reste l'API (403).
 */
export function RequireRole({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const { utilisateur } = useSession();
  const router = useRouter();
  const autorise = utilisateur ? roles.includes(utilisateur.role) : null;

  useEffect(() => {
    if (autorise === false) router.replace("/403");
  }, [autorise, router]);

  if (!autorise) return null;
  return <>{children}</>;
}
