"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { useSession } from "@/components/session/useSession";
import { ChampRechercheListe } from "@/components/ui/ChampRechercheListe";
import { Pagination } from "@/components/ui/Pagination";
import { Plate } from "@/components/ui/Plate";
import { ApiError, apiFetch } from "@/lib/api";
import type { Page } from "@/lib/clients";
import { formatKm, nomComplet } from "@/lib/format";
import { aucunResultat, lienListe } from "@/lib/pages";
import type { Vehicule } from "@/lib/vehicules";

export const TAILLE_VEHICULES = 20;

export const lienVehicules = (q: string, page = 1) => lienListe("/vehicules", { q, page });

/** Message de liste vide : recherche sans résultat ou parc encore vide. */
export function messageAucunVehicule(q: string): string {
  return q ? aucunResultat("Aucun véhicule", q) : "Aucun véhicule pour l'instant : le véhicule se rattache depuis la fiche d'un client.";
}

/**
 * Liste des véhicules (story S1.5), pour le gérant (onglet de « Clients & véhicules ») et le
 * mécanicien (entrée « Véhicules » du menu). Recherche par plaque (avec ou sans tirets),
 * marque, modèle, VIN ou nom du propriétaire, jamais par ses coordonnées ; le propriétaire
 * n'est montré que par son nom, avec un lien vers sa fiche pour le gérant seul.
 */
export function VehiculesListe({ page, q: qInitial }: { page: number; q: string }) {
  const { utilisateur } = useSession();
  const [q, setQ] = useState(qInitial);
  // Une nouvelle recherche repart de la page 1.
  const [pageCourante, setPage] = useState(page);
  const parametres = new URLSearchParams({ page: String(pageCourante), taille: String(TAILLE_VEHICULES) });
  if (q) parametres.set("q", q);
  const { data, isPending, isError, error } = useQuery({
    queryKey: ["vehicules", "liste", q, pageCourante],
    queryFn: ({ signal }) => apiFetch<Page<Vehicule>>(`/vehicules?${parametres.toString()}`, { signal }),
    placeholderData: keepPreviousData,
  });
  const erreurRecherche = isError && error instanceof ApiError && error.status === 422 ? (error.champs.q ?? error.message) : null;

  function rechercher(saisie: string) {
    setQ(saisie);
    setPage(1);
    window.history.replaceState(null, "", lienVehicules(saisie));
  }

  return (
    <div className="stack">
      <ChampRechercheListe
        libelle="Rechercher un véhicule"
        placeholder="Plaque, marque, modèle, VIN ou propriétaire"
        valeurInitiale={qInitial}
        onRecherche={rechercher}
        total={data && q ? data.total : null}
        erreurServeur={erreurRecherche}
        className="recherche-liste"
      />
      <section className="panel" aria-labelledby="titre-liste-vehicules">
        <h2 id="titre-liste-vehicules" className="sr-only">
          Liste des véhicules
        </h2>
        {isPending ? (
          <p className="empty" role="status">
            Chargement des véhicules…
          </p>
        ) : isError && !erreurRecherche ? (
          <p className="empty danger-text" role="alert">
            {error.message}
          </p>
        ) : !data || data.elements.length === 0 ? (
          <p className="empty">{messageAucunVehicule(q)}</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Plaque</th>
                  <th scope="col">Véhicule</th>
                  <th scope="col">Propriétaire</th>
                  <th scope="col" className="right">
                    Kilométrage
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.elements.map((vehicule) => (
                  <tr key={vehicule.id}>
                    <td className="nowrap">
                      <Link href={`/vehicules/${vehicule.id}`} className="table-link" aria-label={`Fiche du véhicule ${vehicule.immatriculation}`}>
                        <Plate number={vehicule.immatriculation} size="sm" />
                      </Link>
                    </td>
                    <td>
                      {vehicule.marque} {vehicule.modele}
                      {vehicule.vin ? <span className="caption mono cellule-vin">{vehicule.vin}</span> : null}
                    </td>
                    <td>
                      {utilisateur?.role === "gerant" ? (
                        <Link href={`/clients/${vehicule.proprietaire.id}`} className="table-link">
                          {nomComplet(vehicule.proprietaire)}
                        </Link>
                      ) : (
                        nomComplet(vehicule.proprietaire)
                      )}
                    </td>
                    <td className="right num nowrap">{formatKm(vehicule.kilometrage)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      {data && data.total > 0 ? (
        <Pagination page={pageCourante} taille={TAILLE_VEHICULES} total={data.total} libelle={data.total > 1 ? "véhicules" : "véhicule"} lien={(p) => lienVehicules(q, p)} />
      ) : null}
    </div>
  );
}
