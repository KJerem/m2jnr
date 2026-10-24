/**
 * Devis (story S4.1) : types de l'API, formulaire et calcul en direct.
 *
 * Le calcul reprend exactement la règle de l'API (app/services/calcul_devis.py) en entiers :
 * quantité en centièmes, prix en centimes, total de ligne = arrondi au centime (le demi-centime
 * monte), TVA arrondie au centime, TTC = HT + TVA. Aucun nombre à virgule flottante : les
 * produits passent par BigInt. Les totaux affichés après l'enregistrement sont ceux de l'API.
 */
import { z } from "zod";
import { formatEuros, NBSP, parseEurosToCentimes } from "./format";
import type { StatutOT } from "./statuts";

export type TypeLigne = "piece" | "main_oeuvre";

export const LIBELLE_TYPE_LIGNE: Record<TypeLigne, string> = {
  main_oeuvre: "Main-d'œuvre",
  piece: "Pièce",
};

export interface LigneDevis {
  id: number;
  type: TypeLigne;
  reference: string | null;
  designation: string;
  /** Texte à deux décimales : « 0.50 ». */
  quantite: string;
  prix_unitaire_ht_centimes: number;
  total_ht_centimes: number;
  position: number;
}

export interface TotauxDevis {
  main_oeuvre_ht_centimes: number;
  pieces_ht_centimes: number;
  total_ht_centimes: number;
  total_tva_centimes: number;
  total_ttc_centimes: number;
}

export interface FactureLien {
  id: number;
  numero: string;
}

export interface DevisDetail {
  id: number;
  ordre: { id: number; numero: string; statut: StatutOT };
  lignes: LigneDevis[];
  taux_tva_bp: number;
  totaux: TotauxDevis;
  cree_le: string;
  modifie_le: string;
  facture: FactureLien | null;
}

export interface DevisResume {
  id: number;
  ordre: { id: number; numero: string; statut: StatutOT };
  vehicule: { id: number; immatriculation: string; marque: string; modele: string; kilometrage: number };
  client: { id: number; nom: string; prenom: string | null };
  total_ht_centimes: number;
  total_ttc_centimes: number;
  cree_le: string;
  modifie_le: string;
  facture: FactureLien | null;
}

/** Corps de POST /ordres/{id}/devis et PUT /devis/{id}. */
export interface DevisEntree {
  lignes: { type: TypeLigne; reference: string | null; designation: string; quantite: string; prix_unitaire_ht_centimes: number }[];
}

export const TAUX_TVA_NORMAL_BP = 2000;
export const LIGNES_MAX = 100;
export const QUANTITE_MAX_CENTIEMES = 999_999;
export const PRIX_UNITAIRE_MAX_CENTIMES = 10_000_000;

export const MESSAGE_QUANTITE_INVALIDE = "Quantité invalide : nombre attendu, par exemple 1 ou 0,5.";
export const MESSAGE_QUANTITE_POSITIVE = "La quantité doit être supérieure à 0.";
export const MESSAGE_QUANTITE_MAX = "La quantité ne peut pas dépasser 9 999,99.";
export const MESSAGE_QUANTITE_DECIMALES = "Deux décimales au plus pour la quantité.";
export const MESSAGE_PRIX_INVALIDE = "Prix invalide : montant en euros, par exemple 48,50.";
export const MESSAGE_PRIX_MAX = "100 000,00 € HT au plus.";
export const MESSAGE_LIGNES_VIDES = "Le devis doit contenir au moins une ligne.";

export type LectureQuantite = { ok: true; centiemes: number } | { ok: false; message: string };

/** « 0,5 », « 1.50 », « 2 » vers des centièmes (50, 150, 200) ; mêmes refus que l'API. */
export function lireQuantite(saisie: string): LectureQuantite {
  const texte = saisie.replace(/[\s  ]/g, "").replace(",", ".");
  const negative = /^-\d+(\.\d+)?$/.test(texte);
  if (negative) return { ok: false, message: MESSAGE_QUANTITE_POSITIVE };
  const morceaux = /^(\d+)(?:\.(\d+))?$/.exec(texte);
  if (!morceaux || texte.length > 32) return { ok: false, message: MESSAGE_QUANTITE_INVALIDE };
  const entier = (morceaux[1] ?? "").replace(/^0+(?=\d)/, "");
  // « 1.500 » vaut 1,50 : seuls les zéros finaux au-delà de deux décimales sont tolérés.
  const decimales = (morceaux[2] ?? "").replace(/0+$/, "");
  if (decimales.length > 2) return { ok: false, message: MESSAGE_QUANTITE_DECIMALES };
  if (entier.length > 4) return { ok: false, message: MESSAGE_QUANTITE_MAX };
  const centiemes = Number(entier) * 100 + Number(decimales.padEnd(2, "0"));
  if (centiemes <= 0) return { ok: false, message: MESSAGE_QUANTITE_POSITIVE };
  if (centiemes > QUANTITE_MAX_CENTIEMES) return { ok: false, message: MESSAGE_QUANTITE_MAX };
  return { ok: true, centiemes };
}

/** Division entière arrondie au plus proche, 0,5 vers le haut (valeurs positives). */
function diviserArrondi(numerateur: bigint, diviseur: bigint): bigint {
  return (numerateur * BigInt(2) + diviseur) / (diviseur * BigInt(2));
}

/** Quantité (centièmes) × PU HT (centimes), arrondi au centime : 125 × 999 → 1 249 (12,4875 € → 12,49 €). */
export function totalLigne(quantiteCentiemes: number, prixUnitaireCentimes: number): number {
  return Number(diviserArrondi(BigInt(quantiteCentiemes) * BigInt(prixUnitaireCentimes), BigInt(100)));
}

/** TVA arrondie au centime ; taux en points de base (2000 = 20 %). */
export function tva(totalHtCentimes: number, tauxBp: number): number {
  return Number(diviserArrondi(BigInt(totalHtCentimes) * BigInt(tauxBp), BigInt(10_000)));
}

export interface LigneCalcul {
  type: TypeLigne;
  quantiteCentiemes: number;
  prixUnitaireCentimes: number;
}

export function calculerTotaux(lignes: LigneCalcul[], tauxBp: number = TAUX_TVA_NORMAL_BP): TotauxDevis {
  let mainOeuvre = 0;
  let pieces = 0;
  for (const ligne of lignes) {
    const montant = totalLigne(ligne.quantiteCentiemes, ligne.prixUnitaireCentimes);
    if (ligne.type === "main_oeuvre") mainOeuvre += montant;
    else pieces += montant;
  }
  const ht = mainOeuvre + pieces;
  const montantTva = tva(ht, tauxBp);
  return { main_oeuvre_ht_centimes: mainOeuvre, pieces_ht_centimes: pieces, total_ht_centimes: ht, total_tva_centimes: montantTva, total_ttc_centimes: ht + montantTva };
}

const nombre = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 2 });
const nombreSaisie = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 2, useGrouping: false });

/** Quantité de l'API vers un champ de saisie : « 0.50 » → « 0,5 ». */
export function quantiteVersSaisie(quantite: string): string {
  const lecture = lireQuantite(quantite);
  return lecture.ok ? nombreSaisie.format(lecture.centiemes / 100) : quantite;
}

/** Quantité pour l'affichage : « 0,5 h » pour la main-d'œuvre, « 1 » pour une pièce. */
export function formatQuantite(type: TypeLigne, quantite: string): string {
  const lecture = lireQuantite(quantite);
  const valeur = lecture.ok ? nombre.format(lecture.centiemes / 100) : quantite;
  return type === "main_oeuvre" ? `${valeur}${NBSP}h` : valeur;
}

/** « TVA 20 % » (taux en points de base). */
export function libelleTva(tauxBp: number): string {
  return `TVA ${nombre.format(tauxBp / 100)}${NBSP}%`;
}

/** Montant sans le symbole, pour un champ de saisie : 4850 → « 48,50 ». */
export function centimesVersSaisie(centimes: number): string {
  return formatEuros(centimes).replace(/\s?€$/, "").replace(/[\s  ]/g, "");
}

// --- Formulaire ----------------------------------------------------------------------------

export const ligneSchema = z.object({
  type: z.enum(["piece", "main_oeuvre"]),
  reference: z.string().trim().max(40, "40 caractères maximum."),
  designation: z.string().trim().min(1, "Champ obligatoire.").max(200, "200 caractères maximum."),
  quantite: z.string().superRefine((valeur, ctx) => {
    if (!valeur.trim()) {
      ctx.addIssue({ code: "custom", message: "Champ obligatoire." });
      return;
    }
    const lecture = lireQuantite(valeur);
    if (!lecture.ok) ctx.addIssue({ code: "custom", message: lecture.message });
  }),
  prix: z.string().superRefine((valeur, ctx) => {
    if (!valeur.trim()) {
      ctx.addIssue({ code: "custom", message: "Champ obligatoire." });
      return;
    }
    const centimes = parseEurosToCentimes(valeur);
    if (centimes === null) ctx.addIssue({ code: "custom", message: MESSAGE_PRIX_INVALIDE });
    else if (centimes > PRIX_UNITAIRE_MAX_CENTIMES) ctx.addIssue({ code: "custom", message: MESSAGE_PRIX_MAX });
  }),
});

export const devisSchema = z.object({
  lignes: z.array(ligneSchema).min(1, MESSAGE_LIGNES_VIDES).max(LIGNES_MAX, `${LIGNES_MAX} lignes au plus par devis.`),
});

export type DevisFormValues = z.infer<typeof devisSchema>;
export type LigneFormValues = DevisFormValues["lignes"][number];

export const LIGNE_VIDE: LigneFormValues = { type: "piece", reference: "", designation: "", quantite: "1", prix: "" };

/** Champs du formulaire et noms correspondants dans les erreurs de l'API (« lignes.0.quantite »). */
export const CHAMP_API: Record<keyof LigneFormValues, string> = {
  type: "type",
  reference: "reference",
  designation: "designation",
  quantite: "quantite",
  prix: "prix_unitaire_ht_centimes",
};

export function versFormulaireDevis(devis: DevisDetail | null): DevisFormValues {
  if (!devis) return { lignes: [] };
  return {
    lignes: devis.lignes.map((l) => ({
      type: l.type,
      reference: l.reference ?? "",
      designation: l.designation,
      quantite: quantiteVersSaisie(l.quantite),
      prix: centimesVersSaisie(l.prix_unitaire_ht_centimes),
    })),
  };
}

/** Ligne saisie vers les nombres du calcul, ou null tant qu'elle est incomplète ou invalide. */
export function ligneCalculable(ligne: Partial<LigneFormValues> | undefined): LigneCalcul | null {
  if (!ligne?.type) return null;
  const quantite = lireQuantite(ligne.quantite ?? "");
  const prix = parseEurosToCentimes(ligne.prix ?? "");
  if (!quantite.ok || prix === null || prix > PRIX_UNITAIRE_MAX_CENTIMES) return null;
  return { type: ligne.type, quantiteCentiemes: quantite.centiemes, prixUnitaireCentimes: prix };
}

export function versEntreeDevis(valeurs: DevisFormValues): DevisEntree {
  return {
    lignes: valeurs.lignes.map((l) => {
      const quantite = lireQuantite(l.quantite);
      const centiemes = quantite.ok ? quantite.centiemes : 0;
      return {
        type: l.type,
        reference: l.reference.trim() || null,
        designation: l.designation.trim(),
        // Texte décimal exact (« 0.50 ») : l'API le lit en Decimal, sans flottant.
        quantite: `${Math.floor(centiemes / 100)}.${String(centiemes % 100).padStart(2, "0")}`,
        prix_unitaire_ht_centimes: parseEurosToCentimes(l.prix) ?? 0,
      };
    }),
  };
}
