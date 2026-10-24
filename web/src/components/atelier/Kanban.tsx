"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { CarteOrdre } from "@/components/ordres/CarteOrdre";
import { useChangerStatut } from "@/components/ordres/actions";
import { Button } from "@/components/ui/Button";
import { apiFetch } from "@/lib/api";
import type { Page } from "@/lib/clients";
import { libellePasserA, messageTachesRestantes, peutPasserA, suivant, tachesRestantes, trierCartes, type OrdreResume } from "@/lib/ordres";
import { LIBELLE_OT, STATUTS_OT, type StatutOT } from "@/lib/statuts";

export const CLE_ATELIER = ["ordres", "atelier"] as const;

export interface CarteKanbanProps {
  ordre: OrdreResume;
  enCours: boolean;
  onAvancer: (ordre: OrdreResume, nouveau: StatutOT) => void;
}

/** Carte du kanban : lien vers la fiche, et bouton « Passer à … » à part (pas de glisser-déposer). */
export function CarteKanban({ ordre, enCours, onAvancer }: CarteKanbanProps) {
  const prochain = suivant(ordre.statut);
  const bloque = prochain !== null && !peutPasserA(ordre, prochain);
  const idRestantes = `kanban-restantes-${ordre.id}`;
  return (
    <li id={`kanban-${ordre.id}`} className="kanban-carte" tabIndex={-1}>
      <CarteOrdre ordre={ordre} />
      {prochain ? (
        <Button block loading={enCours} disabled={bloque} aria-describedby={bloque ? idRestantes : undefined} onClick={() => onAvancer(ordre, prochain)}>
          {libellePasserA(prochain)}
          <span className="sr-only"> : {ordre.numero}</span>
        </Button>
      ) : null}
      {bloque ? (
        <span className="caption" id={idRestantes}>
          {messageTachesRestantes(tachesRestantes(ordre))}
        </span>
      ) : null}
    </li>
  );
}

/** Suivi atelier : quatre colonnes de statut, livrés limités au jour même. */
export function Kanban() {
  const { data, isPending, isError, error } = useQuery({
    queryKey: CLE_ATELIER,
    queryFn: ({ signal }) => apiFetch<Page<OrdreResume>>("/ordres?atelier=true&taille=200", { signal }),
    refetchInterval: 60_000,
  });
  // La carte change de colonne : le focus la suit une fois la liste rechargée (sinon il
  // retomberait au début de la page avec le bouton disparu).
  const aFocaliser = useRef<{ id: number; statut: StatutOT } | null>(null);
  const avancer = useChangerStatut({ onSucces: (ordre) => (aFocaliser.current = { id: ordre.id, statut: ordre.statut }) });

  useEffect(() => {
    const cible = aFocaliser.current;
    if (!cible || !data) return;
    const ordre = data.elements.find((o) => o.id === cible.id);
    if (ordre?.statut !== cible.statut) return;
    document.getElementById(`kanban-${cible.id}`)?.focus();
    aFocaliser.current = null;
  }, [data]);

  return (
    <>
      <header className="page-head">
        <div>
          <h1 className="display">Suivi atelier</h1>
          <p className="caption sub">Un bouton par carte fait avancer l&apos;intervention d&apos;une étape. Les livraisons du jour restent visibles.</p>
        </div>
      </header>
      {isPending ? (
        <p className="muted" role="status">
          Chargement de l&apos;atelier…
        </p>
      ) : isError ? (
        <p className="callout callout-danger" role="alert">
          {error.message}
        </p>
      ) : (
        <div className="kanban">
          {STATUTS_OT.map((statut) => {
            const cartes = trierCartes(data.elements.filter((o) => o.statut === statut));
            const titreId = `kanban-titre-${statut}`;
            return (
              <section key={statut} className="kanban-colonne" aria-labelledby={titreId}>
                <h2 id={titreId} className="kanban-titre">
                  <span>{statut === "livre" ? "Livré aujourd'hui" : LIBELLE_OT[statut]}</span>
                  <span className="kanban-compte" aria-label={`${cartes.length} ${cartes.length > 1 ? "ordres" : "ordre"}`}>
                    {cartes.length}
                  </span>
                </h2>
                {cartes.length === 0 ? (
                  <p className="kanban-vide">Aucun véhicule.</p>
                ) : (
                  <ol className="kanban-cartes">
                    {cartes.map((ordre) => (
                      <CarteKanban
                        key={ordre.id}
                        ordre={ordre}
                        enCours={avancer.isPending && avancer.variables?.ordreId === ordre.id}
                        onAvancer={(o, nouveau) => avancer.mutate({ ordreId: o.id, nouveau })}
                      />
                    ))}
                  </ol>
                )}
              </section>
            );
          })}
        </div>
      )}
    </>
  );
}
