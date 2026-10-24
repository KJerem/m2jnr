/** Paramètres d'adresse communs aux pages de liste. */

export type Recherche = Record<string, string | string[] | undefined>;

/** « ?page=3 » vers 3 ; absent, invalide ou inférieur à 1 → 1. */
export function numeroDePage(valeur: string | string[] | undefined): number {
  return Math.max(1, Number.parseInt(typeof valeur === "string" ? valeur : "1", 10) || 1);
}
