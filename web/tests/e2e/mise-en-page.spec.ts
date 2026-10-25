/**
 * Mise en page à 1024 px (règle « utilisable à 1024 px ») et sur grand écran, en thème clair
 * et en thème sombre (revue du sprint 4) :
 * - onglets Devis et Factures : le tableau tient dans son cadre, la page ne défile pas à
 *   l'horizontale, les numéros d'OT et de facture et les plaques restent sur une ligne ;
 * - tableau de bord : le champ « Rechercher » et « Nouvelle intervention » sur une même
 *   ligne (maquette 4).
 */
import { expect, test, type Page } from "@playwright/test";
import { GERANT, seConnecter } from "./outils";

const THEMES = ["light", "dark"] as const;

interface Mesures {
  pageDefile: boolean;
  tableau: number;
  cadre: number;
  coupes: string[];
}

/** Largeurs du tableau et de son cadre, défilement de la page, textes coupés sur plusieurs
 * lignes parmi les numéros (« OT-2026-003 », « F-2026-001 ») et les plaques. */
async function mesurer(page: Page): Promise<Mesures> {
  await expect(page.locator(".table-wrap table tbody tr").first()).toBeVisible();
  return page.evaluate(() => {
    const cadre = document.querySelector<HTMLElement>(".table-wrap")!;
    const coupes: string[] = [];
    for (const cellule of document.querySelectorAll<HTMLElement>(".table-wrap td a, .table-wrap .et-plate-num")) {
      const parcours = document.createTreeWalker(cellule, NodeFilter.SHOW_TEXT);
      for (let noeud = parcours.nextNode(); noeud; noeud = parcours.nextNode()) {
        const texte = noeud.textContent?.trim() ?? "";
        if (!/^(OT|F)-\d{4}-\d+$|^[A-Z]{2}-\d{3}-[A-Z]{2}$/.test(texte)) continue;
        const plage = document.createRange();
        plage.selectNodeContents(noeud);
        if (plage.getClientRects().length > 1) coupes.push(texte);
      }
    }
    return {
      pageDefile: document.documentElement.scrollWidth > document.documentElement.clientWidth,
      tableau: cadre.querySelector("table")!.scrollWidth,
      cadre: cadre.clientWidth,
      coupes,
    };
  });
}

for (const theme of THEMES) {
  test.describe(`thème ${theme === "light" ? "clair" : "sombre"}`, () => {
    test.use({ colorScheme: theme });

    for (const largeur of [1024, 1440]) {
      test(`onglets Devis et Factures sans défilement horizontal à ${largeur} px`, async ({ page }) => {
        await page.setViewportSize({ width: largeur, height: 900 });
        await seConnecter(page, GERANT);
        for (const chemin of ["/factures", "/devis"]) {
          await page.goto(chemin);
          const mesures = await mesurer(page);
          expect(mesures.pageDefile, `${chemin} : la page défile à l'horizontale`).toBe(false);
          expect(mesures.tableau, `${chemin} : le tableau dépasse son cadre`).toBeLessThanOrEqual(mesures.cadre);
          expect(mesures.coupes, `${chemin} : numéros ou plaques coupés`).toEqual([]);
        }
      });

      test(`tableau de bord : recherche et « Nouvelle intervention » sur une ligne à ${largeur} px`, async ({ page }) => {
        await page.setViewportSize({ width: largeur, height: 900 });
        await seConnecter(page, GERANT);
        await page.goto("/");
        const champ = page.getByRole("searchbox", { name: "Rechercher" });
        const bouton = page.getByRole("link", { name: "Nouvelle intervention" });
        await expect(bouton).toBeVisible();
        const [boiteChamp, boiteBouton] = await Promise.all([champ.boundingBox(), bouton.boundingBox()]);
        // Même ligne : le bouton commence à droite du champ, et leurs bas sont alignés.
        expect(boiteBouton!.x).toBeGreaterThan(boiteChamp!.x + boiteChamp!.width);
        expect(Math.abs(boiteBouton!.y + boiteBouton!.height - (boiteChamp!.y + boiteChamp!.height))).toBeLessThanOrEqual(2);
        if (largeur >= 1440) {
          // Grand écran : à droite du titre, sur sa ligne, comme la maquette 4.
          const titre = (await page.getByRole("heading", { level: 1 }).boundingBox())!;
          expect(boiteChamp!.x).toBeGreaterThan(titre.x + titre.width);
          expect(boiteBouton!.y).toBeLessThan(titre.y + titre.height);
        }
        expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false);
      });
    }
  });
}
