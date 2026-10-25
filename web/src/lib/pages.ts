/** Paramètres d'adresse communs aux pages de liste. */

export type Recherche = Record<string, string | string[] | undefined>;

/** « ?page=3 » vers 3 ; absent, invalide ou inférieur à 1 → 1. */
export function numeroDePage(valeur: string | string[] | undefined): number {
  return Math.max(1, Number.parseInt(typeof valeur === "string" ? valeur : "1", 10) || 1);
}

/** Longueur minimale d'une recherche, comme l'API (422 en dessous). */
const LONGUEUR_MIN_Q = 2;

/**
 * « ?q= » d'une liste (stories S8.2 et S1.5) : saisie sans espaces de bord, 100 caractères au
 * plus. Moins de 2 caractères (adresse saisie à la main) : ignorée, la liste s'affiche sans
 * filtre (revue du sprint 5 : l'API répondait 422 et la liste annonçait « Aucun … ne
 * correspond à « a ». » sans qu'aucune recherche ait eu lieu).
 */
export function texteDeRecherche(valeur: string | string[] | undefined): string {
  const texte = typeof valeur === "string" ? valeur.trim().slice(0, 100) : "";
  return texte.length >= LONGUEUR_MIN_Q ? texte : "";
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
