"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { ChampRechercheListe } from "@/components/ui/ChampRechercheListe";
import { Pagination } from "@/components/ui/Pagination";
import { Plate } from "@/components/ui/Plate";
import { ApiError, apiFetch } from "@/lib/api";
import type { Page } from "@/lib/clients";
import { FILTRES_PAIEMENT, formatEmission, libelleTelechargement, lienFactures, lienPdf, type FactureResume, type StatutPaiement } from "@/lib/factures";
import { formatEuros, nomComplet } from "@/lib/format";
import { modele } from "@/lib/ordres";
import { aucunResultat } from "@/lib/pages";
import { TAILLE_LISTE } from "./ListeDevis";
import { BadgesPaiement } from "./PaiementsFacture";

type Filtre = StatutPaiement | "toutes";

/**
 * Onglet « Factures » : de la plus récente à la plus ancienne, avec le PDF de chacune, le
 * statut de paiement et le reste à payer (story S4.4). Les filtres (Toutes, Impayées,
 * Partielles, Payées) sont des boutons à bascule ; la recherche (numéro de facture ou d'OT,
 * client ou plaque figés sur la facture, story S1.5) s'y ajoute. Filtre et recherche suivent
 * l'adresse (?paiement=…&q=…) sans recharger la page, et le focus reste où il était.
 */
export function ListeFactures({ page, paiement = "toutes", q: qInitial = "" }: { page: number; paiement?: Filtre; q?: string }) {
  const [filtre, setFiltre] = useState<Filtre>(paiement);
  const [q, setQ] = useState(qInitial);
  const [pageCourante, setPage] = useState(page);
  const parametres = new URLSearchParams({ page: String(pageCourante), taille: String(TAILLE_LISTE) });
  if (filtre !== "toutes") parametres.set("statut_paiement", filtre);
  if (q) parametres.set("q", q);
  const { data, isPending, isError, error } = useQuery({
    queryKey: ["factures", "liste", filtre, q, pageCourante],
    queryFn: ({ signal }) => apiFetch<Page<FactureResume>>(`/factures?${parametres.toString()}`, { signal }),
    placeholderData: keepPreviousData,
  });
  const erreurRecherche = isError && error instanceof ApiError && error.status === 422 ? (error.champs.q ?? error.message) : null;

  function changer(suivant: Filtre) {
    setFiltre(suivant);
    setPage(1);
    window.history.replaceState(null, "", lienFactures(suivant, 1, q));
  }

  function rechercher(saisie: string) {
    setQ(saisie);
    setPage(1);
    window.history.replaceState(null, "", lienFactures(filtre, 1, saisie));
  }

  return (
    <div className="stack">
      <div className="liste-filtres">
        <ChampRechercheListe
          libelle="Rechercher une facture"
          placeholder="N° de facture ou d'OT, client, plaque"
          valeurInitiale={qInitial}
          onRecherche={rechercher}
          total={data && q ? data.total : null}
          erreurServeur={erreurRecherche}
          className="recherche-liste"
        />
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
      </div>
      <Contenu data={data} isPending={isPending} erreur={isError && !erreurRecherche ? error.message : null} filtre={filtre} q={q} page={pageCourante} />
    </div>
  );
}

interface ContenuProps {
  data: Page<FactureResume> | undefined;
  isPending: boolean;
  erreur: string | null;
  filtre: Filtre;
  q: string;
  page: number;
}

function Contenu({ data, isPending, erreur, filtre, q, page }: ContenuProps) {
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
    if (q) return <p className="panel empty">{aucunResultat("Aucune facture", q)}</p>;
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
                <th scope="col" className="th-replie">
                  Numéro · <span className="nowrap">émise le</span>
                </th>
                <th scope="col">Client</th>
                <th scope="col">Véhicule</th>
                <th scope="col" className="right">
                  Total TTC
                </th>
                <th scope="col">Paiement</th>
                <th scope="col" className="right th-replie">
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
                    <span className="cellule-empilee">
                      <Link href={`/factures/${facture.id}`} className="table-link mono">
                        {facture.numero}
                      </Link>
                      <span className="caption">{formatEmission(facture.emise_le)}</span>
                    </span>
                  </td>
                  <td>{nomComplet(facture.client)}</td>
                  <td>
                    <span className="cellule-empilee">
                      <Plate number={facture.vehicule.immatriculation} size="sm" />
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
      <Pagination page={page} taille={TAILLE_LISTE} total={data.total} libelle={data.total > 1 ? "factures" : "facture"} lien={(p) => lienFactures(filtre, p, q)} />
    </div>
  );
}
