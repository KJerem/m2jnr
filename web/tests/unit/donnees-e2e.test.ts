import { afterEach, describe, expect, it, vi } from "vitest";
import * as donnees from "../e2e/donnees";

const { plaqueUnique, telephoneUnique } = donnees;

/** Données des fichiers de recette : gérant 0, mécanicien 101, accessibilité 201 et 202. */
const DONNEES = [0, 101, 201, 202];

afterEach(() => {
  vi.useRealTimers();
});

describe("données uniques des parcours de recette", () => {
  it("ne dépendent pas de l'heure d'appel : deux fichiers lancés à 100 s d'écart ne se croisent pas", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-12-14T09:00:00Z"));
    const accessibilite = { plaque: plaqueUnique(201), telephone: telephoneUnique(201) };
    vi.setSystemTime(new Date("2026-12-14T09:01:40Z"));
    expect(plaqueUnique(101)).not.toBe(accessibilite.plaque);
    expect(telephoneUnique(101)).not.toBe(accessibilite.telephone);
    // Et une même donnée garde sa valeur pendant toute l'exécution.
    expect(plaqueUnique(201)).toBe(accessibilite.plaque);
  });

  it("sont distinctes d'une donnée à l'autre, plaques SIV et téléphones valides", () => {
    const plaques = DONNEES.map((d) => plaqueUnique(d));
    const telephones = DONNEES.map((d) => telephoneUnique(d));
    expect(new Set(plaques).size).toBe(DONNEES.length);
    expect(new Set(telephones).size).toBe(DONNEES.length);
    for (const plaque of plaques) expect(plaque).toMatch(/^[A-HJ-NP-TV-Z]{2}-\d{3}-[A-HJ-NP-TV-Z]{2}$/);
    for (const telephone of telephones) expect(telephone).toMatch(/^07\d{8}$/);
  });

  it("distinguent deux exécutions, et E2E_EXECUTION fixe l'identifiant", () => {
    expect(donnees.lireExecution("4242")).toBe(4242);
    expect(donnees.lireExecution(undefined, () => 0.5)).toBe(50_000);
    expect(donnees.lireExecution("pas un nombre", () => 0)).toBe(0);
    expect(donnees.plaqueUnique(0, 1)).not.toBe(donnees.plaqueUnique(0, 2));
    expect(donnees.telephoneUnique(0, 1)).not.toBe(donnees.telephoneUnique(0, 2));
  });

  it("choisit le premier créneau libre du pont, sinon aucun", () => {
    const jour = "2027-01-12";
    const rdv = (debut: string, fin: string) => ({ debut: `${jour}T${debut}:00+01:00`, fin: `${jour}T${fin}:00+01:00` });
    expect(donnees.premierCreneauLibre([], 60)).toBe("08:00");
    expect(donnees.premierCreneauLibre([rdv("08:00", "09:00"), rdv("09:30", "10:30")], 60)).toBe("10:30");
    expect(donnees.premierCreneauLibre([rdv("08:00", "18:00")], 60)).toBeNull();
  });
});
