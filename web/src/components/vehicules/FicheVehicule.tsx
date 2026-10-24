"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { useSession } from "@/components/session/useSession";
import { Button } from "@/components/ui/Button";
import { Plate } from "@/components/ui/Plate";
import { apiFetch } from "@/lib/api";
import { formatDate, formatKm, nomComplet } from "@/lib/format";
import { versFormulaireVehicule, type Vehicule, type VehiculeEntree } from "@/lib/vehicules";
import { VehiculeForm } from "./VehiculeForm";

/** Fiche véhicule : lecture pour le mécanicien, modification pour le gérant. */
export function FicheVehicule({ vehiculeId }: { vehiculeId: number }) {
  const { utilisateur } = useSession();
  const gerant = utilisateur?.role === "gerant";
  const queryClient = useQueryClient();
  const [edition, setEdition] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const cle = ["vehicules", vehiculeId] as const;
  const { data: vehicule, isPending, isError, error } = useQuery({
    queryKey: cle,
    queryFn: ({ signal }) => apiFetch<Vehicule>(`/vehicules/${vehiculeId}`, { signal }),
  });

  if (isPending) {
    return (
      <p className="muted" role="status">
        Chargement de la fiche…
      </p>
    );
  }
  if (isError) {
    return (
      <p className="callout callout-danger" role="alert">
        {error.message}
      </p>
    );
  }

  function modifier(entree: VehiculeEntree) {
    return apiFetch<Vehicule>(`/vehicules/${vehiculeId}`, { method: "PUT", body: entree });
  }

  const proprietaire = nomComplet(vehicule.proprietaire);

  return (
    <>
      <header className="page-head">
        <div className="stack-sm">
          {gerant ? (
            <p className="breadcrumb">
              <Link href="/clients">Clients</Link> / <Link href={`/clients/${vehicule.proprietaire.id}`}>{proprietaire}</Link> / Véhicule
            </p>
          ) : (
            <p className="breadcrumb">Véhicule</p>
          )}
          <Plate number={vehicule.immatriculation} size="lg" />
          <h1 className="display">
            {vehicule.marque} {vehicule.modele}
          </h1>
        </div>
        {gerant && !edition ? (
          <Button
            onClick={() => {
              setMessage(null);
              setEdition(true);
            }}
          >
            Modifier
          </Button>
        ) : null}
      </header>

      <p role="status" className={message ? "callout callout-success" : undefined}>
        {message}
      </p>

      <section className="panel" aria-labelledby="titre-vehicule">
        <div className="panel-head">
          <h2 id="titre-vehicule">Caractéristiques</h2>
        </div>
        <div className="panel-body">
          {edition ? (
            <VehiculeForm
              mode="modification"
              valeursInitiales={versFormulaireVehicule(vehicule)}
              envoyer={modifier}
              onSucces={(maj) => {
                queryClient.setQueryData(cle, maj);
                void queryClient.invalidateQueries({ queryKey: ["clients"] });
                setEdition(false);
                setMessage("Véhicule enregistré.");
              }}
              onAnnuler={() => setEdition(false)}
            />
          ) : (
            <dl className="dl">
              <dt>Immatriculation</dt>
              <dd className="mono">{vehicule.immatriculation}</dd>
              <dt>Marque et modèle</dt>
              <dd>
                {vehicule.marque} {vehicule.modele}
              </dd>
              <dt>VIN</dt>
              <dd className="mono">{vehicule.vin ?? <span className="muted">Non renseigné</span>}</dd>
              <dt>Kilométrage</dt>
              <dd className="mono">{formatKm(vehicule.kilometrage)}</dd>
              <dt>Mise en circulation</dt>
              <dd>{vehicule.date_mise_en_circulation ? formatDate(vehicule.date_mise_en_circulation) : <span className="muted">Non renseignée</span>}</dd>
              <dt>Propriétaire</dt>
              <dd>{gerant ? <Link href={`/clients/${vehicule.proprietaire.id}`}>{proprietaire}</Link> : proprietaire}</dd>
            </dl>
          )}
        </div>
      </section>
    </>
  );
}
