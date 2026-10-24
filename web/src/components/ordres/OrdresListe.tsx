"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useSession } from "@/components/session/useSession";
import { ButtonLink } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { Pagination } from "@/components/ui/Pagination";
import { Plate } from "@/components/ui/Plate";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { apiFetch } from "@/lib/api";
import type { Page } from "@/lib/clients";
import { nomComplet } from "@/lib/format";
import { formatRestitution, modele, type OrdreResume } from "@/lib/ordres";
import { BADGE_OT, LIBELLE_OT, STATUTS_OT, type StatutOT } from "@/lib/statuts";

const TAILLE = 50;

function lien(statut: StatutOT | null, page = 1) {
  const params = new URLSearchParams();
  if (statut) params.set("statut", statut);
  if (page > 1) params.set("page", String(page));
  const requete = params.toString();
  return requete ? `/ordres?${requete}` : "/ordres";
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

export function OrdresListe({ page, statut }: { page: number; statut: StatutOT | null }) {
  const { utilisateur } = useSession();
  const { data, isPending, isError, error } = useQuery({
    queryKey: ["ordres", "liste", statut, page],
    queryFn: ({ signal }) => apiFetch<Page<OrdreResume>>(`/ordres?page=${page}&taille=${TAILLE}${statut ? `&statut=${statut}` : ""}`, { signal }),
  });

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

      <nav className="chips" aria-label="Filtrer par statut">
        <Link href={lien(null)} className="chip" aria-current={statut === null ? "true" : undefined}>
          Tous
        </Link>
        {STATUTS_OT.map((s) => (
          <Link key={s} href={lien(s)} className="chip" aria-current={statut === s ? "true" : undefined}>
            {LIBELLE_OT[s]}
          </Link>
        ))}
      </nav>

      <section className="panel" aria-labelledby="titre-liste-ordres">
        <h2 id="titre-liste-ordres" className="sr-only">
          Liste des ordres de travail
        </h2>
        {isPending ? (
          <p className="empty" role="status">
            Chargement des ordres de travail…
          </p>
        ) : isError ? (
          <p className="empty danger-text" role="alert">
            {error.message}
          </p>
        ) : data.elements.length === 0 ? (
          <p className="empty">{statut ? `Aucun ordre de travail « ${LIBELLE_OT[statut]} ».` : "Aucun ordre de travail pour l'instant."}</p>
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

      {data && data.total > 0 ? <Pagination page={page} taille={TAILLE} total={data.total} libelle={data.total > 1 ? "ordres de travail" : "ordre de travail"} lien={(p) => lien(statut, p)} /> : null}
    </>
  );
}
