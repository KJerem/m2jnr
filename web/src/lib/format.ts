/** Formats d'affichage du design system : « 454,80 € », « 17 h 30 », « mar. 14 oct. ». */

export const TIMEZONE = "Europe/Paris";
const NBSP = " ";
const NNBSP = " ";

const euro = new Intl.NumberFormat("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** Centimes (entier) vers « 1 234,50 € » avec espaces insécables. */
export function formatEuros(centimes: number): string {
  // Intl utilise U+202F comme séparateur de milliers en fr-FR : on le garde, il est insécable.
  return `${euro.format(centimes / 100)}${NBSP}€`;
}

/** Saisie « 48,5 » ou « 48.50 » vers centimes (entier), ou null si invalide. */
export function parseEurosToCentimes(input: string): number | null {
  const clean = input.replace(/[\s  €]/g, "").replace(",", ".");
  if (!/^\d+(\.\d{1,2})?$/.test(clean)) return null;
  const [entier, decimales = ""] = clean.split(".");
  return Number(entier) * 100 + Number(decimales.padEnd(2, "0"));
}

function parts(date: Date | string, options: Intl.DateTimeFormatOptions) {
  const d = typeof date === "string" ? new Date(date) : date;
  return new Intl.DateTimeFormat("fr-FR", { timeZone: TIMEZONE, ...options }).formatToParts(d);
}

function part(list: Intl.DateTimeFormatPart[], type: Intl.DateTimeFormatPartTypes) {
  return list.find((p) => p.type === type)?.value ?? "";
}

/** « 17 h 30 » ; « 9 h 05 ». */
export function formatHeure(date: Date | string): string {
  const p = parts(date, { hour: "numeric", minute: "2-digit", hour12: false });
  return `${Number(part(p, "hour"))}${NBSP}h${NBSP}${part(p, "minute")}`;
}

/** « mar. 14 oct. ». */
export function formatDateCourte(date: Date | string): string {
  const p = parts(date, { weekday: "short", day: "numeric", month: "short" });
  return `${part(p, "weekday")} ${part(p, "day")} ${part(p, "month")}`.replace(/\s+/g, " ").trim();
}

/** « mar. 14 oct. à 17 h 30 ». */
export function formatDateHeure(date: Date | string): string {
  return `${formatDateCourte(date)} à ${formatHeure(date)}`;
}

/** « 14/10/2026 ». */
export function formatDate(date: Date | string): string {
  return new Intl.DateTimeFormat("fr-FR", { timeZone: TIMEZONE, day: "2-digit", month: "2-digit", year: "numeric" }).format(
    typeof date === "string" ? new Date(date) : date,
  );
}

/** « 84 312 km ». */
export function formatKm(km: number): string {
  return `${new Intl.NumberFormat("fr-FR").format(km)}${NBSP}km`;
}

/** Durée en minutes vers « 1,5 h ». */
export function formatDureeHeures(minutes: number): string {
  return `${new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 2 }).format(minutes / 60)}${NBSP}h`;
}

/** « 0612345678 » vers « 06 12 34 56 78 » (espaces insécables : le numéro ne se coupe pas). */
export function formatTelephone(telephone: string): string {
  return /^\d{10}$/.test(telephone) ? (telephone.match(/\d{2}/g) ?? []).join(NBSP) : telephone;
}

/** « Laurent », « Claire » vers « Claire Laurent ». */
export function nomComplet(personne: { nom: string; prenom?: string | null }): string {
  return [personne.prenom, personne.nom].filter(Boolean).join(" ");
}

export { NBSP, NNBSP };
