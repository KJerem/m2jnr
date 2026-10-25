/** Comptes des employés (story S8.2) : types de l'API, libellés, validation et adresses. */
import { z } from "zod";
import type { BadgeStatus } from "@/components/ui/StatusBadge";
import { formatDateHeureOuAnnee, formatHeure } from "./format";
import type { Role } from "./session";

export type StatutCompte = "actif" | "en_attente" | "desactive";

export interface Employe {
  id: number;
  prenom: string;
  nom: string;
  nom_affiche: string;
  email: string;
  role: Role;
  statut: StatutCompte;
  /** Fin du blocage après 5 essais erronés ; null si le compte n'est pas bloqué. */
  bloque_jusqu_a: string | null;
  derniere_connexion: string | null;
  cree_le: string;
  valide_le: string | null;
  desactive_le: string | null;
}

export const LIBELLE_STATUT_COMPTE: Record<StatutCompte, string> = {
  actif: "Actif",
  en_attente: "En attente de validation",
  desactive: "Désactivé",
};

/** Pastille + mot : actif (pleine, succès), en attente (pleine, avertissement), désactivé (anneau). */
export const BADGE_STATUT_COMPTE: Record<StatutCompte, BadgeStatus> = {
  actif: "pret",
  en_attente: "en-cours",
  desactive: "livre",
};

export const LIBELLE_ROLE_PLURIEL: Record<Role, string> = {
  gerant: "Gérants",
  mecanicien: "Mécaniciens",
};

export const STATUTS_COMPTE: StatutCompte[] = ["en_attente", "actif", "desactive"];
export const ROLES: Role[] = ["gerant", "mecanicien"];

/** « Bloqué jusqu'à 15 h 02 » (5 essais erronés), ou null. */
export function libelleBlocage(employe: Pick<Employe, "bloque_jusqu_a">): string | null {
  return employe.bloque_jusqu_a ? `Bloqué jusqu'à ${formatHeure(employe.bloque_jusqu_a)}` : null;
}

export function libelleDerniereConnexion(employe: Pick<Employe, "derniere_connexion">): string {
  return employe.derniere_connexion ? formatDateHeureOuAnnee(employe.derniere_connexion) : "Jamais connecté";
}

export interface FiltresEmployes {
  q: string;
  role: Role | null;
  statut: StatutCompte | null;
  page: number;
}

/** « /employes?q=karim&statut=actif&page=2 » (paramètres vides omis). */
export function lienEmployes(filtres: Partial<FiltresEmployes>): string {
  const params = new URLSearchParams();
  if (filtres.q) params.set("q", filtres.q);
  if (filtres.role) params.set("role", filtres.role);
  if (filtres.statut) params.set("statut", filtres.statut);
  if (filtres.page && filtres.page > 1) params.set("page", String(filtres.page));
  const requete = params.toString();
  return requete ? `/employes?${requete}` : "/employes";
}

/** Requête de l'API correspondant aux filtres. */
export function requeteEmployes(filtres: FiltresEmployes, taille: number): string {
  const params = new URLSearchParams({ page: String(filtres.page), taille: String(taille) });
  if (filtres.q) params.set("q", filtres.q);
  if (filtres.role) params.set("role", filtres.role);
  if (filtres.statut) params.set("statut", filtres.statut);
  return `/utilisateurs?${params.toString()}`;
}

export function lireRole(valeur: string | string[] | undefined): Role | null {
  return valeur === "gerant" || valeur === "mecanicien" ? valeur : null;
}

export function lireStatut(valeur: string | string[] | undefined): StatutCompte | null {
  return typeof valeur === "string" && (STATUTS_COMPTE as string[]).includes(valeur) ? (valeur as StatutCompte) : null;
}

// --- Formulaires ---------------------------------------------------------------------------

export const LONGUEUR_MIN_MOT_DE_PASSE = 12;
export const MESSAGE_MOT_DE_PASSE_COURT = `Le mot de passe doit contenir au moins ${LONGUEUR_MIN_MOT_DE_PASSE} caractères.`;
export const MESSAGE_CONFIRMATION = "Les deux mots de passe ne correspondent pas.";
export const AIDE_MOT_DE_PASSE = `${LONGUEUR_MIN_MOT_DE_PASSE} caractères au moins. Une phrase de passe est plus facile à retenir.`;

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const obligatoire = (max: number) => z.string().trim().min(1, "Champ obligatoire.").max(max, `${max} caractères maximum.`);

export const motDePasseSchema = z
  .object({
    mot_de_passe: z.string().min(LONGUEUR_MIN_MOT_DE_PASSE, MESSAGE_MOT_DE_PASSE_COURT).max(1024, "1024 caractères maximum."),
    confirmation: z.string(),
  })
  .refine((v) => v.mot_de_passe === v.confirmation, { message: MESSAGE_CONFIRMATION, path: ["confirmation"] });

export type MotDePasseValeurs = z.infer<typeof motDePasseSchema>;

const identite = {
  prenom: obligatoire(100),
  nom: obligatoire(100),
  email: z
    .string()
    .trim()
    .min(1, "Champ obligatoire.")
    .max(254, "254 caractères maximum.")
    .refine((v) => EMAIL.test(v), "Adresse e-mail invalide."),
  role: z.enum(["gerant", "mecanicien"]),
};

export const employeModificationSchema = z.object(identite);
export type EmployeModificationValeurs = z.infer<typeof employeModificationSchema>;

/**
 * Modification d'un compte repris sans nom de famille (migration 0016 : « Admin » → prénom
 * « Admin », nom vide) : le nom peut rester vide, sans en inventer un (revue du sprint 5).
 */
export const employeSansNomModificationSchema = z.object({ ...identite, nom: z.string().trim().max(100, "100 caractères maximum.") });

/** Schéma du formulaire de modification : nom facultatif seulement s'il est déjà vide. */
export const schemaModificationEmploye = (employe: Pick<Employe, "nom">) => (employe.nom.trim() ? employeModificationSchema : employeSansNomModificationSchema);

export const employeCreationSchema = z
  .object({
    ...identite,
    mot_de_passe: z.string().min(LONGUEUR_MIN_MOT_DE_PASSE, MESSAGE_MOT_DE_PASSE_COURT).max(1024, "1024 caractères maximum."),
    confirmation: z.string(),
  })
  .refine((v) => v.mot_de_passe === v.confirmation, { message: MESSAGE_CONFIRMATION, path: ["confirmation"] });
export type EmployeCreationValeurs = z.infer<typeof employeCreationSchema>;

export const EMPLOYE_VIDE: EmployeCreationValeurs = { prenom: "", nom: "", email: "", role: "mecanicien", mot_de_passe: "", confirmation: "" };

export interface EmployeEntree {
  prenom: string;
  nom: string;
  email: string;
  role: Role;
}

export function versEntreeEmploye(valeurs: EmployeModificationValeurs): EmployeEntree {
  return { prenom: valeurs.prenom.trim(), nom: valeurs.nom.trim(), email: valeurs.email.trim(), role: valeurs.role };
}

export function versFormulaireEmploye(employe: Employe): EmployeModificationValeurs {
  return { prenom: employe.prenom, nom: employe.nom, email: employe.email, role: employe.role };
}

/** Clés de cache : invalider ["utilisateurs"] rafraîchit la liste et les fiches. */
export const cleEmploye = (id: number) => ["utilisateurs", "fiche", id] as const;

/** « de Karim B. », « d'Inès Morel » : élision devant une voyelle ou un h muet supposé. */
export function de(nom: string): string {
  return /^[aeiouyhàâäéèêëîïôöùûüÿœæ]/i.test(nom) ? `d'${nom}` : `de ${nom}`;
}
