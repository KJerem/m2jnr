"use client";

import type { ReactNode } from "react";
import { Icon } from "@/components/ui/Icon";
import { useDeconnexion, useSession } from "@/components/session/useSession";
import { LIBELLE_ROLE } from "@/lib/session";
import { Sidebar } from "./Sidebar";

/** Coquille des pages connectées : menu selon le rôle réel, nom de l'employé et déconnexion. */
export function AppShell({ children }: { children: ReactNode }) {
  const { utilisateur, isError } = useSession();
  const deconnexion = useDeconnexion();

  if (!utilisateur) {
    return (
      <main className="center-page" id="contenu">
        <p className="muted" role="status">
          {isError ? "Session indisponible. Rechargez la page." : "Chargement de votre session…"}
        </p>
      </main>
    );
  }

  const pied = (
    <>
      <div className="who">
        <strong>{utilisateur.nom}</strong>
        {LIBELLE_ROLE[utilisateur.role]}
      </div>
      <button
        type="button"
        className="et-btn et-btn-sm"
        onClick={() => deconnexion.mutate()}
        disabled={deconnexion.isPending}
        aria-label="Se déconnecter"
        title="Se déconnecter"
      >
        <Icon name="logout" />
        <span className="sidebar-label">Se déconnecter</span>
      </button>
    </>
  );

  return (
    <>
      <a href="#contenu" className="skip-link">
        Aller au contenu
      </a>
      <div className="shell">
        <Sidebar role={utilisateur.role} garageName="Garage Établi" footer={pied} />
        <main id="contenu" className="main" tabIndex={-1}>
          {children}
        </main>
      </div>
    </>
  );
}
