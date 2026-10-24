/** Fiche client : types de l'API, validation du formulaire (mêmes règles que l'API). */
import { z } from "zod";
import type { VehiculeResume } from "./vehicules";

export interface Page<T> {
  elements: T[];
  total: number;
  page: number;
  taille: number;
}

export interface ClientResume {
  id: number;
  nom: string;
  prenom: string | null;
}

/** Adresse postale facultative (mention de la facture, art. 242 nonies A du CGI). */
export interface AdresseClient {
  adresse: string | null;
  code_postal: string | null;
  ville: string | null;
}

export interface Client extends ClientResume, AdresseClient {
  telephone: string;
  email: string | null;
  consentement_rappels: boolean;
  nombre_vehicules: number;
  cree_le: string;
  modifie_le: string;
}

/** Fiche complète renvoyée par GET /clients/{id}. */
export interface ClientDetail extends Client {
  vehicules: VehiculeResume[];
}

/** Corps envoyé à POST /clients et PUT /clients/{id}. */
export interface ClientEntree extends AdresseClient {
  nom: string;
  prenom: string | null;
  telephone: string;
  email: string | null;
  consentement_rappels: boolean;
}

export const MESSAGE_OBLIGATOIRE = "Champ obligatoire.";
export const MESSAGE_TELEPHONE = "Numéro de téléphone français invalide.";
export const MESSAGE_EMAIL = "Adresse e-mail invalide.";
export const MESSAGE_CODE_POSTAL = "Code postal à 5 chiffres.";

/** « 12 rue des Tilleuls », « 69003 Lyon » : lignes de l'adresse renseignées, sinon []. */
export function lignesAdresse(client: Partial<AdresseClient>): string[] {
  const ville = [client.code_postal, client.ville].filter(Boolean).join(" ");
  return [client.adresse, ville].filter((ligne): ligne is string => Boolean(ligne));
}

/** Même règle que l'API (services/telephone.py) : 10 chiffres « 0XXXXXXXXX », ou null. */
export function normaliserTelephone(valeur: string): string | null {
  let chiffres = valeur.trim().replace(/[\s.\-()/]/g, "");
  if (chiffres.startsWith("+33")) chiffres = `0${chiffres.slice(3)}`;
  else if (chiffres.startsWith("0033")) chiffres = `0${chiffres.slice(4)}`;
  return /^0[1-9]\d{8}$/.test(chiffres) ? chiffres : null;
}

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export const clientSchema = z.object({
  nom: z.string().trim().min(1, MESSAGE_OBLIGATOIRE).max(100, "100 caractères maximum."),
  prenom: z.string().trim().max(100, "100 caractères maximum."),
  telephone: z
    .string()
    .trim()
    .min(1, MESSAGE_OBLIGATOIRE)
    .refine((v) => normaliserTelephone(v) !== null, MESSAGE_TELEPHONE),
  email: z
    .string()
    .trim()
    .max(254, "254 caractères maximum.")
    .refine((v) => v === "" || EMAIL.test(v), MESSAGE_EMAIL),
  adresse: z.string().trim().max(200, "200 caractères maximum."),
  code_postal: z
    .string()
    .trim()
    .refine((v) => v === "" || /^\d{5}$/.test(v), MESSAGE_CODE_POSTAL),
  ville: z.string().trim().max(100, "100 caractères maximum."),
  consentement_rappels: z.boolean(),
});

export type ClientFormValues = z.infer<typeof clientSchema>;

export const CLIENT_VIDE: ClientFormValues = {
  nom: "",
  prenom: "",
  telephone: "",
  email: "",
  adresse: "",
  code_postal: "",
  ville: "",
  // RGPD : jamais coché par défaut.
  consentement_rappels: false,
};

export function versFormulaire(client: Client): ClientFormValues {
  return {
    nom: client.nom,
    prenom: client.prenom ?? "",
    telephone: client.telephone,
    email: client.email ?? "",
    adresse: client.adresse ?? "",
    code_postal: client.code_postal ?? "",
    ville: client.ville ?? "",
    consentement_rappels: client.consentement_rappels,
  };
}

export function versEntree(valeurs: ClientFormValues): ClientEntree {
  return {
    nom: valeurs.nom.trim(),
    prenom: valeurs.prenom.trim() || null,
    telephone: valeurs.telephone.trim(),
    email: valeurs.email.trim() || null,
    adresse: valeurs.adresse.trim() || null,
    code_postal: valeurs.code_postal.trim() || null,
    ville: valeurs.ville.trim() || null,
    consentement_rappels: valeurs.consentement_rappels,
  };
}
