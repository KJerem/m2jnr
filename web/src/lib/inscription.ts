/** Inscription autonome d'un gérant (story S8.3) : types de l'API, validation, messages. */
import { z } from "zod";
import { LONGUEUR_MIN_MOT_DE_PASSE, MESSAGE_CONFIRMATION, MESSAGE_MOT_DE_PASSE_COURT } from "./employes";
import type { Utilisateur } from "./session";

/** Message neutre de l'API (202) : le même, que l'e-mail soit déjà connu ou non. */
export const MESSAGE_DEMANDE_ENREGISTREE = "Demande enregistrée. Un gérant du garage doit valider votre compte avant votre première connexion.";

/** GET /auth/inscription : la prochaine inscription crée-t-elle le premier compte (actif) ? */
export interface EtatInscription {
  premier_compte: boolean;
}

/** POST /auth/register : 201 avec la session (premier compte), 202 sinon. */
export interface InscriptionReponse {
  compte_actif: boolean;
  message: string;
  utilisateur: Utilisateur | null;
}

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const obligatoire = z.string().trim().min(1, "Champ obligatoire.").max(100, "100 caractères maximum.");

export const inscriptionSchema = z
  .object({
    prenom: obligatoire,
    nom: obligatoire,
    email: z
      .string()
      .trim()
      .min(1, "Champ obligatoire.")
      .max(254, "254 caractères maximum.")
      .refine((v) => EMAIL.test(v), "Adresse e-mail invalide."),
    mot_de_passe: z.string().min(LONGUEUR_MIN_MOT_DE_PASSE, MESSAGE_MOT_DE_PASSE_COURT).max(1024, "1024 caractères maximum."),
    confirmation: z.string(),
  })
  .refine((v) => v.mot_de_passe === v.confirmation, { message: MESSAGE_CONFIRMATION, path: ["confirmation"] });

export type InscriptionValeurs = z.infer<typeof inscriptionSchema>;

export const INSCRIPTION_VIDE: InscriptionValeurs = { prenom: "", nom: "", email: "", mot_de_passe: "", confirmation: "" };

export function versEntreeInscription(valeurs: InscriptionValeurs) {
  return { prenom: valeurs.prenom.trim(), nom: valeurs.nom.trim(), email: valeurs.email.trim(), mot_de_passe: valeurs.mot_de_passe };
}
