"use client";

import type { ReactNode } from "react";
import { useSession } from "@/components/session/useSession";

/** Coquille de la vue tablette : pleine largeur, sans barre latérale (tablette près du pont). */
export function ShellTablette({ children }: { children: ReactNode }) {
  const { utilisateur, isError } = useSession();
  if (!utilisateur) {
    return (
      <main className="center-page" id="contenu">
        <p className="muted" role="status">
          {isError ? "Session indisponible. Rechargez la page." : "Chargement de votre session…"}
        </p>
      </main>
    );
  }
  return (
    <main id="contenu" className="tablette" tabIndex={-1}>
      {children}
    </main>
  );
}
