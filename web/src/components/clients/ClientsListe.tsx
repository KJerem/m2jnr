"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { ButtonLink } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { Pagination } from "@/components/ui/Pagination";
import { apiFetch } from "@/lib/api";
import type { Client, Page } from "@/lib/clients";
import { formatTelephone } from "@/lib/format";

const TAILLE = 20;

export function ClientsListe({ page }: { page: number }) {
  const { data, isPending, isError, error } = useQuery({
    queryKey: ["clients", "liste", page],
    queryFn: ({ signal }) => apiFetch<Page<Client>>(`/clients?page=${page}&taille=${TAILLE}`, { signal }),
  });

  return (
    <>
      <header className="page-head">
        <div>
          <h1 className="display">Clients</h1>
          <p className="caption sub">Fiches clients et véhicules rattachés.</p>
        </div>
        <ButtonLink href="/clients/nouveau" variant="primary">
          <Icon name="plus" />
          Nouveau client
        </ButtonLink>
      </header>

      <section className="panel" aria-labelledby="titre-liste-clients">
        <h2 id="titre-liste-clients" className="sr-only">
          Liste des clients
        </h2>
        {isPending ? (
          <p className="empty" role="status">
            Chargement des clients…
          </p>
        ) : isError ? (
          <p className="empty danger-text" role="alert">
            {error.message}
          </p>
        ) : data.elements.length === 0 ? (
          <p className="empty">{data.total === 0 ? "Aucun client pour l'instant. Créez la première fiche." : "Aucun client sur cette page."}</p>
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
                    <td>{client.email ?? <span className="muted">—</span>}</td>
                    <td className="right num">{client.nombre_vehicules}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {data && data.total > 0 ? <Pagination page={page} taille={TAILLE} total={data.total} libelle={data.total > 1 ? "clients" : "client"} lien={(p) => `/clients?page=${p}`} /> : null}
    </>
  );
}
