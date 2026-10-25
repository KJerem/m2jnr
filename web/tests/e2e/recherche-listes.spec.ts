/**
 * Recherche dans les listes (recette du sprint 5, story S1.5) : sur Clients, Véhicules, Ordres
 * de travail, Devis, Factures et Employés, le champ de recherche filtre la liste côté serveur,
 * annonce le nombre de résultats, garde la saisie dans l'adresse (?q=, relue au rechargement
 * et au retour arrière, revue du sprint 5) et montre « Aucun … ne correspond à « … ». » quand
 * rien ne correspond.
 *
 * Les données (client, véhicule, OT, devis, facture) sont créées par l'API à chaque exécution.
 */
import { expect, test, type Page } from "@playwright/test";
import { Api, creerFacture, creerOrdre, GERANT, MECANICIEN, seConnecter, type OrdreCree } from "./outils";

const INTROUVABLE = "zqxwv";

let ordre: OrdreCree;
let facture: { id: number; numero: string; ordre: OrdreCree };

test.beforeAll(async () => {
  const api = await Api.connecter(GERANT);
  ordre = await creerOrdre(api, { decalage: 303 });
  facture = await creerFacture(api, 304);
  await api.fermer();
});

/** Saisit la recherche, attend l'adresse et l'annonce du nombre de résultats. */
async function chercher(page: Page, libelle: string, saisie: string, chemin: string): Promise<void> {
  const champ = page.getByRole("searchbox", { name: libelle });
  await champ.fill(saisie);
  await champ.press("Enter");
  await expect(page).toHaveURL(new RegExp(`${chemin}\\?(.*&)?q=${encodeURIComponent(saisie).replace(/%20/g, "\\+")}`));
}

async function annonce(page: Page, texte: RegExp): Promise<void> {
  await expect(page.locator(".recherche-liste-total")).toHaveText(texte);
}

test("chaque liste du gérant se filtre par une recherche et dit quand rien ne correspond", async ({ page }) => {
  await seConnecter(page, GERANT);
  const plaqueCompacte = ordre.plaque.replaceAll("-", "");

  await test.step("clients : par le nom, gardé au rechargement", async () => {
    await page.goto("/clients");
    const nom = ordre.client.split(" ")[1]!;
    await chercher(page, "Rechercher un client", nom.toLowerCase(), "/clients");
    await annonce(page, /^\d+ résultats? pour/);
    await expect(page.getByRole("link", { name: ordre.client.split(" ").reverse().join(" ") })).toBeVisible();
    await page.reload();
    await expect(page.getByRole("searchbox", { name: "Rechercher un client" })).toHaveValue(nom.toLowerCase());
    await expect(page.getByRole("link", { name: ordre.client.split(" ").reverse().join(" ") })).toBeVisible();
    await chercher(page, "Rechercher un client", INTROUVABLE, "/clients");
    await expect(page.getByText(`Aucun client ne correspond à « ${INTROUVABLE} ».`)).toBeVisible();
  });

  await test.step("véhicules : par la plaque sans tirets", async () => {
    await page.getByRole("tab", { name: "Véhicules" }).click();
    await expect(page).toHaveURL(/\/vehicules$/);
    await chercher(page, "Rechercher un véhicule", plaqueCompacte.toLowerCase(), "/vehicules");
    await annonce(page, /^\d+ résultats? pour/);
    await expect(page.getByRole("link", { name: `Fiche du véhicule ${ordre.plaque}` })).toBeVisible();
    await chercher(page, "Rechercher un véhicule", INTROUVABLE, "/vehicules");
    await expect(page.getByText(`Aucun véhicule ne correspond à « ${INTROUVABLE} ».`)).toBeVisible();
  });

  await test.step("ordres de travail : par le numéro", async () => {
    await page.goto("/ordres");
    await chercher(page, "Rechercher un ordre de travail", ordre.numero, "/ordres");
    await annonce(page, /^\d+ résultats? pour/);
    await expect(page.getByRole("link", { name: ordre.numero, exact: true })).toBeVisible();
    await chercher(page, "Rechercher un ordre de travail", INTROUVABLE, "/ordres");
    await expect(page.getByText(`Aucun ordre de travail ne correspond à « ${INTROUVABLE} ».`)).toBeVisible();
  });

  await test.step("devis : par la plaque", async () => {
    await page.goto("/devis");
    await chercher(page, "Rechercher un devis", facture.ordre.plaque, "/devis");
    await annonce(page, /^\d+ résultats? pour/);
    await expect(page.getByRole("link", { name: facture.ordre.numero, exact: true })).toBeVisible();
    await chercher(page, "Rechercher un devis", INTROUVABLE, "/devis");
    await expect(page.getByText(`Aucun devis ne correspond à « ${INTROUVABLE} ».`)).toBeVisible();
  });

  await test.step("factures : par le numéro de facture", async () => {
    await page.goto("/factures");
    await chercher(page, "Rechercher une facture", facture.numero, "/factures");
    await annonce(page, /^\d+ résultats? pour/);
    await expect(page.getByRole("link", { name: facture.numero, exact: true })).toBeVisible();
    await chercher(page, "Rechercher une facture", INTROUVABLE, "/factures");
    await expect(page.getByText(`Aucune facture ne correspond à « ${INTROUVABLE} ».`)).toBeVisible();
  });

  await test.step("employés : par le prénom, sans accent ni casse", async () => {
    await page.goto("/employes");
    await chercher(page, "Rechercher un employé", "KARIM", "/employes");
    await expect(page.getByRole("link", { name: "Karim B." })).toBeVisible();
    await chercher(page, "Rechercher un employé", INTROUVABLE, "/employes");
    await expect(page.getByText(`Aucun employé ne correspond à « ${INTROUVABLE} ».`)).toBeVisible();
  });
});

test("le retour arrière garde la recherche et les filtres, le lien du menu les retire", async ({ page }) => {
  await seConnecter(page, GERANT);
  const lignes = (nom: string) => page.getByRole("table").getByRole("link", { name: nom, exact: true });

  await test.step("clients : la fiche ouverte, le retour arrière rend la liste filtrée", async () => {
    await page.goto("/clients");
    const nom = ordre.client.split(" ")[1]!;
    const lien = ordre.client.split(" ").reverse().join(" ");
    await chercher(page, "Rechercher un client", nom.toLowerCase(), "/clients");
    // Compter seulement une fois la liste filtrée arrivée : l'adresse change avant la réponse.
    await annonce(page, /^\d+ résultats? pour/);
    await expect(lignes(lien)).toBeVisible();
    const total = await page.getByRole("table").getByRole("row").count();
    await lignes(lien).click();
    await expect(page).toHaveURL(/\/clients\/\d+$/);
    await page.goBack();
    await expect(page).toHaveURL(/\/clients\?q=/);
    await expect(page.getByRole("searchbox", { name: "Rechercher un client" })).toHaveValue(nom.toLowerCase());
    await annonce(page, /^\d+ résultats? pour/);
    await expect(page.getByRole("table").getByRole("row")).toHaveCount(total);
  });

  await test.step("ordres de travail : idem après la fiche de l'OT", async () => {
    await page.goto("/ordres");
    await chercher(page, "Rechercher un ordre de travail", ordre.numero, "/ordres");
    await lignes(ordre.numero).click();
    await expect(page).toHaveURL(/\/ordres\/\d+$/);
    await page.goBack();
    await expect(page.getByRole("searchbox", { name: "Rechercher un ordre de travail" })).toHaveValue(ordre.numero);
    await expect(page.getByRole("table").getByRole("row")).toHaveCount(2);
  });

  await test.step("employés : recherche et statut repris au retour, retirés par le lien du menu", async () => {
    await page.goto("/employes");
    await page.getByRole("group", { name: "Filtrer par statut" }).getByRole("button", { name: "Actif" }).click();
    await chercher(page, "Rechercher un employé", "karim", "/employes");
    await expect(page).toHaveURL(/statut=actif/);
    await lignes("Karim B.").click();
    await expect(page).toHaveURL(/\/employes\/\d+$/);
    await page.goBack();
    await expect(page.getByRole("searchbox", { name: "Rechercher un employé" })).toHaveValue("karim");
    await expect(page.getByRole("group", { name: "Filtrer par statut" }).getByRole("button", { name: "Actif" })).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByRole("table").getByRole("row")).toHaveCount(2);

    await page.getByRole("navigation", { name: "Navigation principale" }).getByRole("link", { name: "Employés" }).click();
    await expect(page).toHaveURL(/\/employes$/);
    await expect(page.getByRole("searchbox", { name: "Rechercher un employé" })).toHaveValue("");
    await expect(page.getByRole("group", { name: "Filtrer par statut" }).getByRole("button", { name: "Tous les statuts" })).toHaveAttribute("aria-pressed", "true");
    await expect.poll(() => page.getByRole("table").getByRole("row").count()).toBeGreaterThan(2);
  });
});

test("le mécanicien cherche un véhicule par sa plaque, jamais par le téléphone du client", async ({ page }) => {
  await seConnecter(page, MECANICIEN);
  await page.getByRole("navigation", { name: "Navigation principale" }).getByRole("link", { name: "Véhicules" }).click();
  await expect(page).toHaveURL(/\/vehicules$/);
  await chercher(page, "Rechercher un véhicule", ordre.plaque, "/vehicules");
  await expect(page.getByRole("link", { name: `Fiche du véhicule ${ordre.plaque}` })).toBeVisible();
  await expect(page.getByRole("link", { name: ordre.client })).toHaveCount(0);
  await chercher(page, "Rechercher un véhicule", "0612483075", "/vehicules");
  await expect(page.getByText("Aucun véhicule ne correspond à « 0612483075 ».")).toBeVisible();
});
