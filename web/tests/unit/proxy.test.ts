import { describe, expect, it } from "vitest";
import { config } from "@/proxy";

// Le matcher de Next suit la syntaxe path-to-regexp ; ce motif-ci est une expression régulière
// pure, on le vérifie donc tel quel sur le chemin complet.
const motif = new RegExp(`^${config.matcher[0]}$`);

describe("aiguillage du proxy", () => {
  it("passe par l'aiguillage de session pour les pages", () => {
    for (const chemin of ["/", "/clients", "/clients/12", "/vehicules/3", "/connexion"]) {
      expect(motif.test(chemin), chemin).toBe(true);
    }
  });

  it("laisse passer l'API, tout /_next et les fichiers statiques", () => {
    for (const chemin of ["/api/auth/me", "/_next/static/chunks/app.js", "/_next/image", "/_next/webpack-hmr", "/favicon.ico", "/logo.svg"]) {
      expect(motif.test(chemin), chemin).toBe(false);
    }
  });
});
