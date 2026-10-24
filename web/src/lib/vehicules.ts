/** Fiche véhicule : types de l'API, normalisation de la plaque et validation (mêmes règles que l'API). */
import { z } from "zod";
import { TIMEZONE } from "./format";

export const KILOMETRAGE_MAX = 2_000_000;

export interface VehiculeResume {
  id: number;
  immatriculation: string;
  marque: string;
  modele: string;
  kilometrage: number;
}

export interface Vehicule extends VehiculeResume {
  client_id: number;
  vin: string | null;
  date_mise_en_circulation: string | null;
  /** Identité seule : pas de coordonnées, la fiche est lisible par le mécanicien. */
  proprietaire: { id: number; nom: string; prenom: string | null };
  cree_le: string;
  modifie_le: string;
}

export interface VehiculeEntree {
  immatriculation: string;
  marque: string;
  modele: string;
  kilometrage: number;
  vin: string | null;
  date_mise_en_circulation: string | null;
}

export const MESSAGE_IMMATRICULATION = "Immatriculation invalide (format AA-123-AA).";
export const MESSAGE_VIN = "VIN invalide (17 caractères, sans I, O ni Q).";
export const MESSAGE_DATE_FUTURE = "La date de mise en circulation ne peut pas être dans le futur.";

const LETTRES = "[A-HJ-NP-TV-Z]";
const SIV = new RegExp(`^(${LETTRES}{2})(\\d{3})(${LETTRES}{2})$`);

/** « gh 482 kl » → « GH-482-KL » ; null si le format SIV n'est pas respecté (comme l'API). */
export function normaliserImmatriculation(valeur: string): string | null {
  const compacte = valeur.replace(/[\s-]/g, "").toUpperCase();
  const morceaux = SIV.exec(compacte);
  if (!morceaux || morceaux[2] === "000") return null;
  return `${morceaux[1]}-${morceaux[2]}-${morceaux[3]}`;
}

/** VIN en majuscules sans espaces ; null s'il ne fait pas 17 caractères autorisés. */
export function normaliserVin(valeur: string): string | null {
  const vin = valeur.replace(/\s/g, "").toUpperCase();
  return /^[A-HJ-NPR-Z0-9]{17}$/.test(vin) ? vin : null;
}

/** Date du jour à Paris au format des champs date : « 2026-11-09 ». */
export function aujourdHui(maintenant: Date = new Date()): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: TIMEZONE, year: "numeric", month: "2-digit", day: "2-digit" }).format(maintenant);
}

const obligatoire = (max: number) => z.string().trim().min(1, "Champ obligatoire.").max(max, `${max} caractères maximum.`);

export const vehiculeSchema = z.object({
  immatriculation: z
    .string()
    .trim()
    .min(1, "Champ obligatoire.")
    .refine((v) => normaliserImmatriculation(v) !== null, MESSAGE_IMMATRICULATION),
  marque: obligatoire(50),
  modele: obligatoire(80),
  kilometrage: z
    .string()
    .trim()
    .min(1, "Champ obligatoire.")
    .refine((v) => /^\d+$/.test(v.replace(/\s/g, "")), "Nombre entier positif attendu.")
    .refine((v) => Number(v.replace(/\s/g, "")) <= KILOMETRAGE_MAX, "Doit être inférieur ou égal à 2 000 000."),
  vin: z
    .string()
    .trim()
    .refine((v) => v === "" || normaliserVin(v) !== null, MESSAGE_VIN),
  date_mise_en_circulation: z.string().refine((v) => v === "" || v <= aujourdHui(), MESSAGE_DATE_FUTURE),
});

export type VehiculeFormValues = z.infer<typeof vehiculeSchema>;

export const VEHICULE_VIDE: VehiculeFormValues = {
  immatriculation: "",
  marque: "",
  modele: "",
  kilometrage: "",
  vin: "",
  date_mise_en_circulation: "",
};

export function versFormulaireVehicule(v: Vehicule): VehiculeFormValues {
  return {
    immatriculation: v.immatriculation,
    marque: v.marque,
    modele: v.modele,
    kilometrage: String(v.kilometrage),
    vin: v.vin ?? "",
    date_mise_en_circulation: v.date_mise_en_circulation ?? "",
  };
}

export function versEntreeVehicule(valeurs: VehiculeFormValues): VehiculeEntree {
  return {
    immatriculation: normaliserImmatriculation(valeurs.immatriculation) ?? valeurs.immatriculation.trim(),
    marque: valeurs.marque.trim(),
    modele: valeurs.modele.trim(),
    kilometrage: Number(valeurs.kilometrage.replace(/\s/g, "")),
    vin: valeurs.vin.trim() ? (normaliserVin(valeurs.vin) ?? valeurs.vin.trim()) : null,
    date_mise_en_circulation: valeurs.date_mise_en_circulation || null,
  };
}
