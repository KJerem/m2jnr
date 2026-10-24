/** Rendez-vous et planning : types de l'API, formulaire (mêmes règles que l'API) et formats. */
import { z } from "zod";
import { formatDateCourte, formatHeure, TIMEZONE } from "./format";
import type { ClientOrdre, OrdreResume, VehiculeOrdre } from "./ordres";
import type { StatutOT } from "./statuts";
import { aujourdHui } from "./vehicules";

export interface Pont {
  id: number;
  nom: string;
}

export interface RendezVous {
  id: number;
  debut: string;
  fin: string;
  duree_minutes: number;
  motif: string;
  pont: Pont;
  vehicule: VehiculeOrdre;
  client: ClientOrdre;
  ordre: { id: number; numero: string; statut: StatutOT } | null;
}

export interface ElementPlanning {
  type: "rendez_vous" | "ordre";
  /** Début du créneau ; pour un report, minuit du jour affiché (le report vient en tête). */
  heure: string;
  rendez_vous: RendezVous;
  ordre: OrdreResume | null;
  /** Rendez-vous d'un jour précédent dont l'OT n'est pas livré : le véhicule est encore sur le pont. */
  report: boolean;
}

export interface PontPlanning extends Pont {
  charge_minutes: number;
  capacite_minutes: number;
  elements: ElementPlanning[];
}

export interface Planning {
  jour: string;
  ponts: PontPlanning[];
  a_planifier: OrdreResume[];
}

export interface RendezVousEntree {
  vehicule_id: number;
  pont_id: number;
  /** « 2026-11-19T09:00 », lu à l'heure de Paris par l'API. */
  debut: string;
  duree_minutes: number;
  motif: string;
}

export const MESSAGE_PASSE = "Impossible de prendre un rendez-vous dans le passé.";
export const MESSAGE_OBLIGATOIRE = "Champ obligatoire.";

/** Durées proposées : de 30 min à 8 h, par demi-heure. */
export const DUREES_RDV = Array.from({ length: 16 }, (_, i) => (i + 1) * 30);

/** Heure courante à Paris au format des champs time : « 14:47 ». */
export function heureCourante(maintenant: Date = new Date()): string {
  return new Intl.DateTimeFormat("en-GB", { timeZone: TIMEZONE, hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(maintenant);
}

/** Vrai si le jour et l'heure saisis (heure de Paris) sont déjà passés. */
export function estDansLePasse(jour: string, heure: string, maintenant: Date = new Date()): boolean {
  return `${jour}T${heure}` < `${aujourdHui(maintenant)}T${heureCourante(maintenant)}`;
}

export function creerSchemaRendezVous(maintenant: () => Date = () => new Date()) {
  return z
    .object({
      vehicule_id: z.string().min(1, MESSAGE_OBLIGATOIRE),
      pont_id: z.string().min(1, MESSAGE_OBLIGATOIRE),
      jour: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, MESSAGE_OBLIGATOIRE),
      heure: z.string().regex(/^([01]\d|2[0-3]):[0-5]\d$/, MESSAGE_OBLIGATOIRE),
      duree_minutes: z.string().refine((v) => DUREES_RDV.includes(Number(v)), MESSAGE_OBLIGATOIRE),
      motif: z.string().trim().min(1, MESSAGE_OBLIGATOIRE).max(500, "500 caractères maximum."),
    })
    .superRefine((v, ctx) => {
      if (/^\d{4}-\d{2}-\d{2}$/.test(v.jour) && /^\d{2}:\d{2}$/.test(v.heure) && estDansLePasse(v.jour, v.heure, maintenant())) {
        ctx.addIssue({ code: "custom", path: ["jour"], message: MESSAGE_PASSE });
      }
    });
}

export type RendezVousFormValues = z.infer<ReturnType<typeof creerSchemaRendezVous>>;

export const RENDEZ_VOUS_VIDE: RendezVousFormValues = { vehicule_id: "", pont_id: "", jour: "", heure: "", duree_minutes: "60", motif: "" };

export function versEntreeRendezVous(v: RendezVousFormValues): RendezVousEntree {
  return {
    vehicule_id: Number(v.vehicule_id),
    pont_id: Number(v.pont_id),
    debut: `${v.jour}T${v.heure}`,
    duree_minutes: Number(v.duree_minutes),
    motif: v.motif.trim(),
  };
}

/** « 9 h 00 – 10 h 30 ». */
export function formatCreneau(debut: string, fin: string): string {
  return `${formatHeure(debut)} – ${formatHeure(fin)}`;
}

/** Créneau d'un report : « Reporté du mar. 3 nov. (9 h 00 – 10 h 00) ». */
export function libelleReport(rdv: Pick<RendezVous, "debut" | "fin">): string {
  return `Reporté du ${formatDateCourte(rdv.debut)} (${formatCreneau(rdv.debut, rdv.fin)})`;
}

/**
 * Jour du planning à lire pour « Ensuite sur ce pont » : celui du rendez-vous, ou aujourd'hui
 * si le rendez-vous date d'un jour précédent (l'OT y figure alors en report).
 */
export function jourDuPont(debutRendezVous: string, maintenant: Date = new Date()): string {
  const jourRdv = aujourdHui(new Date(debutRendezVous));
  const jour = aujourdHui(maintenant);
  return jourRdv > jour ? jourRdv : jour;
}

/** Jour « AAAA-MM-JJ » vers « jeu. 22 oct. » (midi UTC : le même jour à Paris). */
export function formatJour(jour: string): string {
  return formatDateCourte(`${jour}T12:00:00Z`);
}

/** Jour décalé de n jours, en arithmétique de calendrier (sans effet des changements d'heure). */
export function decalerJour(jour: string, n: number): string {
  const [a, m, j] = jour.split("-").map(Number);
  const d = new Date(Date.UTC(a ?? 1970, (m ?? 1) - 1, (j ?? 1) + n));
  return d.toISOString().slice(0, 10);
}

/** Rendez-vous groupés par jour de Paris, dans l'ordre reçu (déjà trié par heure). */
export function grouperParJour(rendezVous: RendezVous[]): { jour: string; rendezVous: RendezVous[] }[] {
  const groupes: { jour: string; rendezVous: RendezVous[] }[] = [];
  for (const r of rendezVous) {
    const jour = aujourdHui(new Date(r.debut));
    const dernier = groupes[groupes.length - 1];
    if (dernier && dernier.jour === jour) dernier.rendezVous.push(r);
    else groupes.push({ jour, rendezVous: [r] });
  }
  return groupes;
}

/** Élément suivant sur le même pont, après le créneau donné (« Ensuite sur ce pont »). */
export function elementSuivant(planning: Planning | undefined, pontId: number, rendezVousId: number): ElementPlanning | null {
  const pont = planning?.ponts.find((p) => p.id === pontId);
  if (!pont) return null;
  const courant = pont.elements.find((e) => e.rendez_vous.id === rendezVousId);
  if (!courant) return null;
  // Pas de chevauchement sur un pont : le suivant est le premier qui commence après.
  const debutCourant = new Date(courant.heure).getTime();
  return pont.elements.find((e) => new Date(e.heure).getTime() > debutCourant) ?? null;
}
