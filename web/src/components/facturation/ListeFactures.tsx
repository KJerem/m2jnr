"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { Pagination } from "@/components/ui/Pagination";
import { Plate } from "@/components/ui/Plate";
import { apiFetch } from "@/lib/api";
import type { Page } from "@/lib/clients";
import { formatEmission, libelleTelechargement, lienPdf, type FactureResume } from "@/lib/factures";
import { formatEuros, nomComplet } from "@/lib/format";
import { modele } from "@/lib/ordres";
import { TAILLE_LISTE } from "./ListeDevis";

/** Onglet « Factures » : de la plus récente à la plus ancienne, avec le PDF de chacune. */
export function ListeFactures({ page }: { page: number }) {
  const { data, isPending, isError, error } = useQuery({
    queryKey: ["factures", "liste", page],
    queryFn: ({ signal }) => apiFetch<Page<FactureResume>>(`/factures?page=${page}&taille=${TAILLE_LISTE}`, { signal }),
  });

  if (isPending) {
    return (
      <p className="panel empty" role="status">
        Chargement des factures…
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
    return <p className="panel empty">Aucune facture pour l&apos;instant : elle s&apos;établit depuis le devis d&apos;une intervention terminée.</p>;
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
                <th scope="col">
                  <span className="sr-only">Téléchargement</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {data.elements.map((facture) => (
                <tr key={facture.id}>
                  <td>
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
      <Pagination page={page} taille={TAILLE_LISTE} total={data.total} libelle={data.total > 1 ? "factures" : "facture"} lien={(p) => `/factures?page=${p}`} />
    </div>
  );
}
