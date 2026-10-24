/** Ordres de travail : types de l'API, formulaire (mêmes règles que l'API) et formats d'affichage. */
import { z } from "zod";
import { formatDateHeure, formatHeure, NBSP, TIMEZONE } from "./format";
import type { StatutOT } from "./statuts";
import { aujourdHui } from "./vehicules";

export interface UtilisateurResume {
  id: number;
  nom: string;
}

export interface VehiculeOrdre {
  id: number;
  immatriculation: string;
  marque: string;
  modele: string;
  kilometrage: number;
}

export interface VehiculeOrdreDetail extends VehiculeOrdre {
  vin: string | null;
  date_mise_en_circulation: string | null;
}

export interface ClientOrdre {
  id: number;
  nom: string;
  prenom: string | null;
  /** null pour le mécanicien : ni téléphone ni e-mail. */
  contact: { telephone: string; email: string | null } | null;
}

export interface Tache {
  id: number;
  libelle: string;
  duree_prevue_minutes: number;
  position: number;
  terminee: boolean;
  terminee_le: string | null;
  terminee_par: UtilisateurResume | null;
}

export interface OrdreResume {
  id: number;
  numero: string;
  statut: StatutOT;
  prioritaire: boolean;
  vehicule: VehiculeOrdre;
  client: ClientOrdre;
  mecanicien: UtilisateurResume | null;
  restitution_prevue: string | null;
  ouvert_le: string;
  cloture_le: string | null;
  taches_terminees: number;
  taches_total: number;
  duree_prevue_minutes: number;
  en_retard: boolean;
}

export interface OrdreDetail extends OrdreResume {
  vehicule: VehiculeOrdreDetail;
  demande_client: string;
  diagnostic: string | null;
  kilometrage_entree: number | null;
  cree_par: UtilisateurResume;
  taches: Tache[];
}

export interface TacheEntree {
  id?: number;
  libelle: string;
  duree_prevue_minutes: number;
}

/** Corps de POST /ordres ; PUT /ordres/{id} reprend les mêmes champs sauf véhicule et kilométrage. */
export interface OrdreEntree {
  vehicule_id?: number;
  demande_client: string;
  diagnostic: string | null;
  prioritaire: boolean;
  kilometrage_entree?: number | null;
  /** « 2026-11-16T17:30 », lu à l'heure de Paris par l'API. */
  restitution_prevue: string | null;
  mecanicien_id: number | null;
  taches: TacheEntree[];
}

export const MESSAGE_VEHICULE_OBLIGATOIRE = "Un ordre de travail doit être rattaché à un véhicule.";
export const DUREE_TACHE_MAX = 600;
export const TACHES_MAX = 50;

/** Durées proposées pour une tâche, en minutes (de 15 min à 10 h). */
export const DUREES_TACHE = [15, 30, 45, 60, 75, 90, 120, 150, 180, 240, 300, 360, 420, 480, 540, 600];

const tacheSchema = z.object({
  id: z.number().optional(),
  libelle: z.string().trim().min(1, "Champ obligatoire.").max(200, "200 caractères maximum."),
  duree_prevue_minutes: z
    .string()
    .min(1, "Champ obligatoire.")
    .refine((v) => /^\d+$/.test(v) && Number(v) >= 1 && Number(v) <= DUREE_TACHE_MAX, "Durée invalide."),
});

export const ordreSchema = z.object({
  vehicule_id: z.string(),
  demande_client: z.string().trim().min(1, "Champ obligatoire.").max(2000, "2000 caractères maximum."),
  diagnostic: z.string().trim().max(4000, "4000 caractères maximum."),
  prioritaire: z.boolean(),
  kilometrage_entree: z
    .string()
    .trim()
    .refine((v) => v === "" || /^\d+$/.test(v.replace(/\s/g, "")), "Nombre entier positif attendu."),
  restitution_prevue: z.string(),
  mecanicien_id: z.string(),
  taches: z.array(tacheSchema).max(TACHES_MAX, `${TACHES_MAX} tâches maximum.`),
});

export type OrdreFormValues = z.infer<typeof ordreSchema>;
export type TacheFormValues = OrdreFormValues["taches"][number];

export const TACHE_VIDE: TacheFormValues = { libelle: "", duree_prevue_minutes: "60" };

export function ordreVide(vehiculeId?: number | null): OrdreFormValues {
  return {
    vehicule_id: vehiculeId ? String(vehiculeId) : "",
    demande_client: "",
    diagnostic: "",
    prioritaire: false,
    kilometrage_entree: "",
    restitution_prevue: "",
    mecanicien_id: "",
    taches: [],
  };
}

/** Instant ISO vers la valeur d'un champ datetime-local à l'heure de Paris : « 2026-11-16T17:30 ». */
export function versSaisieDateHeure(iso: string): string {
  const p = new Intl.DateTimeFormat("en-CA", {
    timeZone: TIMEZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(new Date(iso));
  const v = (type: Intl.DateTimeFormatPartTypes) => p.find((x) => x.type === type)?.value ?? "";
  return `${v("year")}-${v("month")}-${v("day")}T${v("hour")}:${v("minute")}`;
}

export function versFormulaireOrdre(ordre: OrdreDetail): OrdreFormValues {
  return {
    vehicule_id: String(ordre.vehicule.id),
    demande_client: ordre.demande_client,
    diagnostic: ordre.diagnostic ?? "",
    prioritaire: ordre.prioritaire,
    kilometrage_entree: ordre.kilometrage_entree === null ? "" : String(ordre.kilometrage_entree),
    restitution_prevue: ordre.restitution_prevue ? versSaisieDateHeure(ordre.restitution_prevue) : "",
    mecanicien_id: ordre.mecanicien ? String(ordre.mecanicien.id) : "",
    taches: ordre.taches.map((t) => ({ id: t.id, libelle: t.libelle, duree_prevue_minutes: String(t.duree_prevue_minutes) })),
  };
}

export function versEntreeOrdre(valeurs: OrdreFormValues): OrdreEntree {
  const km = valeurs.kilometrage_entree.replace(/\s/g, "");
  return {
    vehicule_id: valeurs.vehicule_id ? Number(valeurs.vehicule_id) : undefined,
    demande_client: valeurs.demande_client.trim(),
    diagnostic: valeurs.diagnostic.trim() || null,
    prioritaire: valeurs.prioritaire,
    kilometrage_entree: km ? Number(km) : null,
    restitution_prevue: valeurs.restitution_prevue || null,
    mecanicien_id: valeurs.mecanicien_id ? Number(valeurs.mecanicien_id) : null,
    taches: valeurs.taches.map((t) => ({
      ...(t.id !== undefined ? { id: t.id } : {}),
      libelle: t.libelle.trim(),
      duree_prevue_minutes: Number(t.duree_prevue_minutes),
    })),
  };
}

/** « 2 h 30 », « 45 min », « 3 h ». */
export function formatDureeHM(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h === 0) return `${m}${NBSP}min`;
  return m === 0 ? `${h}${NBSP}h` : `${h}${NBSP}h${NBSP}${String(m).padStart(2, "0")}`;
}

/** Restitution : « 17 h 30 » le jour même, sinon « jeu. 22 oct. à 17 h 30 ». */
export function formatRestitution(iso: string, maintenant: Date = new Date()): string {
  return aujourdHui(new Date(iso)) === aujourdHui(maintenant) ? formatHeure(iso) : formatDateHeure(iso);
}

/** Prénom affiché dans « Ouvert … par Nadia ». */
export function prenom(nom: string): string {
  return nom.trim().split(/\s+/)[0] ?? nom;
}

/** Marque et modèle : « Peugeot 308 SW ». */
export function modele(v: { marque: string; modele: string }): string {
  return `${v.marque} ${v.modele}`;
}

/** « aujourd'hui à 9 h 15 », « hier à 9 h 15 », sinon « mar. 14 oct. à 9 h 15 ». */
export function formatQuand(iso: string, maintenant: Date = new Date()): string {
  const jour = aujourdHui(new Date(iso));
  if (jour === aujourdHui(maintenant)) return `aujourd'hui à ${formatHeure(iso)}`;
  const hier = new Date(maintenant.getTime() - 24 * 3600 * 1000);
  if (jour === aujourdHui(hier)) return `hier à ${formatHeure(iso)}`;
  return formatDateHeure(iso);
}
