"use client";

import Link from "next/link";
import { useChangerStatut } from "@/components/ordres/actions";
import { useOrdre } from "@/components/ordres/donnees";
import { TachesCochables } from "@/components/ordres/TachesCochables";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Plate } from "@/components/ui/Plate";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { formatKm } from "@/lib/format";
import { formatRestitution, modele, type OrdreDetail } from "@/lib/ordres";
import { BADGE_OT, LIBELLE_OT } from "@/lib/statuts";
import { Horloge } from "./Horloge";

/** « TRAVAUX 1 SUR 3 TERMINÉS » et barre de progression. */
function Progression({ ordre }: { ordre: OrdreDetail }) {
  const pct = ordre.taches_total > 0 ? Math.round((ordre.taches_terminees / ordre.taches_total) * 100) : 0;
  // « Travaux … terminés » : l'accord se fait avec « travaux ».
  const libelle = `Travaux ${ordre.taches_terminees} sur ${ordre.taches_total} terminés`;
  return (
    <div className="tablette-progression">
      <h2 className="label" id="tablette-progression">
        {libelle}
      </h2>
      <div className="et-progress tablette-barre" role="progressbar" aria-labelledby="tablette-progression" aria-valuemin={0} aria-valuemax={ordre.taches_total} aria-valuenow={ordre.taches_terminees}>
        <div className="et-progress-bar" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

/** Action principale selon le statut : démarrer, puis terminer quand toutes les tâches sont faites. */
export function ActionPrincipale({ ordre }: { ordre: OrdreDetail }) {
  const avancer = useChangerStatut();
  const restantes = ordre.taches_total - ordre.taches_terminees;
  if (ordre.statut === "a_faire") {
    return (
      <Button variant="primary" size="lg" loading={avancer.isPending} onClick={() => avancer.mutate({ ordreId: ordre.id, nouveau: "en_cours" })}>
        Démarrer l&apos;intervention
      </Button>
    );
  }
  if (ordre.statut === "en_cours") {
    return (
      <div className="tablette-terminer">
        <Button
          variant="primary"
          size="lg"
          disabled={restantes > 0}
          aria-describedby={restantes > 0 ? "tablette-restantes" : undefined}
          loading={avancer.isPending}
          onClick={() => avancer.mutate({ ordreId: ordre.id, nouveau: "termine" })}
        >
          Terminer l&apos;intervention
        </Button>
        {restantes > 0 ? (
          <span className="caption" id="tablette-restantes">
            Encore {restantes} {restantes > 1 ? "tâches" : "tâche"} à terminer.
          </span>
        ) : null}
      </div>
    );
  }
  return (
    <p className="callout callout-success" role="status">
      {ordre.statut === "termine" ? "Intervention terminée : le véhicule est prêt." : "Véhicule livré au client."}
    </p>
  );
}

/** Vue tablette atelier (maquette 1) : lisible à un mètre, cibles de 56 px et plus. */
export function VueTablette({ ordreId }: { ordreId: number }) {
  const { data: ordre, isPending, isError, error } = useOrdre(ordreId);
  const colonne = null;
  const nomPoste = "Atelier";

  return (
    <div className="tablette-page">
      <header className="tablette-entete">
        <p className="tablette-poste">{ordre ? `${nomPoste} · ${ordre.mecanicien?.nom ?? "Non affecté"}` : "Atelier"}</p>
        <Horloge />
      </header>
      {isPending ? (
        <p className="muted tablette-corps" role="status">
          Chargement de l&apos;intervention…
        </p>
      ) : isError ? (
        <div className="tablette-corps stack">
          <p className="callout callout-danger" role="alert">
            {error.message}
          </p>
          <Link href="/">Retour à l&apos;accueil</Link>
        </div>
      ) : (
        <div className={`tablette-corps tablette-grille${colonne ? " tablette-grille-pont" : ""}`}>
          <div className="stack">
            <section className="panel" aria-labelledby="tablette-titre">
              <div className="panel-body">
                <div className="row">
                  <Plate number={ordre.vehicule.immatriculation} size="lg" />
                  <h1 id="tablette-titre" className="tablette-modele">
                    {modele(ordre.vehicule)}
                  </h1>
                  {ordre.prioritaire ? <StatusBadge status="urgent" /> : null}
                  <StatusBadge status={BADGE_OT[ordre.statut]}>{LIBELLE_OT[ordre.statut]}</StatusBadge>
                </div>
                <p className="tablette-infos">
                  <span className="mono">{ordre.numero}</span> · <span className="mono">{formatKm(ordre.kilometrage_entree ?? ordre.vehicule.kilometrage)}</span>
                  {ordre.restitution_prevue ? (
                    <span className={ordre.en_retard ? "danger-text" : undefined}>
                      {" "}
                      · prêt promis à {formatRestitution(ordre.restitution_prevue)}
                      {ordre.en_retard ? " · en retard" : null}
                    </span>
                  ) : null}
                </p>
                <div className="note">
                  <p className="label">Demande du client</p>
                  <p className="texte-libre tablette-demande">{ordre.demande_client}</p>
                  {ordre.diagnostic ? <p className="texte-libre caption">Diagnostic : {ordre.diagnostic}</p> : null}
                </div>
              </div>
            </section>
            <section className="panel" aria-labelledby="tablette-progression">
              <div className="panel-body">
                <Progression ordre={ordre} />
              </div>
              <TachesCochables ordre={ordre} variante="tablette" />
            </section>
            <div className="tablette-actions">
              <ButtonLink href={`/ordres/${ordre.id}`} size="lg">
                Vue accueil
              </ButtonLink>
              <ActionPrincipale ordre={ordre} />
            </div>
          </div>
          {colonne}
        </div>
      )}
    </div>
  );
}
