"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { ChampRechercheListe } from "@/components/ui/ChampRechercheListe";
import { Pagination } from "@/components/ui/Pagination";
import { Plate } from "@/components/ui/Plate";
import { ApiError, apiFetch } from "@/lib/api";
import type { Page } from "@/lib/clients";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { BADGE_DEVIS, LIBELLE_DEVIS, type DevisResume } from "@/lib/devis";
import { formatDateCourteOuAnnee, formatEuros, nomComplet } from "@/lib/format";
import { modele } from "@/lib/ordres";
import { useFiltresAdresse } from "@/lib/adresse";
import { aucunResultat, lienListe, numeroDePage, texteDeRecherche, type Recherche } from "@/lib/pages";

export const TAILLE_LISTE = 50;

export const lienDevis = (q: string, page = 1) => lienListe("/devis", { q, page });

interface FiltresDevis {
  q: string;
  page: number;
}

const lireDevis = (p: Recherche): FiltresDevis => ({ q: texteDeRecherche(p.q), page: numeroDePage(p.page) });

/**
 * Onglet « Devis » : numéro d'OT, véhicule, client, statut, total TTC, date (avec l'année si
 * ce n'est pas l'année en cours). Recherche par numéro d'OT, plaque ou client (story S1.5),
 * gardée dans l'adresse (?q=), retour arrière compris.
 */
export function ListeDevis({ page, q: qInitial = "" }: { page: number; q?: string }) {
  const [filtres, changer] = useFiltresAdresse("/devis", { q: qInitial, page }, lireDevis, (f) => lienDevis(f.q, f.page));
  const { q, page: pageCourante } = filtres;
  const parametres = new URLSearchParams({ page: String(pageCourante), taille: String(TAILLE_LISTE) });
  if (q) parametres.set("q", q);
  const { data, isPending, isError, error } = useQuery({
    queryKey: ["devis", "liste", q, pageCourante],
    queryFn: ({ signal }) => apiFetch<Page<DevisResume>>(`/devis?${parametres.toString()}`, { signal }),
    placeholderData: keepPreviousData,
  });
  const erreurRecherche = isError && error instanceof ApiError && error.status === 422 ? (error.champs.q ?? error.message) : null;

  function rechercher(saisie: string) {
    changer({ q: saisie, page: 1 });
  }

  return (
    <div className="stack">
      <ChampRechercheListe
        libelle="Rechercher un devis"
        placeholder="N° d'OT, plaque ou client"
        valeurInitiale={q}
        onRecherche={rechercher}
        total={data && q ? data.total : null}
        erreurServeur={erreurRecherche}
        className="recherche-liste"
      />
      <Contenu data={data} isPending={isPending} erreur={isError && !erreurRecherche ? error.message : null} q={q} page={pageCourante} />
    </div>
  );
}

interface ContenuProps {
  data: Page<DevisResume> | undefined;
  isPending: boolean;
  erreur: string | null;
  q: string;
  page: number;
}

function Contenu({ data, isPending, erreur, q, page }: ContenuProps) {
  if (isPending) {
    return (
      <p className="panel empty" role="status">
        Chargement des devis…
      </p>
    );
  }
  if (erreur !== null) {
    return (
      <p className="panel empty danger-text" role="alert">
        {erreur}
      </p>
    );
  }
  if (!data || data.elements.length === 0) {
    return q ? (
      <p className="panel empty">{aucunResultat("Aucun devis", q)}</p>
    ) : (
      <p className="panel empty">Aucun devis pour l&apos;instant : le devis se rédige depuis la fiche d&apos;un ordre de travail.</p>
    );
  }
  return (
    <div className="stack">
      <section className="panel" aria-label="Liste des devis">
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">N° OT</th>
                <th scope="col">Véhicule</th>
                <th scope="col">Client</th>
                <th scope="col">Statut</th>
                <th scope="col" className="right">
                  Total TTC
                </th>
                <th scope="col">Date</th>
                <th scope="col">Facture</th>
              </tr>
            </thead>
            <tbody>
              {data.elements.map((devis) => (
                <tr key={devis.id}>
                  <td className="nowrap">
                    <Link href={`/ordres/${devis.ordre.id}`} className="table-link mono">
                      {devis.ordre.numero}
                    </Link>
                  </td>
                  <td>
                    <span className="cellule-empilee">
                      <Plate number={devis.vehicule.immatriculation} size="sm" />
                      <span>{modele(devis.vehicule)}</span>
                    </span>
                  </td>
                  <td>{nomComplet(devis.client)}</td>
                  <td>
                    <StatusBadge status={BADGE_DEVIS[devis.statut]}>{LIBELLE_DEVIS[devis.statut]}</StatusBadge>
                  </td>
                  <td className="right num nowrap strong">{formatEuros(devis.total_ttc_centimes)}</td>
                  <td className="nowrap">{formatDateCourteOuAnnee(devis.modifie_le)}</td>
                  <td className="nowrap">
                    {devis.facture ? (
                      <Link href={`/factures/${devis.facture.id}`} className="table-link mono">
                        {devis.facture.numero}
                      </Link>
                    ) : (
                      <span className="muted">Non facturé</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <Pagination page={page} taille={TAILLE_LISTE} total={data.total} libelle="devis" lien={(p) => lienDevis(q, p)} />
    </div>
  );
}
