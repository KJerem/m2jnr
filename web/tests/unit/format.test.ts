import { describe, expect, it } from "vitest";
import { formatDateCourte, formatEuros, formatHeure, formatKm, parseEurosToCentimes } from "@/lib/format";

const normalise = (s: string) => s.replace(/[  ]/g, " ");

describe("format", () => {
  it("formate les montants en euros avec virgule et espace insécable", () => {
    expect(normalise(formatEuros(45480))).toBe("454,80 €");
    expect(normalise(formatEuros(284650))).toBe("2 846,50 €");
    expect(formatEuros(16800)).toContain(" €");
  });

  it("formate les heures à la française", () => {
    expect(normalise(formatHeure("2026-10-22T15:30:00Z"))).toBe("17 h 30");
    expect(normalise(formatHeure("2026-10-22T07:05:00Z"))).toBe("9 h 05");
  });

  it("formate les dates courtes", () => {
    expect(formatDateCourte("2026-10-14T10:00:00Z")).toBe("mer. 14 oct.");
  });

  it("formate le kilométrage", () => {
    expect(normalise(formatKm(84312))).toBe("84 312 km");
  });

  it("convertit une saisie en centimes sans erreur d'arrondi", () => {
    expect(parseEurosToCentimes("48,50")).toBe(4850);
    expect(parseEurosToCentimes("0.1")).toBe(10);
    expect(parseEurosToCentimes("72")).toBe(7200);
    expect(parseEurosToCentimes("1 234,56 €")).toBe(123456);
    expect(parseEurosToCentimes("-3")).toBeNull();
    expect(parseEurosToCentimes("12,345")).toBeNull();
    expect(parseEurosToCentimes("abc")).toBeNull();
  });
});
