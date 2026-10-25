"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { ChampRechercheListe } from "@/components/ui/ChampRechercheListe";
import { Pagination } from "@/components/ui/Pagination";
import { ApiError, apiFetch } from "@/lib/api";
import type { Client, Page } from "@/lib/clients";
import { formatTelephone } from "@/lib/format";
import { aucunResultat, lienListe } from "@/lib/pages";

export const TAILLE_CLIENTS = 20;

export const lienClients = (q: string, page = 1) => lienListe("/clients", { q, page });

/** Message de liste vide : recherche sans résultat, page vide ou fichier encore vide. */
export function messageAucunClient(q: string, total: number): string {
  if (q) return aucunResultat("Aucun client", q);
  return total === 0 ? "Aucun client pour l'instant. Créez la première fiche." : "Aucun client sur cette page.";
}

/**
 * Onglet « Clients » de « Clients & véhicules » (gérant) : recherche par nom, prénom,
 * téléphone même partiel, plaque d'un véhicule ou e-mail (story S1.5), gardée dans l'adresse
 * (?q=) ; une nouvelle recherche repart de la page 1.
 */
export function ClientsListe({ page, q: qInitial }: { page: number; q: string }) {
  const [q, setQ] = useState(qInitial);
  const [pageCourante, setPage] = useState(page);
  const parametres = new URLSearchParams({ page: String(pageCourante), taille: String(TAILLE_CLIENTS) });
  if (q) parametres.set("q", q);
  const { data, isPending, isError, error } = useQuery({
    queryKey: ["clients", "liste", q, pageCourante],
    queryFn: ({ signal }) => apiFetch<Page<Client>>(`/clients?${parametres.toString()}`, { signal }),
    placeholderData: keepPreviousData,
  });
  const erreurRecherche = isError && error instanceof ApiError && error.status === 422 ? (error.champs.q ?? error.message) : null;

  function rechercher(saisie: string) {
    setQ(saisie);
    setPage(1);
    window.history.replaceState(null, "", lienClients(saisie));
  }

  return (
    <div className="stack">
      <ChampRechercheListe
        libelle="Rechercher un client"
        placeholder="Nom, téléphone, plaque ou e-mail"
        valeurInitiale={qInitial}
        onRecherche={rechercher}
        total={data && q ? data.total : null}
        erreurServeur={erreurRecherche}
        className="recherche-liste"
      />
      <section className="panel" aria-labelledby="titre-liste-clients">
        <h2 id="titre-liste-clients" className="sr-only">
          Liste des clients
        </h2>
        {isPending ? (
          <p className="empty" role="status">
            Chargement des clients…
          </p>
        ) : isError && !erreurRecherche ? (
          <p className="empty danger-text" role="alert">
            {error.message}
          </p>
        ) : !data || data.elements.length === 0 ? (
          <p className="empty">{messageAucunClient(q, data?.total ?? 0)}</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Nom</th>
                  <th scope="col">Téléphone</th>
                  <th scope="col">E-mail</th>
                  <th scope="col" className="right">
                    Véhicules
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.elements.map((client) => (
                  <tr key={client.id}>
                    <td>
                      <Link href={`/clients/${client.id}`} className="table-link">
                        <strong>{client.nom}</strong>
                        {client.prenom ? ` ${client.prenom}` : null}
                      </Link>
                    </td>
                    <td className="num">{formatTelephone(client.telephone)}</td>
                    <td className="cellule-email">{client.email ?? <span className="muted">—</span>}</td>
                    <td className="right num">{client.nombre_vehicules}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      {data && data.total > 0 ? (
        <Pagination page={pageCourante} taille={TAILLE_CLIENTS} total={data.total} libelle={data.total > 1 ? "clients" : "client"} lien={(p) => lienClients(q, p)} />
      ) : null}
    </div>
  );
}
