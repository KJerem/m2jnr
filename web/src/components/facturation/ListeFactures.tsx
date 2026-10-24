"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { Pagination } from "@/components/ui/Pagination";
import { Plate } from "@/components/ui/Plate";
import { apiFetch } from "@/lib/api";
import type { Page } from "@/lib/clients";
import { FILTRES_PAIEMENT, formatEmission, libelleTelechargement, lienFactures, lienPdf, type FactureResume, type StatutPaiement } from "@/lib/factures";
import { formatEuros, nomComplet } from "@/lib/format";
import { modele } from "@/lib/ordres";
import { TAILLE_LISTE } from "./ListeDevis";
import { BadgesPaiement } from "./PaiementsFacture";

type Filtre = StatutPaiement | "toutes";

/**
 * Onglet « Factures » : de la plus récente à la plus ancienne, avec le PDF de chacune, le
 * statut de paiement et le reste à payer (story S4.4). Les filtres (Toutes, Impayées,
 * Partielles, Payées) sont des boutons à bascule ; le filtre suit l'adresse (?paiement=…)
 * sans recharger la page, et le focus reste sur le bouton.
 */
export function ListeFactures({ page, paiement = "toutes" }: { page: number; paiement?: Filtre }) {
  const [filtre, setFiltre] = useState<Filtre>(paiement);
  // La page demandée ne vaut que pour le filtre ouvert par l'adresse.
  const pageCourante = filtre === paiement ? page : 1;
  const parametre = filtre === "toutes" ? "" : `&statut_paiement=${filtre}`;
  const { data, isPending, isError, error } = useQuery({
    queryKey: ["factures", "liste", filtre, pageCourante],
    queryFn: ({ signal }) => apiFetch<Page<FactureResume>>(`/factures?page=${pageCourante}&taille=${TAILLE_LISTE}${parametre}`, { signal }),
  });

  function changer(suivant: Filtre) {
    setFiltre(suivant);
    window.history.replaceState(null, "", lienFactures(suivant));
  }

  return (
    <div className="stack">
      <div className="factures-filtres">
        <div className="chips" role="group" aria-label="Filtrer par statut de paiement">
          {FILTRES_PAIEMENT.map((f) => (
            <button key={f.id} type="button" className="chip" aria-pressed={filtre === f.id} onClick={() => changer(f.id)}>
              {f.libelle}
            </button>
          ))}
        </div>
        <p className="caption" role="status">
          {data ? `${data.total} facture${data.total > 1 ? "s" : ""}` : ""}
        </p>
      </div>
      <Contenu data={data} isPending={isPending} erreur={isError ? error.message : null} filtre={filtre} page={pageCourante} />
    </div>
  );
}

interface ContenuProps {
  data: Page<FactureResume> | undefined;
  isPending: boolean;
  erreur: string | null;
  filtre: Filtre;
  page: number;
}

function Contenu({ data, isPending, erreur, filtre, page }: ContenuProps) {
  if (isPending) {
    return (
      <p className="panel empty" role="status">
        Chargement des factures…
      </p>
    );
  }
  if (erreur !== null || !data) {
    return (
      <p className="panel empty danger-text" role="alert">
        {erreur}
      </p>
    );
  }
  if (data.elements.length === 0) {
    return filtre === "toutes" ? (
      <p className="panel empty">Aucune facture pour l&apos;instant : elle s&apos;établit depuis le devis d&apos;une intervention terminée.</p>
    ) : (
      <p className="panel empty">Aucune facture dans ce filtre.</p>
    );
  }
  return (
    <div className="stack">
      <section className="panel" aria-label="Liste des factures">
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">Numéro</th>
                <th scope="col">Émise le</th>
                <th scope="col">Client</th>
                <th scope="col">Véhicule</th>
                <th scope="col" className="right">
                  Total TTC
                </th>
                <th scope="col">Paiement</th>
                <th scope="col" className="right">
                  Reste à payer
                </th>
                <th scope="col">
                  <span className="sr-only">Téléchargement</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {data.elements.map((facture) => (
                <tr key={facture.id}>
                  <td className="nowrap">
                    <Link href={`/factures/${facture.id}`} className="table-link mono">
                      {facture.numero}
                    </Link>
                  </td>
                  <td className="nowrap">{formatEmission(facture.emise_le)}</td>
                  <td>{nomComplet(facture.client)}</td>
                  <td>
                    <span className="row nowrap">
                      <Plate number={facture.vehicule.immatriculation} />
                      <span>{modele(facture.vehicule)}</span>
                    </span>
                  </td>
                  <td className="right num nowrap strong">{formatEuros(facture.total_ttc_centimes)}</td>
                  <td>
                    <BadgesPaiement statut={facture.statut_paiement} enRetard={facture.en_retard} />
                  </td>
                  <td className="right num nowrap">{facture.reste_centimes === 0 ? <span className="muted">—</span> : formatEuros(facture.reste_centimes)}</td>
                  <td className="right">
                    <a className="et-btn et-btn-quiet" href={lienPdf(facture.id)} download aria-label={libelleTelechargement(facture.numero)}>
                      PDF
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <Pagination page={page} taille={TAILLE_LISTE} total={data.total} libelle={data.total > 1 ? "factures" : "facture"} lien={(p) => lienFactures(filtre, p)} />
    </div>
  );
}
