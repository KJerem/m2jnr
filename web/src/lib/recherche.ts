/** Recherche du gérant (story S1.3) : types de l'API, messages et adresse de la page. */
import type { StatutOT } from "./statuts";

export interface ClientTrouve {
  id: number;
  nom: string;
  prenom: string | null;
  telephone: string;
  nb_vehicules: number;
}

export interface VehiculeTrouve {
  id: number;
  immatriculation: string;
  marque: string;
  modele: string;
  proprietaire: { id: number; nom: string; prenom: string | null };
}

export interface OrdreTrouve {
  id: number;
  numero: string;
  statut: StatutOT;
  immatriculation: string;
  marque: string;
  modele: string;
}

export interface FactureTrouvee {
  id: number;
  numero: string;
  emise_le: string;
  total_ttc_centimes: number;
  client: { nom: string; prenom: string | null };
}

export interface ResultatsRecherche {
  q: string;
  clients: ClientTrouve[];
  vehicules: VehiculeTrouve[];
  ordres: OrdreTrouve[];
  factures: FactureTrouvee[];
}

export const LONGUEUR_MIN = 2;
export const LONGUEUR_MAX = 100;
/** L'API rend au plus 20 résultats par rubrique. */
export const RESULTATS_MAX = 20;
export const PLACEHOLDER_RECHERCHE = "Plaque, client, n° d'OT";
export const MESSAGE_TROP_COURT = "Saisissez au moins 2 caractères.";
export const MESSAGE_TROP_LONG = "100 caractères au plus.";
export const AIDE_RECHERCHE = "Cherchez un nom, un numéro de téléphone, une immatriculation (avec ou sans tirets), un numéro d'OT ou de facture.";

/** Même règle que l'API : message d'erreur de la saisie, ou null si elle est valable. */
export function erreurSaisie(saisie: string): string | null {
  const texte = saisie.trim();
  if (texte.length < LONGUEUR_MIN) return MESSAGE_TROP_COURT;
  if (texte.length > LONGUEUR_MAX) return MESSAGE_TROP_LONG;
  return null;
}

/** « /recherche?q=gh482kl ». */
export function lienRecherche(saisie: string): string {
  return `/recherche?q=${encodeURIComponent(saisie.trim())}`;
}

export function messageAucunResultat(q: string): string {
  return `Aucun résultat pour « ${q} ». Vérifiez l'orthographe, ou cherchez un numéro de téléphone ou une immatriculation.`;
}

export function nombreResultats(r: ResultatsRecherche): number {
  return r.clients.length + r.vehicules.length + r.ordres.length + r.factures.length;
}

/** « 1 résultat », « 4 résultats ». */
export function libelleNombre(n: number): string {
  return `${n} résultat${n > 1 ? "s" : ""}`;
}
