"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { useSession } from "@/components/session/useSession";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Plate } from "@/components/ui/Plate";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { apiFetch } from "@/lib/api";
import { formatDate, formatDateHeure, formatKm, formatTelephone, nomComplet } from "@/lib/format";
import {
  formatDureeHM,
  formatRestitution,
  libellePasserA,
  messageTachesRestantes,
  modele,
  peutPasserA,
  prenom,
  suivant,
  tachesRestantes,
  versFormulaireOrdre,
  type OrdreDetail,
  type OrdreEntree,
} from "@/lib/ordres";
import { BADGE_OT, LIBELLE_OT } from "@/lib/statuts";
import { rafraichirApresOrdre, useChangerStatut } from "./actions";
import { cleOrdre, useMecaniciens, useOrdre } from "./donnees";
import { OrdreForm } from "./OrdreForm";
import { Suivi } from "./Suivi";
import { TachesCochables } from "./TachesCochables";

/** Fiche d'un ordre de travail (maquette « détail d'un OR ») : demande, travaux, véhicule, client. */
export function FicheOrdre({ ordreId }: { ordreId: number }) {
  const { utilisateur } = useSession();
  const gerant = utilisateur?.role === "gerant";
  const queryClient = useQueryClient();
  const [edition, setEdition] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const { data: ordre, isPending, isError, error } = useOrdre(ordreId);
  const mecaniciens = useMecaniciens();
  const avancer = useChangerStatut();

  if (isPending) {
    return (
      <p className="muted" role="status">
        Chargement de l&apos;ordre de travail…
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
          <Link href="/ordres">Retour aux ordres de travail</Link>
        </p>
      </div>
    );
  }

  function modifier(entree: OrdreEntree) {
    return apiFetch<OrdreDetail>(`/ordres/${ordreId}`, { method: "PUT", body: entree });
  }

  const modifiable = gerant && ordre.statut !== "livre";
  const prochain = suivant(ordre.statut);
  // Même règle que l'API (et que la vue tablette) : « Prêt » attend la dernière tâche.
  const bloque = prochain !== null && !peutPasserA(ordre, prochain);

  return (
    <>
      <header className="page-head">
        <div className="stack-sm">
          <p className="breadcrumb">
            <Link href="/ordres">Ordres de travail</Link> / <span className="mono">{ordre.numero}</span>
          </p>
          <div className="row">
            <h1 className="display">
              <span className="mono-titre">{ordre.numero}</span> · {modele(ordre.vehicule)}
            </h1>
            {ordre.prioritaire ? <StatusBadge status="urgent" /> : null}
            <StatusBadge status={BADGE_OT[ordre.statut]}>{LIBELLE_OT[ordre.statut]}</StatusBadge>
          </div>
          <p className="caption">
            Ouvert {formatDateHeure(ordre.ouvert_le)} par {prenom(ordre.cree_par.nom)}
            {ordre.cloture_le ? ` · livré ${formatDateHeure(ordre.cloture_le)}` : null}
          </p>
        </div>
        <div className="actions">
          {ordre.statut !== "livre" ? <ButtonLink href={`/ordres/${ordre.id}/tablette`}>Vue tablette atelier</ButtonLink> : null}
          {modifiable && !edition ? (
            <Button
              onClick={() => {
                setMessage(null);
                setEdition(true);
              }}
            >
              Modifier
            </Button>
          ) : null}
          {prochain && !edition ? (
            <>
              {bloque ? (
                <span className="caption" id="fiche-restantes">
                  {messageTachesRestantes(tachesRestantes(ordre))}
                </span>
              ) : null}
              <Button
                variant="primary"
                loading={avancer.isPending}
                disabled={bloque}
                aria-describedby={bloque ? "fiche-restantes" : undefined}
                onClick={() => avancer.mutate({ ordreId: ordre.id, nouveau: prochain })}
              >
                {libellePasserA(prochain)}
              </Button>
            </>
          ) : null}
        </div>
      </header>

      <p role="status" className={message ? "callout callout-success" : undefined}>
        {message}
      </p>

      <div className="grid-ot">
        <div className="stack">
          {edition ? (
            <section className="panel" aria-labelledby="titre-modification">
              <div className="panel-head">
                <h2 id="titre-modification">Modifier l&apos;ordre de travail</h2>
              </div>
              <div className="panel-body">
                {mecaniciens.data ? (
                  <OrdreForm
                    mode="modification"
                    valeursInitiales={versFormulaireOrdre(ordre)}
                    vehicules={[]}
                    mecaniciens={mecaniciens.data}
                    envoyer={modifier}
                    onSucces={(maj) => {
                      queryClient.setQueryData(cleOrdre(ordreId), maj);
                      void rafraichirApresOrdre(queryClient);
                      setEdition(false);
                      setMessage("Ordre de travail enregistré.");
                    }}
                    onAnnuler={() => setEdition(false)}
                  />
                ) : (
                  <p className="muted" role="status">
                    Chargement…
                  </p>
                )}
              </div>
            </section>
          ) : (
            <>
              <DemandeDiagnostic ordre={ordre} />
              <Travaux ordre={ordre} />
            </>
          )}
        </div>
        <aside className="stack" aria-label="Véhicule et client">
          <CarteVehicule ordre={ordre} lienFiche />
          <CarteClient ordre={ordre} />
          <Suivi historique={ordre.historique} />
        </aside>
      </div>
    </>
  );
}

export function DemandeDiagnostic({ ordre }: { ordre: OrdreDetail }) {
  return (
    <section className="panel" aria-labelledby="titre-demande">
      <div className="panel-head">
        <h2 id="titre-demande">Demande du client &amp; diagnostic</h2>
        {ordre.restitution_prevue ? (
          <span className={ordre.en_retard ? "danger-text strong" : "caption"}>
            Prêt promis {ordre.en_retard ? "pour" : "à"} {formatRestitution(ordre.restitution_prevue)}
            {ordre.en_retard ? " · en retard" : null}
          </span>
        ) : null}
      </div>
      <div className="panel-body">
        <div className="note">
          <p className="label">Demande du client</p>
          <p className="texte-libre">{ordre.demande_client}</p>
        </div>
        <div>
          <p className="label">Diagnostic</p>
          <p className="texte-libre">{ordre.diagnostic ?? <span className="muted">Pas encore de diagnostic.</span>}</p>
        </div>
        {ordre.kilometrage_entree !== null ? (
          <p className="caption">
            Kilométrage à l&apos;entrée : <span className="mono">{formatKm(ordre.kilometrage_entree)}</span>
          </p>
        ) : null}
      </div>
    </section>
  );
}

/** En-tête du panneau des travaux : « 1 sur 3 terminé · 2 h 30 prévues ». */
export function resumeTravaux(ordre: Pick<OrdreDetail, "taches_terminees" | "taches_total" | "duree_prevue_minutes">): string {
  const fait = `${ordre.taches_terminees} sur ${ordre.taches_total} ${ordre.taches_terminees > 1 ? "terminés" : "terminé"}`;
  return `${fait} · ${formatDureeHM(ordre.duree_prevue_minutes)} prévues`;
}

/** Travaux cochables par les deux rôles (mise à jour optimiste). */
export function Travaux({ ordre }: { ordre: OrdreDetail }) {
  return (
    <section className="panel" aria-labelledby="titre-travaux">
      <div className="panel-head">
        <h2 id="titre-travaux">Travaux à réaliser</h2>
        {ordre.taches_total > 0 ? <span className="caption">{resumeTravaux(ordre)}</span> : null}
      </div>
      <TachesCochables ordre={ordre} />
    </section>
  );
}

export function CarteVehicule({ ordre, lienFiche }: { ordre: OrdreDetail; lienFiche?: boolean }) {
  const v = ordre.vehicule;
  return (
    <section className="panel" aria-labelledby="titre-carte-vehicule">
      <div className="panel-head">
        <h2 id="titre-carte-vehicule">Véhicule</h2>
        {lienFiche ? <Link href={`/vehicules/${v.id}`}>Fiche véhicule</Link> : null}
      </div>
      <div className="panel-body">
        <div className="stack-sm">
          <Plate number={v.immatriculation} size="lg" />
          <p className="vehicule-modele">{modele(v)}</p>
        </div>
        <dl className="dl">
          <dt>VIN</dt>
          <dd className="mono">{v.vin ?? <span className="muted">Non renseigné</span>}</dd>
          <dt>Kilométrage</dt>
          <dd className="mono">{formatKm(v.kilometrage)}</dd>
          <dt>Mise en circulation</dt>
          <dd>{v.date_mise_en_circulation ? formatDate(v.date_mise_en_circulation) : <span className="muted">Non renseignée</span>}</dd>
          <dt>Mécanicien</dt>
          <dd>{ordre.mecanicien?.nom ?? <span className="muted">Non affecté</span>}</dd>
        </dl>
      </div>
    </section>
  );
}

/** Le mécanicien voit le nom du client ; téléphone et e-mail sont réservés au gérant (l'API ne les envoie pas). */
export function CarteClient({ ordre }: { ordre: OrdreDetail }) {
  const { client } = ordre;
  return (
    <section className="panel" aria-labelledby="titre-carte-client">
      <div className="panel-head">
        <h2 id="titre-carte-client">Client</h2>
        {client.contact ? <Link href={`/clients/${client.id}`}>Fiche client</Link> : null}
      </div>
      <div className="panel-body">
        <p className="strong">{nomComplet(client)}</p>
        {client.contact ? (
          <dl className="dl">
            <dt>Téléphone</dt>
            <dd className="num">
              <a href={`tel:${client.contact.telephone}`}>{formatTelephone(client.contact.telephone)}</a>
            </dd>
            <dt>E-mail</dt>
            <dd>{client.contact.email ? <a href={`mailto:${client.contact.email}`}>{client.contact.email}</a> : <span className="muted">Non renseigné</span>}</dd>
          </dl>
        ) : null}
      </div>
    </section>
  );
}
