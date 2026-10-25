/** Constantes et types de session partagés par le proxy, le client d'API et les composants. */

/** Noms alignés sur les réglages de l'API (app/config.py). */
export const SESSION_COOKIE = "etabli_session";
export const CSRF_COOKIE = "csrf_token";
export const CSRF_HEADER = "X-CSRF-Token";

export const PAGE_CONNEXION = "/connexion";
/** Inscription autonome d'un gérant (story S8.3) : publique, comme la connexion. */
export const PAGE_INSCRIPTION = "/inscription";
/** Pages ouvertes sans session. */
export const PAGES_PUBLIQUES: readonly string[] = [PAGE_CONNEXION, PAGE_INSCRIPTION];

export type Role = "gerant" | "mecanicien";

export interface Utilisateur {
  id: number;
  email: string;
  prenom: string;
  nom: string;
  /** Prénom puis nom, tels qu'ils s'affichent partout (« Karim B. »). */
  nom_affiche: string;
  role: Role;
}

export interface SessionReponse {
  utilisateur: Utilisateur;
}

export const LIBELLE_ROLE: Record<Role, string> = {
  gerant: "Gérant",
  mecanicien: "Mécanicien",
};

/**
 * Chemin de retour après connexion : seulement un chemin interne (pas de « //site » ni d'URL
 * absolue, pour ne pas servir de redirection ouverte), et jamais la page de connexion elle-même.
 */
export function cheminDeRetour(suivant: string | null | undefined): string {
  if (!suivant || !suivant.startsWith("/") || suivant.startsWith("//") || suivant.startsWith("/\\")) return "/";
  if (suivant === PAGE_CONNEXION || suivant.startsWith(`${PAGE_CONNEXION}?`)) return "/";
  return suivant;
}
