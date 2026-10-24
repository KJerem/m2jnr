/** Factures (story S4.3) et leurs paiements (story S4.4) : types de l'API et règles d'affichage. */
import type { BadgeStatus } from "@/components/ui/StatusBadge";
import type { LigneDevis, StatutDevis, TotauxDevis } from "./devis";
import { formatDateCourteOuAnnee, formatEuros, parseEurosToCentimes } from "./format";
import { aujourdHui } from "./vehicules";
import type { StatutOT } from "./statuts";

export type StatutPaiement = "impayee" | "partielle" | "payee";
export type ModePaiement = "carte" | "especes" | "cheque" | "virement";

export interface Paiement {
  id: number;
  montant_centimes: number;
  mode: ModePaiement;
  recu_le: string;
  reference: string | null;
  cree_par: { id: number; nom: string };
}

/** Champs de paiement communs à la liste et à la fiche (story S4.4). */
export interface SuiviPaiement {
  paiements: Paiement[];
  deja_paye_centimes: number;
  reste_centimes: number;
  statut_paiement: StatutPaiement;
  /** Non payée et échéance dépassée (jour de Paris). */
  en_retard: boolean;
}

export interface FactureResume extends SuiviPaiement {
  id: number;
  numero: string;
  emise_le: string;
  /** Jour « AAAA-MM-JJ ». */
  echeance: string;
  ordre: { id: number; numero: string };
  client: { nom: string; prenom: string | null };
  vehicule: { immatriculation: string; marque: string; modele: string };
  total_ht_centimes: number;
  total_ttc_centimes: number;
}

export interface FactureDetail extends Omit<FactureResume, "client" | "vehicule" | "total_ht_centimes" | "total_ttc_centimes"> {
  devis_id: number;
  client: { nom: string; prenom: string | null; telephone: string | null; email: string | null };
  vehicule: { immatriculation: string; marque: string; modele: string; kilometrage: number };
  garage: {
    raison_sociale: string;
    adresse: string;
    siret: string;
    tva_intracommunautaire: string;
    capital: string;
    rcs: string;
    telephone: string;
    email: string;
  };
  lignes: LigneDevis[];
  taux_tva_bp: number;
  totaux: TotauxDevis;
}

/** Même règle que l'API : la facture s'établit quand l'intervention est « Prêt » ou « Livré ». */
export function peutFacturer(statut: StatutOT): boolean {
  return statut === "termine" || statut === "livre";
}

/** Story S4.2 : la facture s'établit sur un devis accepté, intervention « Prêt » ou « Livré ». */
export function factureDisponible(statutOT: StatutOT, statutDevis: StatutDevis): boolean {
  return statutDevis === "accepte" && peutFacturer(statutOT);
}

export const MESSAGE_FACTURE_INDISPONIBLE = "Disponible quand le devis est accepté et l'intervention « Prêt ».";

/** Adresse du PDF, relayée vers l'API (même origine, cookie de session). */
export function lienPdf(factureId: number): string {
  return `/api/factures/${factureId}/pdf`;
}

/** « Télécharger la facture F-2026-001 (PDF) » : nom accessible des liens de téléchargement. */
export function libelleTelechargement(numero: string): string {
  return `Télécharger la facture ${numero} (PDF)`;
}

/** Numéro annoncé avant l'émission : « F-2026-… » (année du jour à Paris). */
export function numeroAVenir(maintenant: Date = new Date()): string {
  return `F-${aujourdHui(maintenant).slice(0, 4)}-…`;
}

/** Échéance « 2026-11-23 » vers « 23/11/2026 » (jour calendaire, sans fuseau). */
export function formatJour(jour: string): string {
  const [annee, mois, date] = jour.split("-");
  return `${date}/${mois}/${annee}`;
}

/** Date d'émission : « sam. 24 oct. » cette année, « ven. 24 oct. 2025 » sinon. */
export function formatEmission(iso: string, maintenant: Date = new Date()): string {
  return formatDateCourteOuAnnee(iso, maintenant);
}

// --- Paiements (story S4.4) ---------------------------------------------------------------

export const STATUTS_PAIEMENT: StatutPaiement[] = ["impayee", "partielle", "payee"];

export const LIBELLE_PAIEMENT: Record<StatutPaiement, string> = {
  impayee: "Impayée",
  partielle: "Partiellement payée",
  payee: "Payée",
};

/** Badges du design system : anneau « attente », pastille « en-cours », pastille « pret ». */
export const BADGE_PAIEMENT: Record<StatutPaiement, BadgeStatus> = {
  impayee: "attente",
  partielle: "en-cours",
  payee: "pret",
};

/** Libellés des filtres de l'onglet Factures. */
export const FILTRES_PAIEMENT: { id: StatutPaiement | "toutes"; libelle: string }[] = [
  { id: "toutes", libelle: "Toutes" },
  { id: "impayee", libelle: "Impayées" },
  { id: "partielle", libelle: "Partielles" },
  { id: "payee", libelle: "Payées" },
];

/** « ?paiement=partielle » vers le filtre ; absent ou inconnu → toutes. */
export function filtrePaiement(valeur: string | string[] | undefined): StatutPaiement | "toutes" {
  return typeof valeur === "string" && (STATUTS_PAIEMENT as string[]).includes(valeur) ? (valeur as StatutPaiement) : "toutes";
}

/** Adresse de l'onglet Factures pour un filtre et une page. */
export function lienFactures(filtre: StatutPaiement | "toutes", page = 1): string {
  const params = new URLSearchParams();
  if (filtre !== "toutes") params.set("paiement", filtre);
  if (page > 1) params.set("page", String(page));
  const texte = params.toString();
  return texte ? `/factures?${texte}` : "/factures";
}

/** « carte » est le terminal du garage : aucune donnée de carte n'est saisie. */
export const LIBELLE_MODE: Record<ModePaiement, string> = {
  carte: "Carte bancaire (terminal)",
  especes: "Espèces",
  cheque: "Chèque",
  virement: "Virement",
};

export const MODES_PAIEMENT: ModePaiement[] = ["carte", "especes", "cheque", "virement"];

export const MESSAGE_MONTANT_INVALIDE = "Montant en euros, par exemple « 120,50 ».";
export const MESSAGE_MONTANT_NUL = "Le montant doit être supérieur à 0.";

export function messageTropPercu(resteCentimes: number): string {
  return `Le paiement dépasse le reste à payer (${formatEuros(resteCentimes)}).`;
}

/** Montant saisi pré-rempli : le reste à payer, « 168,00 ». */
export function montantSaisi(centimes: number): string {
  return (centimes / 100).toFixed(2).replace(".", ",");
}

/** Lecture du montant saisi : centimes, ou message d'erreur (même règle que l'API). */
export function lireMontant(saisie: string, resteCentimes: number): { centimes: number } | { erreur: string } {
  const centimes = parseEurosToCentimes(saisie);
  if (centimes === null) return { erreur: MESSAGE_MONTANT_INVALIDE };
  if (centimes <= 0) return { erreur: MESSAGE_MONTANT_NUL };
  if (centimes > resteCentimes) return { erreur: messageTropPercu(resteCentimes) };
  return { centimes };
}
