/**
 * Parcours du mécanicien (recette du sprint 4) : « Mes travaux » → vue tablette d'un OT qui
 * lui est affecté → tâches cochées → « Terminer l'intervention » → « Prêt » ; les factures lui
 * sont refusées (page 403) et son menu n'a pas « Devis & factures ».
 *
 * L'OT est créé par l'API (comme le gérant) avant le test : le parcours ne dépend pas de
 * l'état des données de démonstration.
 */
import { expect, test } from "@playwright/test";
import { Api, creerOrdre, GERANT, MECANICIEN, seConnecter, type OrdreCree } from "./outils";

let ordre: OrdreCree;

test.beforeAll(async () => {
  const api = await Api.connecter(GERANT);
  const mecaniciens = await api.get<{ id: number; email?: string; nom: string }[]>("/api/mecaniciens");
  const karim = mecaniciens.find((m) => m.nom === "Karim B.");
  expect(karim, "le compte de démonstration Karim B. doit exister (seed)").toBeDefined();
  ordre = await creerOrdre(api, { decalage: 101, mecanicienId: karim!.id, taches: ["Contrôle des niveaux", "Pression des pneus"] });
  await api.fermer();
});

test("parcours du mécanicien : tablette, tâches, « Prêt », factures refusées", async ({ page }) => {
  await seConnecter(page, MECANICIEN);

  await test.step("« Mes travaux » montre l'OT affecté", async () => {
    await expect(page.getByRole("heading", { level: 1, name: "Mes travaux" })).toBeVisible();
    await page.getByRole("link", { name: new RegExp(ordre.numero) }).click();
    await expect(page).toHaveURL(new RegExp(`/ordres/${ordre.id}/tablette$`));
  });

  await test.step("vue tablette : démarrer, cocher les tâches, terminer", async () => {
    await page.getByRole("button", { name: "Démarrer l'intervention" }).click();
    const terminer = page.getByRole("button", { name: "Terminer l'intervention" });
    await expect(terminer).toBeDisabled();
    // Cases contrôlées par la réponse de l'API : on touche la case, puis on attend l'état coché.
    for (const tache of ["Contrôle des niveaux", "Pression des pneus"]) {
      await page.getByLabel(tache).click();
      await expect(page.getByLabel(tache)).toBeChecked();
    }
    await expect(terminer).toBeEnabled();
    await terminer.click();
    await expect(page.locator(".et-status").filter({ hasText: "Prêt" }).first()).toBeVisible();
    await expect(page.getByRole("button", { name: "Terminer l'intervention" })).toHaveCount(0);
  });

  await test.step("les factures lui sont refusées et son menu ne les propose pas", async () => {
    const menu = page.getByRole("navigation", { name: "Navigation principale" });
    await expect(menu.getByRole("link", { name: "Devis & factures" })).toHaveCount(0);
    await page.goto("/factures");
    await expect(page.getByRole("heading", { level: 1, name: "Accès refusé" })).toBeVisible();
    await expect(page.getByText(/154,92|€ TTC/)).toHaveCount(0);
  });
});
