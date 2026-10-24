"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import type { ReactNode } from "react";
import { Plate } from "@/components/ui/Plate";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ApiError, apiFetch } from "@/lib/api";
import { formatDateCourteOuAnnee, formatEuros, formatTelephone, nomComplet } from "@/lib/format";
import { modele } from "@/lib/ordres";
import {
  AIDE_RECHERCHE,
  libelleNombre,
  messageAucunResultat,
  nombreResultats,
  RESULTATS_MAX,
  type ResultatsRecherche,
} from "@/lib/recherche";
import { BADGE_OT, LIBELLE_OT } from "@/lib/statuts";
import { ChampRecherche } from "./ChampRecherche";

export const cleRecherche = (q: string) => ["recherche", q] as const;

/** Page « Recherche » (gérant) : résultats groupés, chaque résultat est un lien. */
export function PageRecherche({ q }: { q: string }) {
  const texte = q.trim();
  const { data, isPending, isError, error } = useQuery({
    queryKey: cleRecherche(texte),
    queryFn: ({ signal }) => apiFetch<ResultatsRecherche>(`/recherche?q=${encodeURIComponent(texte)}`, { signal }),
    enabled: texte.length > 0,
    retry: false,
  });
  // 422 (saisie trop courte ou trop longue) : message sous le champ, pas d'encadré d'erreur.
  const erreurChamp = isError && error instanceof ApiError && error.status === 422 ? (error.champs.q ?? error.message) : null;

  return (
    <>
      <header className="page-head">
        <div>
          <h1 className="display">Recherche</h1>
          <p className="caption sub">{AIDE_RECHERCHE}</p>
        </div>
        <ChampRecherche key={texte} valeurInitiale={texte} erreurServeur={erreurChamp} className="recherche-page" />
      </header>
      {texte.length === 0 ? null : isPending ? (
        <p className="muted" role="status">
          Recherche en cours…
        </p>
      ) : isError ? (
        erreurChamp ? null : (
          <p className="callout callout-danger" role="alert">
            {error.message}
          </p>
        )
      ) : (
        <Resultats resultats={data} />
      )}
    </>
  );
}

function Resultats({ resultats }: { resultats: ResultatsRecherche }) {
  const total = nombreResultats(resultats);
  if (total === 0) {
    return (
      <p className="panel empty" role="status">
        {messageAucunResultat(resultats.q)}
      </p>
    );
  }
  return (
    <>
      <p role="status" className="caption">
        {libelleNombre(total)} pour « {resultats.q} ».
      </p>
      <div className="recherche-grille">
        <Groupe id="clients" titre="Clients" nombre={resultats.clients.length}>
          {resultats.clients.map((c) => (
            <li key={c.id}>
              <Link href={`/clients/${c.id}`} className="recherche-lien">
                <span className="strong">{nomComplet(c)}</span>
                <span className="caption">
                  <span className="num">{formatTelephone(c.telephone)}</span> · {c.nb_vehicules} véhicule{c.nb_vehicules > 1 ? "s" : ""}
                </span>
              </Link>
            </li>
          ))}
        </Groupe>
        <Groupe id="vehicules" titre="Véhicules" nombre={resultats.vehicules.length}>
          {resultats.vehicules.map((v) => (
            <li key={v.id}>
              <Link href={`/vehicules/${v.id}`} className="recherche-lien recherche-lien-ligne">
                <Plate number={v.immatriculation} size="sm" />
                <span className="recherche-texte">
                  <span className="strong">{modele(v)}</span>
                  <span className="caption">{nomComplet(v.proprietaire)}</span>
                </span>
              </Link>
            </li>
          ))}
        </Groupe>
        <Groupe id="ordres" titre="Ordres de travail" nombre={resultats.ordres.length}>
          {resultats.ordres.map((o) => (
            <li key={o.id}>
              <Link href={`/ordres/${o.id}`} className="recherche-lien recherche-lien-ot">
                <span className="mono strong nowrap">{o.numero}</span>
                <span className="recherche-texte">
                  <Plate number={o.immatriculation} size="sm" />
                  <span className="caption">{modele(o)}</span>
                </span>
                <StatusBadge status={BADGE_OT[o.statut]}>{LIBELLE_OT[o.statut]}</StatusBadge>
              </Link>
            </li>
          ))}
        </Groupe>
        <Groupe id="factures" titre="Factures" nombre={resultats.factures.length}>
          {resultats.factures.map((f) => (
            <li key={f.id}>
              <Link href={`/factures/${f.id}`} className="recherche-lien recherche-lien-ligne">
                <span className="mono strong nowrap">{f.numero}</span>
                <span className="recherche-texte">
                  <span>{nomComplet(f.client)}</span>
                  <span className="caption">Émise le {formatDateCourteOuAnnee(f.emise_le)}</span>
                </span>
                <span className="num strong nowrap">{formatEuros(f.total_ttc_centimes)}</span>
              </Link>
            </li>
          ))}
        </Groupe>
      </div>
    </>
  );
}

function Groupe({ id, titre, nombre, children }: { id: string; titre: string; nombre: number; children: ReactNode }) {
  if (nombre === 0) return null;
  return (
    <section className="panel" aria-labelledby={`titre-recherche-${id}`}>
      <div className="panel-head">
        <h2 id={`titre-recherche-${id}`}>
          {titre} <span className="muted num">({nombre})</span>
        </h2>
        {nombre >= RESULTATS_MAX ? <span className="caption">Les {RESULTATS_MAX} premiers : précisez la recherche.</span> : null}
      </div>
      <ul className="recherche-liste">{children}</ul>
    </section>
  );
}
