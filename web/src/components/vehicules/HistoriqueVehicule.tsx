"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { Icon } from "@/components/ui/Icon";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { apiFetch } from "@/lib/api";
import { formatDateAnnee, formatKm } from "@/lib/format";
import type { StatutOT } from "@/lib/statuts";
import { BADGE_OT, LIBELLE_OT } from "@/lib/statuts";

export interface Intervention {
  id: number;
  numero: string;
  statut: StatutOT;
  demande_client: string;
  diagnostic: string | null;
  kilometrage_entree: number | null;
  ouvert_le: string;
  cloture_le: string | null;
  mecanicien: { id: number; nom: string } | null;
  taches: { libelle: string; terminee: boolean }[];
}

export const MESSAGE_AUCUNE_INTERVENTION = "Aucune intervention pour ce véhicule.";

/** Liste des interventions, de la plus récente à la plus ancienne (ordre rendu par l'API). */
export function ListeInterventions({ interventions }: { interventions: Intervention[] }) {
  if (interventions.length === 0) return <p className="empty">{MESSAGE_AUCUNE_INTERVENTION}</p>;
  return (
    <ol className="interventions">
      {interventions.map((i) => (
        <li key={i.id} className="intervention">
          <div className="intervention-tete">
            <time dateTime={i.ouvert_le} className="intervention-date">
              {formatDateAnnee(i.ouvert_le)}
            </time>
            <Link href={`/ordres/${i.id}`} className="mono intervention-numero">
              {i.numero}
            </Link>
            <StatusBadge status={BADGE_OT[i.statut]}>{LIBELLE_OT[i.statut]}</StatusBadge>
            {i.kilometrage_entree !== null ? <span className="mono muted">{formatKm(i.kilometrage_entree)}</span> : null}
          </div>
          <p className="texte-libre">{i.demande_client}</p>
          {i.diagnostic ? <p className="caption texte-libre">Diagnostic : {i.diagnostic}</p> : null}
          {i.taches.length > 0 ? (
            <ul className="intervention-taches">
              {i.taches.map((t, n) => (
                <li key={n} className={t.terminee ? "intervention-tache-faite" : undefined}>
                  <span className="intervention-coche" aria-hidden="true">
                    {t.terminee ? <Icon name="check" size={16} /> : null}
                  </span>
                  {t.libelle}
                  <span className="sr-only">{t.terminee ? " (fait)" : " (à faire)"}</span>
                </li>
              ))}
            </ul>
          ) : null}
          <p className="caption">{i.mecanicien ? `Mécanicien : ${i.mecanicien.nom}` : "Mécanicien non affecté"}</p>
        </li>
      ))}
    </ol>
  );
}

/** Onglet « Historique » de la fiche véhicule (gérant et mécanicien). */
export function HistoriqueVehicule({ vehiculeId }: { vehiculeId: number }) {
  const { data, isPending, isError, error } = useQuery({
    queryKey: ["vehicules", vehiculeId, "historique"],
    queryFn: ({ signal }) => apiFetch<Intervention[]>(`/vehicules/${vehiculeId}/historique`, { signal }),
  });
  if (isPending) {
    return (
      <p className="empty" role="status">
        Chargement de l&apos;historique…
      </p>
    );
  }
  if (isError) {
    return (
      <p className="empty danger-text" role="alert">
        {error.message}
      </p>
    );
  }
  return <ListeInterventions interventions={data} />;
}
