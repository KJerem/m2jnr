"use client";

import { ClientsVehicules } from "@/components/clients/ClientsVehicules";
import { useSession } from "@/components/session/useSession";
import { VehiculesListe } from "./VehiculesListe";

/**
 * /vehicules (story S1.5) : pour le gérant, l'onglet « Véhicules » de « Clients & véhicules » ;
 * pour le mécanicien, la même liste seule, sans fiche client ni coordonnées.
 */
export function PageVehicules({ page, q }: { page: number; q: string }) {
  const { utilisateur } = useSession();
  if (!utilisateur) return null;
  if (utilisateur.role === "gerant") return <ClientsVehicules onglet="vehicules" page={page} q={q} />;
  return (
    <>
      <header className="page-head">
        <div>
          <h1 className="display">Véhicules</h1>
          <p className="caption sub">Véhicules suivis par l&apos;atelier, avec leur fiche et leur historique.</p>
        </div>
      </header>
      <VehiculesListe page={page} q={q} />
    </>
  );
}
