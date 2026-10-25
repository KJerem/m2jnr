/**
 * Données uniques des parcours de recette (fonctions pures, testées par Vitest).
 *
 * L'identifiant de l'exécution est tiré UNE fois, au chargement du module (E2E_EXECUTION
 * s'il est fourni, sinon au hasard) ; chaque fichier de test a ses propres numéros de donnée
 * (gérant 0, mécanicien 101, accessibilité 201 et 202). Plaque, téléphone et nom viennent de
 * « exécution × 1000 + donnée », sans l'horloge : deux fichiers lancés à quelques secondes
 * d'écart ne peuvent plus tomber sur la même plaque (unique en base).
 */

// Lettres du SIV (sans I, O ni U).
const LETTRES = "ABCDEFGHJKLMNPQRSTVWXYZ";
/** 100 000 exécutions possibles × 1 000 données : moins de 10⁸, donc un téléphone distinct par
 * donnée, et moins de 999 × 23⁴ plaques. */
const EXECUTIONS = 100_000;
const DONNEES_PAR_EXECUTION = 1_000;

/** E2E_EXECUTION (entier de 0 à 99 999) s'il est valide, sinon un tirage au hasard. */
export function lireExecution(valeur: string | undefined, aleatoire: () => number = Math.random): number {
  const lu = Number(valeur);
  if (valeur !== undefined && Number.isInteger(lu) && lu >= 0 && lu < EXECUTIONS) return lu;
  return Math.floor(aleatoire() * EXECUTIONS);
}

export const EXECUTION = lireExecution(process.env.E2E_EXECUTION);

/** Numéro unique d'une donnée de l'exécution (0 ≤ donnée < 1 000). */
export function numeroExecution(donnee = 0, execution = EXECUTION): number {
  return execution * DONNEES_PAR_EXECUTION + (donnee % DONNEES_PAR_EXECUTION);
}

/** Plaque SIV valide et unique, « AB-123-CD ». */
export function plaqueUnique(donnee = 0, execution = EXECUTION): string {
  let n = numeroExecution(donnee, execution);
  const chiffres = String((n % 999) + 1).padStart(3, "0");
  n = Math.floor(n / 999);
  const lettres: string[] = [];
  for (let i = 0; i < 4; i += 1) {
    lettres.push(LETTRES[n % LETTRES.length]!);
    n = Math.floor(n / LETTRES.length);
  }
  return `${lettres[0]}${lettres[1]}-${chiffres}-${lettres[2]}${lettres[3]}`;
}

/** Téléphone unique « 07xxxxxxxx » (pas d'alerte de doublon). */
export function telephoneUnique(donnee = 0, execution = EXECUTION): string {
  return `07${String(numeroExecution(donnee, execution)).padStart(8, "0")}`;
}

/** Minutes depuis minuit à Paris. */
function minutesParis(iso: string): number {
  const parts = new Intl.DateTimeFormat("fr-FR", { timeZone: "Europe/Paris", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).formatToParts(new Date(iso));
  const valeur = (type: string) => Number(parts.find((p) => p.type === type)?.value ?? 0);
  return valeur("hour") * 60 + valeur("minute");
}

/**
 * Premier créneau « HH:MM » (de 8 h 00 à 18 h 00, par demi-heure) où un rendez-vous de
 * `dureeMinutes` ne chevauche aucun des rendez-vous du pont ce jour-là ; null si la journée
 * est pleine.
 */
export function premierCreneauLibre(occupes: { debut: string; fin: string }[], dureeMinutes: number): string | null {
  const plages = occupes.map((r) => [minutesParis(r.debut), minutesParis(r.fin)] as const);
  for (let debut = 8 * 60; debut + dureeMinutes <= 18 * 60; debut += 30) {
    const fin = debut + dureeMinutes;
    if (plages.every(([d, f]) => fin <= d || debut >= f)) {
      return `${String(Math.floor(debut / 60)).padStart(2, "0")}:${String(debut % 60).padStart(2, "0")}`;
    }
  }
  return null;
}
