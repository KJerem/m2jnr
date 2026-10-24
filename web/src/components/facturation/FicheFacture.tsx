"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { BlocTotaux, TableauDevis } from "@/components/devis/DevisOrdre";
import { Plate } from "@/components/ui/Plate";
import { apiFetch } from "@/lib/api";
import { formatJour, libelleTelechargement, lienPdf, type FactureDetail } from "@/lib/factures";
import { formatDate, formatKm, formatTelephone, nomComplet } from "@/lib/format";
import { modele } from "@/lib/ordres";
import { BadgesPaiement, cleFacture, PaiementsFacture } from "./PaiementsFacture";

/**
 * Page d'une facture : les données figées à l'émission et son PDF (qui ne change jamais), puis
 * ses paiements (story S4.4).
 */
export function FicheFacture({ factureId }: { factureId: number }) {
  const { data: facture, isPending, isError, error } = useQuery({
    queryKey: cleFacture(factureId),
    queryFn: ({ signal }) => apiFetch<FactureDetail>(`/factures/${factureId}`, { signal }),
  });

  if (isPending) {
    return (
      <p className="muted" role="status">
        Chargement de la facture…
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
          <Link href="/factures">Retour aux factures</Link>
        </p>
      </div>
    );
  }

  const { client, vehicule, garage } = facture;
  return (
    <>
      <header className="page-head">
        <div className="stack-sm">
          <p className="breadcrumb">
            <Link href="/factures">Devis &amp; factures</Link> / <span className="mono">{facture.numero}</span>
          </p>
          <h1 className="display">
            Facture <span className="mono-titre">{facture.numero}</span>
          </h1>
          <BadgesPaiement statut={facture.statut_paiement} enRetard={facture.en_retard} />
          <p className="caption">
            Émise le {formatDate(facture.emise_le)} · échéance le {formatJour(facture.echeance)} · ordre de travail{" "}
            <Link href={`/ordres/${facture.ordre.id}`} className="mono">
              {facture.ordre.numero}
            </Link>
          </p>
        </div>
        <div className="actions">
          <a className="et-btn et-btn-primary" href={lienPdf(facture.id)} download aria-label={libelleTelechargement(facture.numero)}>
            Télécharger le PDF
          </a>
        </div>
      </header>

      <div className="grid-ot">
        <div className="stack">
          <section className="panel" aria-labelledby="titre-lignes-facture">
            <div className="panel-head">
              <h2 id="titre-lignes-facture">Pièces &amp; main-d&apos;œuvre</h2>
              <span className="caption">Facture non modifiable</span>
            </div>
            <TableauDevis devis={facture} legende={`Lignes de la facture ${facture.numero}`} />
            <BlocTotaux totaux={facture.totaux} tauxBp={facture.taux_tva_bp} />
          </section>
          <PaiementsFacture facture={facture} />
        </div>
        <aside className="stack" aria-label="Client, véhicule et garage">
          <section className="panel" aria-labelledby="titre-facture-client">
            <div className="panel-head">
              <h2 id="titre-facture-client">Client</h2>
            </div>
            <div className="panel-body">
              <p className="strong">{nomComplet(client)}</p>
              <dl className="dl">
                <dt>Téléphone</dt>
                <dd className="num">{client.telephone ? formatTelephone(client.telephone) : <span className="muted">Non renseigné</span>}</dd>
                <dt>E-mail</dt>
                <dd>{client.email ?? <span className="muted">Non renseigné</span>}</dd>
              </dl>
            </div>
          </section>
          <section className="panel" aria-labelledby="titre-facture-vehicule">
            <div className="panel-head">
              <h2 id="titre-facture-vehicule">Véhicule</h2>
            </div>
            <div className="panel-body">
              <div className="stack-sm">
                <Plate number={vehicule.immatriculation} size="lg" />
                <p className="vehicule-modele">{modele(vehicule)}</p>
              </div>
              <dl className="dl">
                <dt>Kilométrage</dt>
                <dd className="mono">{formatKm(vehicule.kilometrage)}</dd>
              </dl>
            </div>
          </section>
          <section className="panel" aria-labelledby="titre-facture-garage">
            <div className="panel-head">
              <h2 id="titre-facture-garage">Mentions</h2>
            </div>
            <div className="panel-body caption">
              <p>
                {garage.raison_sociale} au capital de {garage.capital} · {garage.rcs}
              </p>
              <p>
                SIRET {garage.siret} · TVA intracommunautaire {garage.tva_intracommunautaire}
              </p>
              <p>{garage.adresse}</p>
            </div>
          </section>
        </aside>
      </div>
    </>
  );
}
