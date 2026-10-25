"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { Icon } from "@/components/ui/Icon";
import { useDeconnexion, useSession } from "@/components/session/useSession";
import { LIBELLE_ROLE } from "@/lib/session";
import { Sidebar } from "./Sidebar";

/** Vue tablette atelier (/ordres/12/tablette) : pleine largeur, sans barre latérale. */
export function estVueTablette(pathname: string): boolean {
  return /^\/ordres\/\d+\/tablette\/?$/.test(pathname);
}

/** Coquille des pages connectées : menu selon le rôle réel, nom de l'employé et déconnexion. */
export function AppShell({ children }: { children: ReactNode }) {
  const { utilisateur, isError } = useSession();
  const deconnexion = useDeconnexion();
  const pathname = usePathname();

  if (!utilisateur) {
    return (
      <main className="center-page" id="contenu">
        <p className="muted" role="status">
          {isError ? "Session indisponible. Rechargez la page." : "Chargement de votre session…"}
        </p>
      </main>
    );
  }

  if (estVueTablette(pathname)) {
    // Tablette accrochée près du pont, lue à un mètre : tout l'écran pour l'intervention.
    return (
      <main id="contenu" className="tablette" tabIndex={-1}>
        {children}
      </main>
    );
  }

  const pied = (
    <>
      <div className="who">
        <strong>{utilisateur.nom_affiche}</strong>
        {LIBELLE_ROLE[utilisateur.role]}
      </div>
      <button
        type="button"
        className="et-btn"
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
