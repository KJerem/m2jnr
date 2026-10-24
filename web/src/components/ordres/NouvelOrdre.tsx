"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { ordreVide, type OrdreDetail, type OrdreEntree } from "@/lib/ordres";
import { useMecaniciens, useVehicules } from "./donnees";
import { OrdreForm } from "./OrdreForm";

export function creerOrdre(entree: OrdreEntree) {
  return apiFetch<OrdreDetail>("/ordres", { method: "POST", body: entree });
}

/** Ouverture d'un OT ; ?vehicule_id= présélectionne le véhicule (bouton de la fiche véhicule). */
export function NouvelOrdre({ vehiculeId }: { vehiculeId: number | null }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const vehicules = useVehicules();
  const mecaniciens = useMecaniciens();

  const erreur = vehicules.error ?? mecaniciens.error;
  return (
    <>
      <header className="page-head">
        <div>
          <p className="breadcrumb">
            <Link href="/ordres">Ordres de travail</Link> / Nouveau
          </p>
          <h1 className="display">Nouvel ordre de travail</h1>
        </div>
      </header>
      <section className="panel">
        <div className="panel-body">
          {erreur ? (
            <p className="callout callout-danger" role="alert">
              {erreur.message}
            </p>
          ) : !vehicules.data || !mecaniciens.data ? (
            <p className="muted" role="status">
              Chargement du formulaire…
            </p>
          ) : (
            <OrdreForm
              mode="creation"
              valeursInitiales={ordreVide(vehicules.data.some((v) => v.id === vehiculeId) ? vehiculeId : null)}
              vehicules={vehicules.data}
              mecaniciens={mecaniciens.data}
              envoyer={creerOrdre}
              onSucces={(ordre) => {
                void queryClient.invalidateQueries({ queryKey: ["ordres"] });
                void queryClient.invalidateQueries({ queryKey: ["vehicules"] });
                router.push(`/ordres/${ordre.id}`);
              }}
              onAnnuler={() => router.back()}
            />
          )}
        </div>
      </section>
    </>
  );
}
