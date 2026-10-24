"use client";

import { formatDureeHeures } from "@/lib/format";
import { formatQuand, type OrdreDetail } from "@/lib/ordres";
import { useBasculerTache } from "./actions";

export interface TachesCochablesProps {
  ordre: OrdreDetail;
  /** fiche : lignes de 56 px · tablette : lignes de 72 px, cases de 32 px (lu à un mètre, au gant). */
  variante?: "fiche" | "tablette";
}

/**
 * Tâches cochables par le gérant et le mécanicien. Une vraie case à cocher par tâche, avec
 * son libellé : utilisable au clavier (Espace) et annoncée par les lecteurs d'écran. Verrouillées
 * quand l'OT est livré ; une tâche faite ne se décoche plus quand le véhicule est prêt.
 */
export function TachesCochables({ ordre, variante = "fiche" }: TachesCochablesProps) {
  const basculer = useBasculerTache(ordre.id);
  if (ordre.taches.length === 0) return <p className="empty">Aucune tâche prévue.</p>;

  return (
    <ul className={`taches${variante === "tablette" ? " taches-tablette" : ""}`}>
      {ordre.taches.map((t) => {
        const id = `tache-${ordre.id}-${t.id}`;
        const verrouillee = ordre.statut === "livre" || (ordre.statut === "termine" && t.terminee);
        return (
          <li key={t.id} className={`tache tache-cochable${t.terminee ? " tache-faite" : ""}`}>
            <input
              id={id}
              type="checkbox"
              className="tache-case"
              checked={t.terminee}
              disabled={verrouillee}
              aria-describedby={`${id}-detail`}
              onChange={(event) => basculer.mutate({ tacheId: t.id, terminee: event.target.checked })}
            />
            <label htmlFor={id} className="tache-texte">
              <span className="tache-libelle">{t.libelle}</span>
              <span className="caption" id={`${id}-detail`}>
                {t.terminee && t.terminee_le ? `Terminé ${formatQuand(t.terminee_le)}${t.terminee_par ? ` par ${t.terminee_par.nom}` : ""}` : "À faire"}
              </span>
            </label>
            <span className="tache-duree mono">{formatDureeHeures(t.duree_prevue_minutes)}</span>
          </li>
        );
      })}
    </ul>
  );
}
