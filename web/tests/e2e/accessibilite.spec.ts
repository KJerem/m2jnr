/**
 * Contrôles d'accessibilité de la recette (sprint 4) : aucun piège au clavier dans l'éditeur
 * du devis ni dans le formulaire de paiement (Tab fait avancer le focus et finit par en
 * sortir, Maj+Tab revient), un seul titre de niveau 1 sur les pages principales.
 */
import { expect, test, type Locator, type Page } from "@playwright/test";
import { Api, creerFacture, creerOrdre, GERANT, seConnecter, type OrdreCree } from "./outils";

let ordre: OrdreCree;
let facture: { id: number; numero: string };

test.beforeAll(async () => {
  const api = await Api.connecter(GERANT);
  ordre = await creerOrdre(api, { decalage: 201 });
  facture = await creerFacture(api, 202);
  await api.fermer();
});

/** Description courte de l'élément qui a le focus, et s'il est dans `zone`. */
async function focus(page: Page, zone: Locator): Promise<{ cle: string; dedans: boolean }> {
  const dedans = await zone.evaluate((el) => el.contains(document.activeElement));
  const cle = await page.evaluate(() => {
    const el = document.activeElement as HTMLElement | null;
    if (!el || el === document.body) return "body";
    return `${el.tagName}#${el.id}|${el.getAttribute("name") ?? ""}|${el.textContent?.trim().slice(0, 30) ?? ""}`;
  });
  return { cle, dedans };
}

/** Parcourt la zone au clavier depuis son premier champ : Tab fait avancer le focus, qui
 * finit par sortir de la zone ; Maj+Tab y revient. Un champ date et heure garde le focus le
 * temps de ses sous-champs (jour, mois, année, heure, minute) : quelques Tab de suite sur le
 * même élément sont permis, pas davantage. */
async function sansPiegeClavier(page: Page, zone: Locator, premier: Locator): Promise<void> {
  await premier.focus();
  const vus: string[] = [];
  let sorti = false;
  let surPlace = 0;
  for (let i = 0; i < 80 && !sorti; i += 1) {
    const avant = await focus(page, zone);
    await page.keyboard.press("Tab");
    const apres = await focus(page, zone);
    surPlace = apres.cle === avant.cle ? surPlace + 1 : 0;
    expect(surPlace, `Tab ne fait plus avancer le focus (${avant.cle})`).toBeLessThan(6);
    vus.push(apres.cle);
    sorti = !apres.dedans;
  }
  expect(sorti, `le focus reste piégé dans la zone : ${vus.join(" → ")}`).toBe(true);
  await page.keyboard.press("Shift+Tab");
  expect((await focus(page, zone)).dedans).toBe(true);
}

test("éditeur du devis : aucun piège au clavier", async ({ page }) => {
  await seConnecter(page, GERANT);
  await page.goto(`/ordres/${ordre.id}`);
  const devis = page.getByRole("region", { name: /Devis — pièces/ });
  await devis.getByRole("button", { name: "Ajouter une ligne" }).click();
  await devis.getByRole("button", { name: "Ajouter une ligne" }).click();
  const formulaire = devis.locator("form");
  await sansPiegeClavier(page, formulaire, devis.getByRole("group", { name: "Ligne 1" }).getByLabel("Type"));
});

test("formulaire de paiement : aucun piège au clavier", async ({ page }) => {
  await seConnecter(page, GERANT);
  await page.goto(`/factures/${facture.id}`);
  const paiements = page.getByRole("region", { name: "Paiements" });
  const formulaire = paiements.locator("form");
  await sansPiegeClavier(page, formulaire, paiements.getByLabel(/^Montant/));
});

const PAGES = ["/", "/planning", "/atelier", "/ordres", "/rendez-vous", "/clients", "/devis", "/factures", "/recherche?q=peugeot"];

test("un seul titre de niveau 1 par page principale", async ({ page }) => {
  await seConnecter(page, GERANT);
  const pages = [...PAGES, `/ordres/${ordre.id}`, `/factures/${facture.id}`];
  for (const chemin of pages) {
    await page.goto(chemin);
    await expect(page.getByRole("heading", { level: 1 }), chemin).toHaveCount(1);
  }
});
