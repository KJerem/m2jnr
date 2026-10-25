import type { BadgeStatus } from "@/components/ui/StatusBadge";

/** Statuts métier de l'ordre de travail (règle du backlog, story S3.2). */
export type StatutOT = "a_faire" | "en_cours" | "termine" | "livre";

export const STATUTS_OT: StatutOT[] = ["a_faire", "en_cours", "termine", "livre"];

/** Correspondance avec les badges du design system Établi. */
export const BADGE_OT: Record<StatutOT, BadgeStatus> = {
  a_faire: "attente",
  en_cours: "en-cours",
  termine: "pret",
  livre: "livre",
};

export const LIBELLE_OT: Record<StatutOT, string> = {
  a_faire: "En attente",
  en_cours: "En cours",
  termine: "Prêt",
  livre: "Livré",
};

/** Statut suivant autorisé (une étape, sans retour), ou null si l'OT est livré. */
export function statutSuivant(statut: StatutOT): StatutOT | null {
  const i = STATUTS_OT.indexOf(statut);
  return STATUTS_OT[i + 1] ?? null;
}

/** « ?statut= » d'un statut d'OT connu, null sinon. */
export function lireStatutOT(valeur: string | string[] | undefined): StatutOT | null {
  return typeof valeur === "string" && (STATUTS_OT as string[]).includes(valeur) ? (valeur as StatutOT) : null;
}
