"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { apiFetch } from "@/lib/api";
import { lignesAdresse, versFormulaire, type Client, type ClientDetail, type ClientEntree } from "@/lib/clients";
import { formatTelephone, nomComplet } from "@/lib/format";
import { VehiculesClient } from "@/components/vehicules/VehiculesClient";
import { ClientForm } from "./ClientForm";

export function FicheClient({ clientId }: { clientId: number }) {
  const queryClient = useQueryClient();
  const [edition, setEdition] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const cle = ["clients", "fiche", clientId] as const;
  const { data: client, isPending, isError, error } = useQuery({
    queryKey: cle,
    queryFn: ({ signal }) => apiFetch<ClientDetail>(`/clients/${clientId}`, { signal }),
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
      <div className="stack">
        <p className="callout callout-danger" role="alert">
          {error.message}
        </p>
        <p>
          <Link href="/clients">Retour à la liste des clients</Link>
        </p>
      </div>
    );
  }

  function modifier(entree: ClientEntree, confirmerDoublon: boolean) {
    return apiFetch<Client>(`/clients/${clientId}${confirmerDoublon ? "?confirmer_doublon=true" : ""}`, { method: "PUT", body: entree });
  }

  return (
    <>
      <header className="page-head">
        <div>
          <p className="breadcrumb">
            <Link href="/clients">Clients</Link> / Fiche
          </p>
          <h1 className="display">{nomComplet(client)}</h1>
        </div>
        {!edition ? (
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

      <section className="panel" aria-labelledby="titre-coordonnees">
        <div className="panel-head">
          <h2 id="titre-coordonnees">Coordonnées</h2>
        </div>
        <div className="panel-body">
          {edition ? (
            <ClientForm
              mode="modification"
              valeursInitiales={versFormulaire(client)}
              envoyer={modifier}
              onSucces={(maj) => {
                // La réponse ne contient pas les véhicules : on garde ceux déjà chargés.
                queryClient.setQueryData<ClientDetail>(cle, (ancien) => (ancien ? { ...ancien, ...maj } : undefined));
                void queryClient.invalidateQueries({ queryKey: ["clients", "liste"] });
                void queryClient.invalidateQueries({ queryKey: ["recherche"] });
                setEdition(false);
                setMessage("Fiche enregistrée.");
              }}
              onAnnuler={() => setEdition(false)}
            />
          ) : (
            <dl className="dl">
              <dt>Nom</dt>
              <dd>{client.nom}</dd>
              <dt>Prénom</dt>
              <dd>{client.prenom ?? <span className="muted">Non renseigné</span>}</dd>
              <dt>Téléphone</dt>
              <dd className="num">
                <a href={`tel:${client.telephone}`}>{formatTelephone(client.telephone)}</a>
              </dd>
              <dt>E-mail</dt>
              <dd>{client.email ? <a href={`mailto:${client.email}`}>{client.email}</a> : <span className="muted">Non renseigné</span>}</dd>
              <dt>Adresse</dt>
              <dd>
                {lignesAdresse(client).length > 0 ? (
                  <address className="adresse">
                    {lignesAdresse(client).map((ligne) => (
                      <span key={ligne}>{ligne}</span>
                    ))}
                  </address>
                ) : (
                  <span className="muted">Non renseignée</span>
                )}
              </dd>
              <dt>Rappels</dt>
              <dd>{client.consentement_rappels ? "Accepte les rappels d'entretien" : "Pas de rappels d'entretien"}</dd>
            </dl>
          )}
        </div>
      </section>

      <VehiculesClient
        clientId={client.id}
        vehicules={client.vehicules}
        onAjout={(vehicule) => {
          void queryClient.invalidateQueries({ queryKey: ["clients"] });
          void queryClient.invalidateQueries({ queryKey: ["recherche"] });
          setMessage(`Véhicule ${vehicule.immatriculation} ajouté.`);
        }}
      />
    </>
  );
}
