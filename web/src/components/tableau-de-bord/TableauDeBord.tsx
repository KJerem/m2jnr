"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { ButtonLink } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { KpiTile } from "@/components/ui/KpiTile";
import { Plate } from "@/components/ui/Plate";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { apiFetch } from "@/lib/api";
import { formatHeure, nomComplet } from "@/lib/format";
import { modele, type OrdreResume } from "@/lib/ordres";
import { BADGE_OT, LIBELLE_OT } from "@/lib/statuts";
import {
  filtrerInterventions,
  LIBELLE_FILTRE,
  libelleVariation,
  montantSansSymbole,
  restitution,
  sousTitre,
  titreJour,
  type Arrivee,
  type ATraiter,
  type FiltreInterventions,
  type TableauDeBord as Donnees,
} from "@/lib/tableauDeBord";

export const CLE_TABLEAU_DE_BORD = ["tableau-de-bord"] as const;

/** Tableau de bord du gérant (maquette 4), rafraîchi toutes les minutes et après chaque écriture. */
export function TableauDeBord() {
  const { data, isPending, isError, error } = useQuery({
    queryKey: CLE_TABLEAU_DE_BORD,
    queryFn: ({ signal }) => apiFetch<Donnees>("/tableau-de-bord", { signal }),
    refetchInterval: 60_000,
  });

  return (
    <>
      <header className="page-head">
        <div>
          <h1 className="display">{data ? titreJour(data.jour) : "Atelier"}</h1>
          {data ? <p className="caption sub">{sousTitre(data.ponts_actifs, data.mecaniciens_actifs)}</p> : null}
        </div>
        <ButtonLink href="/ordres/nouveau" variant="primary">
          <Icon name="plus" />
          Nouvelle intervention
        </ButtonLink>
      </header>
      {isPending ? (
        <p className="muted" role="status">
          Chargement du tableau de bord…
        </p>
      ) : isError ? (
        <p className="callout callout-danger" role="alert">
          {error.message}
        </p>
      ) : (
        <>
          <Indicateurs donnees={data} />
          <div className="tdb-grille">
            <Interventions ordres={data.interventions} />
            <div className="tdb-cote">
              <Arrivees arrivees={data.arrivees} />
              <ATraiterMaintenant elements={data.a_traiter} />
            </div>
          </div>
        </>
      )}
    </>
  );
}

function Indicateurs({ donnees }: { donnees: Donnees }) {
  const k = donnees.kpis;
  const variation = libelleVariation(k.variation_pct, k.jour_comparaison);
  return (
    <section className="kpis tdb-kpis" aria-label="Indicateurs du jour">
      <KpiTile
        label="Véhicules à l'atelier"
        value={k.vehicules_atelier}
        delta={`+${k.entres_aujourdhui} ${k.entres_aujourdhui > 1 ? "entrés" : "entré"} aujourd'hui`}
        trend={k.entres_aujourdhui > 0 ? "good" : "flat"}
      />
      <KpiTile label="Prêts à restituer" value={k.prets_a_restituer} delta={`${k.a_restituer_aujourdhui} promis pour aujourd'hui`} />
      <KpiTile
        label="En retard"
        value={k.en_retard}
        highlight={k.en_retard > 0}
        trend={k.en_retard > 0 ? "bad" : "flat"}
        delta={k.en_retard > 0 ? "Heure promise dépassée" : "Aucun retard"}
      />
      <KpiTile
        label="Rendez-vous aujourd'hui"
        value={k.rendez_vous_aujourdhui}
        delta={k.prochain_rendez_vous ? `prochain à ${formatHeure(k.prochain_rendez_vous)}` : "Plus de rendez-vous aujourd'hui"}
      />
      <KpiTile
        label="Facturé aujourd'hui"
        value={montantSansSymbole(k.facture_aujourdhui_ttc_centimes)}
        unit="€ TTC"
        delta={variation ?? "Rien à comparer la semaine dernière"}
        trend={k.variation_pct === null || k.variation_pct === 0 ? "flat" : k.variation_pct > 0 ? "good" : "bad"}
      />
    </section>
  );
}

const FILTRES: FiltreInterventions[] = ["toutes", "a_restituer", "en_retard"];

/** « Interventions du jour » : filtres à bascule (aria-pressed) et tableau des OT. */
export function Interventions({ ordres, maintenant }: { ordres: OrdreResume[]; maintenant?: Date }) {
  const [filtre, setFiltre] = useState<FiltreInterventions>("toutes");
  const affichees = filtrerInterventions(ordres, filtre);
  return (
    <section className="panel" aria-labelledby="titre-interventions">
      <div className="panel-head">
        <h2 id="titre-interventions">Interventions du jour</h2>
        <div className="chips" role="group" aria-label="Filtrer les interventions">
          {FILTRES.map((f) => (
            <button key={f} type="button" className="chip" aria-pressed={filtre === f} onClick={() => setFiltre(f)}>
              {LIBELLE_FILTRE[f]} · {filtrerInterventions(ordres, f).length}
            </button>
          ))}
        </div>
      </div>
      {affichees.length === 0 ? (
        <p className="empty" role="status">
          {filtre === "toutes" ? "Aucune intervention aujourd'hui." : `Aucune intervention « ${LIBELLE_FILTRE[filtre]} ».`}
        </p>
      ) : (
        <div className="table-wrap">
          <table className="table tdb-table">
            <caption className="sr-only">Interventions du jour, {LIBELLE_FILTRE[filtre].toLowerCase()}</caption>
            <thead>
              <tr>
                <th scope="col">N° OT</th>
                <th scope="col">Véhicule</th>
                <th scope="col">Client</th>
                <th scope="col">Mécanicien</th>
                <th scope="col">Statut</th>
                <th scope="col" className="right">
                  Restitution
                </th>
              </tr>
            </thead>
            <tbody>
              {affichees.map((ordre) => {
                const cellule = restitution(ordre, maintenant);
                return (
                  <tr key={ordre.id}>
                    <td>
                      <Link href={`/ordres/${ordre.id}`} className="table-link mono nowrap">
                        {ordre.numero}
                      </Link>
                    </td>
                    <td>
                      <span className="tdb-vehicule">
                        <Plate number={ordre.vehicule.immatriculation} size="sm" />
                        <span>{modele(ordre.vehicule)}</span>
                      </span>
                    </td>
                    <td>{nomComplet(ordre.client)}</td>
                    <td>{ordre.mecanicien?.nom ?? <span className="muted">Non affecté</span>}</td>
                    <td>
                      <span className="tdb-badges">
                        {ordre.prioritaire ? <StatusBadge status="urgent" /> : null}
                        <StatusBadge status={BADGE_OT[ordre.statut]}>{LIBELLE_OT[ordre.statut]}</StatusBadge>
                      </span>
                    </td>
                    <td className={`right num nowrap${cellule.retard ? " danger-text strong" : ""}`}>{cellule.texte}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function Arrivees({ arrivees }: { arrivees: Arrivee[] }) {
  return (
    <section className="panel" aria-labelledby="titre-arrivees">
      <div className="panel-head">
        <h2 id="titre-arrivees">Arrivées prévues</h2>
      </div>
      {arrivees.length === 0 ? (
        <p className="empty">Plus d&apos;arrivée prévue aujourd&apos;hui.</p>
      ) : (
        <ul className="tdb-liste">
          {arrivees.map((a) => (
            <li key={a.rendez_vous_id} className="tdb-arrivee">
              <span className="tdb-heure">{formatHeure(a.heure)}</span>
              <span className="tdb-texte">
                <span className="strong">
                  {nomComplet(a.client)} · {modele(a.vehicule)}
                </span>
                <span className="caption">
                  {a.motif} · {a.pont.nom}
                </span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function ATraiterMaintenant({ elements }: { elements: ATraiter[] }) {
  return (
    <section className="panel panel-signal" aria-labelledby="titre-a-traiter">
      <div className="panel-head">
        <h2 id="titre-a-traiter">À traiter maintenant</h2>
      </div>
      {elements.length === 0 ? (
        <p className="empty">Rien d&apos;urgent pour l&apos;instant.</p>
      ) : (
        <ul className="tdb-liste">
          {elements.map((e) => (
            <li key={`${e.type}-${e.ordre_id}`}>
              <Link href={`/ordres/${e.ordre_id}`} className="tdb-a-traiter">
                <span className={`strong${e.type === "retard" ? " danger-text" : ""}`}>{e.titre}</span>
                <span className="caption">{e.detail}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
