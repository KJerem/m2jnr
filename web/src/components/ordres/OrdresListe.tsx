"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { useSession } from "@/components/session/useSession";
import { ButtonLink } from "@/components/ui/Button";
import { ChampRechercheListe } from "@/components/ui/ChampRechercheListe";
import { Icon } from "@/components/ui/Icon";
import { Pagination } from "@/components/ui/Pagination";
import { Plate } from "@/components/ui/Plate";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ApiError, apiFetch } from "@/lib/api";
import type { Page } from "@/lib/clients";
import { nomComplet } from "@/lib/format";
import { formatRestitution, modele, type OrdreResume } from "@/lib/ordres";
import { aucunResultat, lienListe } from "@/lib/pages";
import { BADGE_OT, LIBELLE_OT, STATUTS_OT, type StatutOT } from "@/lib/statuts";

const TAILLE = 50;

/** « /ordres?statut=en_cours&q=clio&page=2 » (paramètres vides omis). */
export function lienOrdres(statut: StatutOT | null, page = 1, q = "") {
  return lienListe("/ordres", { statut, q, page });
}

/** Message de liste vide selon le statut et la recherche. */
export function messageAucunOrdre(statut: StatutOT | null, q: string): string {
  if (q) return aucunResultat(statut ? `Aucun ordre de travail « ${LIBELLE_OT[statut]} »` : "Aucun ordre de travail", q);
  return statut ? `Aucun ordre de travail « ${LIBELLE_OT[statut]} ».` : "Aucun ordre de travail pour l'instant.";
}

/** Cellule « Restitution » : heure le jour même, date sinon ; retard signalé par le mot, pas seulement la couleur. */
export function Restitution({ ordre }: { ordre: OrdreResume }) {
  if (!ordre.restitution_prevue) return <span className="muted">—</span>;
  return (
    <span className={ordre.en_retard ? "danger-text strong" : undefined}>
      {formatRestitution(ordre.restitution_prevue)}
      {ordre.en_retard ? " · en retard" : null}
    </span>
  );
}

/**
 * Liste des ordres de travail (gérant et mécanicien) : filtre par statut (liens) et recherche
 * par numéro, plaque, véhicule, client, mécanicien ou demande (story S1.5), gardés dans
 * l'adresse ; une nouvelle recherche repart de la page 1.
 */
export function OrdresListe({ page, statut, q: qInitial = "" }: { page: number; statut: StatutOT | null; q?: string }) {
  const { utilisateur } = useSession();
  const [q, setQ] = useState(qInitial);
  const [pageCourante, setPage] = useState(page);
  const parametres = new URLSearchParams({ page: String(pageCourante), taille: String(TAILLE) });
  if (statut) parametres.set("statut", statut);
  if (q) parametres.set("q", q);
  const { data, isPending, isError, error } = useQuery({
    queryKey: ["ordres", "liste", statut, q, pageCourante],
    queryFn: ({ signal }) => apiFetch<Page<OrdreResume>>(`/ordres?${parametres.toString()}`, { signal }),
    placeholderData: keepPreviousData,
  });
  const erreurRecherche = isError && error instanceof ApiError && error.status === 422 ? (error.champs.q ?? error.message) : null;

  function rechercher(saisie: string) {
    setQ(saisie);
    setPage(1);
    window.history.replaceState(null, "", lienOrdres(statut, 1, saisie));
  }

  return (
    <>
      <header className="page-head">
        <div>
          <h1 className="display">Ordres de travail</h1>
          <p className="caption sub">Interventions ouvertes, en cours et livrées.</p>
        </div>
        {utilisateur?.role === "gerant" ? (
          <ButtonLink href="/ordres/nouveau" variant="primary">
            <Icon name="plus" />
            Nouvel ordre de travail
          </ButtonLink>
        ) : null}
      </header>

      <div className="liste-filtres">
        <ChampRechercheListe
          libelle="Rechercher un ordre de travail"
          placeholder="N° d'OT, plaque, client, mécanicien"
          valeurInitiale={qInitial}
          onRecherche={rechercher}
          total={data && q ? data.total : null}
          erreurServeur={erreurRecherche}
          className="recherche-liste"
        />
        <nav className="chips" aria-label="Filtrer par statut">
          <Link href={lienOrdres(null, 1, q)} className="chip" aria-current={statut === null ? "true" : undefined}>
            Tous
          </Link>
          {STATUTS_OT.map((s) => (
            <Link key={s} href={lienOrdres(s, 1, q)} className="chip" aria-current={statut === s ? "true" : undefined}>
              {LIBELLE_OT[s]}
            </Link>
          ))}
        </nav>
      </div>

      <section className="panel" aria-labelledby="titre-liste-ordres">
        <h2 id="titre-liste-ordres" className="sr-only">
          Liste des ordres de travail
        </h2>
        {isPending ? (
          <p className="empty" role="status">
            Chargement des ordres de travail…
          </p>
        ) : isError && !erreurRecherche ? (
          <p className="empty danger-text" role="alert">
            {error.message}
          </p>
        ) : !data || data.elements.length === 0 ? (
          <p className="empty">{messageAucunOrdre(statut, q)}</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Numéro</th>
                  <th scope="col">Véhicule</th>
                  <th scope="col">Client</th>
                  <th scope="col">Mécanicien</th>
                  <th scope="col">Statut</th>
                  <th scope="col">Restitution</th>
                </tr>
              </thead>
              <tbody>
                {data.elements.map((ordre) => (
                  <tr key={ordre.id}>
                    <td>
                      <Link href={`/ordres/${ordre.id}`} className="table-link mono">
                        {ordre.numero}
                      </Link>
                    </td>
                    <td>
                      <span className="row nowrap">
                        <Plate number={ordre.vehicule.immatriculation} />
                        <span>{modele(ordre.vehicule)}</span>
                      </span>
                    </td>
                    <td>{nomComplet(ordre.client)}</td>
                    <td>{ordre.mecanicien?.nom ?? <span className="muted">Non affecté</span>}</td>
                    <td>
                      <span className="row nowrap">
                        {ordre.prioritaire ? <StatusBadge status="urgent" /> : null}
                        <StatusBadge status={BADGE_OT[ordre.statut]}>{LIBELLE_OT[ordre.statut]}</StatusBadge>
                      </span>
                    </td>
                    <td className="num">
                      <Restitution ordre={ordre} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {data && data.total > 0 ? <Pagination page={pageCourante} taille={TAILLE} total={data.total} libelle={data.total > 1 ? "ordres de travail" : "ordre de travail"} lien={(p) => lienOrdres(statut, p, q)} /> : null}
    </>
  );
}
