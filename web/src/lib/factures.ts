/** Factures (story S4.3) : types de l'API et règles d'affichage. */
import type { LigneDevis, TotauxDevis } from "./devis";
import { formatDateAnnee, formatDateCourte } from "./format";
import { aujourdHui } from "./vehicules";
import type { StatutOT } from "./statuts";

export interface FactureResume {
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

export const MESSAGE_FACTURE_INDISPONIBLE = "Disponible quand l'intervention est « Prêt ».";

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
  return aujourdHui(new Date(iso)).slice(0, 4) === aujourdHui(maintenant).slice(0, 4) ? formatDateCourte(iso) : formatDateAnnee(iso);
}
