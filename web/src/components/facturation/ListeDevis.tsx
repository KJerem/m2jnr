"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { Pagination } from "@/components/ui/Pagination";
import { Plate } from "@/components/ui/Plate";
import { apiFetch } from "@/lib/api";
import type { Page } from "@/lib/clients";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { BADGE_DEVIS, LIBELLE_DEVIS, type DevisResume } from "@/lib/devis";
import { formatDateCourteOuAnnee, formatEuros, nomComplet } from "@/lib/format";
import { modele } from "@/lib/ordres";

export const TAILLE_LISTE = 50;

/** Onglet « Devis » : numéro d'OT, véhicule, client, statut, total TTC, date (avec l'année si ce n'est pas l'année en cours). */
export function ListeDevis({ page }: { page: number }) {
  const { data, isPending, isError, error } = useQuery({
    queryKey: ["devis", "liste", page],
    queryFn: ({ signal }) => apiFetch<Page<DevisResume>>(`/devis?page=${page}&taille=${TAILLE_LISTE}`, { signal }),
  });

  if (isPending) {
    return (
      <p className="panel empty" role="status">
        Chargement des devis…
      </p>
    );
  }
  if (isError) {
    return (
      <p className="panel empty danger-text" role="alert">
        {error.message}
      </p>
    );
  }
  if (data.elements.length === 0) {
    return <p className="panel empty">Aucun devis pour l&apos;instant : le devis se rédige depuis la fiche d&apos;un ordre de travail.</p>;
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
      <Pagination page={page} taille={TAILLE_LISTE} total={data.total} libelle="devis" lien={(p) => `/devis?page=${p}`} />
    </div>
  );
}
