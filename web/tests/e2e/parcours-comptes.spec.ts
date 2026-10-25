/**
 * Comptes de l'équipe (recette du sprint 5, stories S8.2 et S8.3) :
 * a) le gérant crée un employé, l'employé se connecte, le gérant le désactive : la session
 *    ouverte de l'employé est refusée à sa navigation suivante (retour à /connexion) et sa
 *    connexion est refusée ;
 * b) un nouveau gérant s'inscrit : confirmation neutre, connexion refusée tant que le compte
 *    attend (message générique, comme pour une adresse inconnue), Nadia le valide comme mécanicien, la connexion réussit avec le menu du mécanicien.
 *
 * Les e-mails viennent de l'identifiant d'exécution (rejouable) ; les comptes de
 * démonstration ne sont ni bloqués ni désactivés : seuls les comptes créés ici le sont. À la
 * fin du fichier, réussi ou non, les comptes créés ici encore actifs sont désactivés et les
 * demandes encore en attente refusées : chaque exécution ajoutait un mécanicien actif (listes
 * d'affectation, « N mécaniciens actifs ») et, en cas d'échec, une demande en attente qui
 * rapprochait de la limite de 20 (revue du sprint 5).
 */
import { expect, test, type Browser, type Page } from "@playwright/test";
import { Api, GERANT, numeroExecution, seConnecter } from "./outils";

const MOT_DE_PASSE = "Recette-Sprint5-2027";
const EMAIL_EMPLOYE = `employe.${numeroExecution(301)}@exemple.test`;
const EMAIL_INSCRIPTION = `inscription.${numeroExecution(302)}@exemple.test`;

interface CompteListe {
  id: number;
  email: string;
  statut: "actif" | "en_attente" | "desactive";
}

/** Désactive (actif) ou refuse (en attente) les comptes de recette créés par ce fichier. */
async function rangerComptes(emails: string[]): Promise<void> {
  const api = await Api.connecter(GERANT);
  for (const email of emails) {
    const { elements } = await api.get<{ elements: CompteListe[] }>(`/api/utilisateurs?q=${encodeURIComponent(email)}`);
    for (const compte of elements.filter((c) => c.email === email)) {
      if (compte.statut === "en_attente") await api.post(`/api/utilisateurs/${compte.id}/refuser`);
      else if (compte.statut === "actif") await api.post(`/api/utilisateurs/${compte.id}/desactiver`);
    }
  }
  await api.fermer();
}

test.afterAll(async () => {
  await rangerComptes([EMAIL_EMPLOYE, EMAIL_INSCRIPTION]);
});

async function nouvellePage(browser: Browser): Promise<Page> {
  const contexte = await browser.newContext();
  return contexte.newPage();
}

async function connexionRefusee(page: Page, email: string, message: string): Promise<void> {
  await page.goto("/connexion");
  await page.getByLabel("E-mail").fill(email);
  await page.getByLabel("Mot de passe").fill(MOT_DE_PASSE);
  await page.getByRole("button", { name: "Se connecter" }).click();
  await expect(page.locator("#connexion-erreur")).toHaveText(message);
  await expect(page).toHaveURL(/\/connexion/);
}

test("le gérant crée un employé puis le désactive : session arrêtée, connexion refusée", async ({ page, browser }) => {
  const numero = numeroExecution(301);
  const email = EMAIL_EMPLOYE;
  const nom = `Recette${numero}`;
  await seConnecter(page, GERANT);

  await test.step("le gérant crée le compte d'un mécanicien", async () => {
    await page.goto("/employes");
    await page.getByRole("link", { name: "Nouvel employé" }).click();
    await expect(page).toHaveURL(/\/employes\/nouveau$/);
    await expect(page.getByText("12 caractères").first()).toBeVisible();
    await page.getByLabel(/^Prénom/).fill("Julie");
    await page.getByLabel(/^Nom/).fill(nom);
    await page.getByLabel(/^E-mail/).fill(email);
    await page.getByLabel(/^Rôle/).selectOption("mecanicien");
    await page.getByLabel(/^Mot de passe/).fill(MOT_DE_PASSE);
    await page.getByLabel(/^Confirmer le mot de passe/).fill(MOT_DE_PASSE);
    await page.getByRole("button", { name: "Créer le compte" }).click();
    await expect(page).toHaveURL(/\/employes\/\d+$/);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(`Julie ${nom}`);
    // Revue du sprint 5 : le focus arrive sur le titre de la fiche créée, pas sur <body>.
    await expect(page.getByRole("heading", { level: 1 })).toBeFocused();
  });

  const employe = await nouvellePage(browser);
  await test.step("l'employé se connecte avec le menu du mécanicien", async () => {
    await seConnecter(employe, { email, motDePasse: MOT_DE_PASSE });
    const menu = employe.getByRole("navigation", { name: "Navigation principale" });
    await expect(menu.getByRole("link", { name: "Véhicules" })).toBeVisible();
    await expect(menu.getByRole("link", { name: "Employés" })).toHaveCount(0);
  });

  await test.step("le gérant désactive le compte, après confirmation", async () => {
    await page.getByRole("button", { name: "Désactiver le compte" }).click();
    const fenetre = page.getByRole("dialog", { name: /Désactiver le compte/ });
    await fenetre.getByRole("button", { name: "Désactiver", exact: true }).click();
    await expect(fenetre).toHaveCount(0);
    await expect(page.locator(".et-status").filter({ hasText: "Désactivé" }).first()).toBeVisible();
    await expect(page.getByRole("button", { name: "Réactiver le compte" })).toBeVisible();
  });

  await test.step("la session ouverte de l'employé est refusée à la navigation suivante", async () => {
    await employe.getByRole("navigation", { name: "Navigation principale" }).getByRole("link", { name: "Ordres de travail" }).click();
    await expect(employe).toHaveURL(/\/connexion/);
  });

  await test.step("sa connexion est refusée avec le message générique", async () => {
    await connexionRefusee(employe, email, "Identifiants invalides.");
  });
  await employe.context().close();
});

test("inscription d'un gérant : en attente, refusée, validée comme mécanicien, connectée", async ({ page, browser }) => {
  const numero = numeroExecution(302);
  const email = EMAIL_INSCRIPTION;
  const nom = `Inscrit${numero}`;

  await test.step("le formulaire public d'inscription donne la confirmation neutre", async () => {
    await page.goto("/connexion");
    await page.getByRole("link", { name: "Créer un compte gérant" }).click();
    await expect(page).toHaveURL(/\/inscription$/);
    await page.getByLabel(/^Prénom/).fill("Léa");
    await page.getByLabel(/^Nom/).fill(nom);
    await page.getByLabel(/^E-mail/).fill(email);
    await page.getByLabel(/^Mot de passe/).fill(MOT_DE_PASSE);
    await page.getByLabel(/^Confirmer le mot de passe/).fill(MOT_DE_PASSE);
    await page.getByRole("button", { name: "Créer le compte" }).click();
    await expect(page.getByRole("heading", { name: "Demande envoyée" })).toBeVisible();
    await expect(page.getByText("Demande enregistrée. Un gérant du garage doit valider votre compte avant votre première connexion.")).toBeVisible();
  });

  await test.step("tant que le compte attend, la connexion est refusée", async () => {
    await page.getByRole("link", { name: "Retour à la connexion" }).click();
    await connexionRefusee(page, email, "Identifiants invalides.");
  });

  await test.step("Nadia valide le compte comme mécanicien", async () => {
    const gerant = await nouvellePage(browser);
    await seConnecter(gerant, GERANT);
    await gerant.goto("/employes?statut=en_attente");
    await gerant.getByRole("searchbox", { name: "Rechercher un employé" }).fill(email);
    await gerant.getByRole("link", { name: `Léa ${nom}` }).click();
    await expect(gerant.getByRole("heading", { name: "Validation du compte" })).toBeVisible();
    await gerant.getByLabel("Rôle du compte").selectOption("mecanicien");
    await gerant.getByRole("button", { name: "Valider le compte" }).click();
    await expect(gerant.locator(".et-status").filter({ hasText: "Actif" }).first()).toBeVisible();
    await expect(gerant.getByText("Mécanicien").first()).toBeVisible();
    await gerant.context().close();
  });

  await test.step("la connexion réussit, avec le menu du mécanicien", async () => {
    await seConnecter(page, { email, motDePasse: MOT_DE_PASSE });
    const menu = page.getByRole("navigation", { name: "Navigation principale" });
    await expect(menu.getByRole("link", { name: "Véhicules" })).toBeVisible();
    await expect(menu.getByRole("link", { name: "Employés" })).toHaveCount(0);
    await expect(menu.getByRole("link", { name: "Devis & factures" })).toHaveCount(0);
  });
});
