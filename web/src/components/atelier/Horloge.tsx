"use client";

import { useSyncExternalStore } from "react";
import { formatHeure } from "@/lib/format";

/** L'heure change à chaque minute : on s'abonne à un minuteur aligné sur la minute suivante. */
function abonner(notifier: () => void) {
  let minuteur: number | undefined;
  const planifier = () => {
    const maintenant = new Date();
    const attente = 60_000 - (maintenant.getSeconds() * 1000 + maintenant.getMilliseconds()) + 50;
    minuteur = window.setTimeout(() => {
      notifier();
      planifier();
    }, attente);
  };
  planifier();
  return () => window.clearTimeout(minuteur);
}

const heureCourante = () => formatHeure(new Date());
// Rendu serveur : pas d'heure (elle différerait de celle du navigateur à l'hydratation).
const heureServeur = () => "";

/** Heure courante à Paris, « 14 h 42 », mise à jour chaque minute. */
export function Horloge() {
  const heure = useSyncExternalStore(abonner, heureCourante, heureServeur);
  return (
    <p className="tablette-horloge" aria-label={heure ? `Il est ${heure}` : undefined}>
      {heure}
    </p>
  );
}
