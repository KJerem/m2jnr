"use client";

import Link from "next/link";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { Plate } from "@/components/ui/Plate";
import { apiFetch } from "@/lib/api";
import { formatKm } from "@/lib/format";
import type { Vehicule, VehiculeEntree, VehiculeResume } from "@/lib/vehicules";
import { VehiculeForm } from "./VehiculeForm";

export interface VehiculesClientProps {
  clientId: number;
  vehicules: VehiculeResume[];
  onAjout: (vehicule: Vehicule) => void;
}

/** Véhicules d'un client, montrés par leur plaque, et ajout d'un véhicule rattaché. */
export function VehiculesClient({ clientId, vehicules, onAjout }: VehiculesClientProps) {
  const [ajout, setAjout] = useState(false);

  function ajouter(entree: VehiculeEntree) {
    return apiFetch<Vehicule>(`/clients/${clientId}/vehicules`, { method: "POST", body: entree });
  }

  return (
    <section className="panel" aria-labelledby="titre-vehicules">
      <div className="panel-head">
        <h2 id="titre-vehicules">Véhicules</h2>
        {!ajout ? (
          <Button onClick={() => setAjout(true)}>
            <Icon name="plus" />
            Ajouter un véhicule
          </Button>
        ) : null}
      </div>
      <div className="panel-body">
        {ajout ? (
          <div className="note stack">
            <h3>Nouveau véhicule</h3>
            <VehiculeForm
              mode="creation"
              envoyer={ajouter}
              onSucces={(vehicule) => {
                setAjout(false);
                onAjout(vehicule);
              }}
              onAnnuler={() => setAjout(false)}
            />
          </div>
        ) : null}
        {vehicules.length === 0 ? (
          <p className="muted">Aucun véhicule rattaché à ce client.</p>
        ) : (
          <ul className="vehicules">
            {vehicules.map((v) => (
              <li key={v.id}>
                <Link href={`/vehicules/${v.id}`} className="vehicule-ligne">
                  <Plate number={v.immatriculation} />
                  <span className="vehicule-modele">
                    {v.marque} {v.modele}
                  </span>
                  <span className="mono muted">{formatKm(v.kilometrage)}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
