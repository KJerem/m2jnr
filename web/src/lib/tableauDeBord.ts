/** Tableau de bord du gérant (maquette 4) : types de l'API, filtres et formats. */
import { formatDateCourte, formatEuros, formatHeure, NBSP, TIMEZONE } from "./format";
import type { OrdreResume } from "./ordres";
import { aujourdHui } from "./vehicules";

export interface Arrivee {
  rendez_vous_id: number;
  heure: string;
  fin: string;
  motif: string;
  pont: { id: number; nom: string };
  vehicule: { id: number; immatriculation: string; marque: string; modele: string; kilometrage: number };
  client: { id: number; nom: string; prenom: string | null };
  ordre_id: number | null;
}

export interface ATraiter {
  type: "retard" | "facture_a_etablir" | "devis_a_valider" | "non_affecte";
  titre: string;
  detail: string;
  ordre_id: number;
  numero: string;
}

export interface TableauDeBord {
  /** Jour de Paris « AAAA-MM-JJ ». */
  jour: string;
  ponts_actifs: number;
  mecaniciens_actifs: number;
  kpis: {
    vehicules_atelier: number;
    entres_aujourdhui: number;
    prets_a_restituer: number;
    a_restituer_aujourdhui: number;
    en_retard: number;
    rendez_vous_aujourdhui: number;
    prochain_rendez_vous: string | null;
    facture_aujourdhui_ttc_centimes: number;
    facture_semaine_derniere_ttc_centimes: number;
    jour_comparaison: string;
    variation_pct: number | null;
  };
  interventions: OrdreResume[];
  arrivees: Arrivee[];
  a_traiter: ATraiter[];
}

export type FiltreInterventions = "toutes" | "a_restituer" | "en_retard";

export const LIBELLE_FILTRE: Record<FiltreInterventions, string> = {
  toutes: "Toutes",
  a_restituer: "À restituer",
  en_retard: "En retard",
};

/** « À restituer » = véhicules « Prêt » ; « En retard » = heure promise dépassée. */
export function filtrerInterventions(ordres: OrdreResume[], filtre: FiltreInterventions): OrdreResume[] {
  if (filtre === "a_restituer") return ordres.filter((o) => o.statut === "termine");
  if (filtre === "en_retard") return ordres.filter((o) => o.en_retard);
  return ordres;
}

/** Jour calendaire « AAAA-MM-JJ » vers une date à midi UTC (même jour à Paris). */
function midi(jour: string): Date {
  return new Date(`${jour}T12:00:00Z`);
}

/** « Atelier — samedi 24 oct. » : jour de la semaine en toutes lettres, mois abrégé. */
export function titreJour(jour: string): string {
  const d = midi(jour);
  const semaine = new Intl.DateTimeFormat("fr-FR", { timeZone: TIMEZONE, weekday: "long" }).format(d);
  const mois = new Intl.DateTimeFormat("fr-FR", { timeZone: TIMEZONE, month: "short" }).format(d);
  return `Atelier — ${semaine} ${d.getUTCDate()} ${mois}`;
}

const pluriel = (n: number, mot: string) => `${n} ${mot}${n > 1 ? "s" : ""}`;

/** « 3 ponts ouverts · 3 mécaniciens actifs ». */
export function sousTitre(ponts: number, mecaniciens: number): string {
  return `${pluriel(ponts, "pont")} ${ponts > 1 ? "ouverts" : "ouvert"} · ${pluriel(mecaniciens, "mécanicien")} ${mecaniciens > 1 ? "actifs" : "actif"}`;
}

/** Montant sans le symbole, pour la valeur d'une tuile : « 2 846,50 ». */
export function montantSansSymbole(centimes: number): string {
  return formatEuros(centimes).replace(/\s€$/, "");
}

/** « +12 % vs sam. dernier », « −5 % vs sam. dernier » ; null si rien à comparer. */
export function libelleVariation(pct: number | null, jourComparaison: string): string | null {
  if (pct === null) return null;
  const signe = pct > 0 ? "+" : pct < 0 ? "−" : "";
  const jour = new Intl.DateTimeFormat("fr-FR", { timeZone: TIMEZONE, weekday: "short" }).format(midi(jourComparaison));
  return `${signe}${Math.abs(pct)}${NBSP}% vs ${jour} dernier`;
}

export interface CelluleRestitution {
  texte: string;
  retard: boolean;
}

/**
 * Colonne « Restitution » : « 17 h 30 » aujourd'hui, « ven. 23 oct. » un autre jour,
 * « 12 h 00 · en retard » (le mot dit le retard, pas seulement la couleur), « Rendu 10 h 15 ».
 */
export function restitution(ordre: OrdreResume, maintenant: Date = new Date()): CelluleRestitution {
  const jour = (iso: string) => (aujourdHui(new Date(iso)) === aujourdHui(maintenant) ? formatHeure(iso) : formatDateCourte(iso));
  if (ordre.statut === "livre" && ordre.cloture_le) return { texte: `Rendu ${jour(ordre.cloture_le)}`, retard: false };
  if (!ordre.restitution_prevue) return { texte: "—", retard: false };
  const texte = jour(ordre.restitution_prevue);
  return ordre.en_retard ? { texte: `${texte} · en retard`, retard: true } : { texte, retard: false };
}
