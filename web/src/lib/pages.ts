/** Paramètres d'adresse communs aux pages de liste. */

export type Recherche = Record<string, string | string[] | undefined>;

/** « ?page=3 » vers 3 ; absent, invalide ou inférieur à 1 → 1. */
export function numeroDePage(valeur: string | string[] | undefined): number {
  return Math.max(1, Number.parseInt(typeof valeur === "string" ? valeur : "1", 10) || 1);
}

/** « ?q= » d'une liste (stories S8.2 et S1.5) : saisie sans espaces de bord, 100 caractères au plus. */
export function texteDeRecherche(valeur: string | string[] | undefined): string {
  return typeof valeur === "string" ? valeur.trim().slice(0, 100) : "";
}
