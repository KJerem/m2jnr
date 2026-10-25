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

/**
 * Adresse d'une liste : « /clients?q=laurent&page=2 ». Les paramètres vides (null, « », page 1)
 * sont omis, dans l'ordre donné.
 */
export function lienListe(chemin: string, parametres: Record<string, string | number | null | undefined>): string {
  const params = new URLSearchParams();
  for (const [cle, valeur] of Object.entries(parametres)) {
    if (valeur === null || valeur === undefined || valeur === "") continue;
    if (cle === "page" && Number(valeur) <= 1) continue;
    params.set(cle, String(valeur));
  }
  const texte = params.toString();
  return texte ? `${chemin}?${texte}` : chemin;
}

/** « Aucun client ne correspond à « xyz ». » : message d'une recherche sans résultat. */
export function aucunResultat(aucun: string, q: string): string {
  return `${aucun} ne correspond à « ${q} ».`;
}
