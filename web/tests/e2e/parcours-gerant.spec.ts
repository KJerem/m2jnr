/**
 * Parcours du gérant (recette du sprint 4) : client → véhicule → rendez-vous → ordre de
 * travail → tâches → devis (168,00 € TTC) → envoyé → accepté → « En cours » → « Prêt » →
 * facture et PDF → paiement partiel puis solde → « Payée » → recherche par plaque.
 */
import { expect, test } from "@playwright/test";
import { Api, creneauLibre, GERANT, numeroExecution, plaqueUnique, seConnecter, telephoneUnique } from "./outils";

test("parcours complet du gérant, du client au paiement", async ({ page }) => {
  const plaque = plaqueUnique(0);
  const nom = `Recette${numeroExecution(0)}`;
  // Créneau libre sur le pont 3, lu dans les rendez-vous déjà pris (durée par défaut : 1 h).
  const api = await Api.connecter(GERANT);
  const { jour, heure } = await creneauLibre(api, "Pont 3", 60);
  await api.fermer();

  await seConnecter(page, GERANT);

  await test.step("créer le client, avec son adresse", async () => {
    await page.goto("/clients/nouveau");
    await page.getByLabel(/^Nom/).fill(nom);
    await page.getByLabel("Prénom").fill("Camille");
    await page.getByLabel(/^Téléphone/).fill(telephoneUnique(0));
    await page.getByLabel("Adresse", { exact: true }).fill("12 allée des Recettes");
    await page.getByLabel("Code postal").fill("69003");
    await page.getByLabel("Ville").fill("Lyon");
    await page.getByRole("button", { name: "Créer le client" }).click();
    await expect(page).toHaveURL(/\/clients\/\d+$/);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(`Camille ${nom}`);
    await expect(page.getByText("69003 Lyon")).toBeVisible();
  });

  await test.step("ajouter un véhicule", async () => {
    await page.getByRole("button", { name: "Ajouter un véhicule" }).click();
    await page.getByLabel(/^Immatriculation/).fill(plaque);
    await page.getByLabel(/^Marque/).fill("Peugeot");
    await page.getByLabel(/^Modèle/).fill("208");
    await page.getByLabel(/^Kilométrage/).fill("42150");
    await page.getByRole("button", { name: "Ajouter le véhicule" }).click();
    await expect(page.getByRole("region", { name: "Véhicules" }).getByText(plaque)).toBeVisible();
  });

  await test.step("prendre rendez-vous sur un créneau libre", async () => {
    await page.goto("/rendez-vous");
    const formulaire = page.getByRole("region", { name: "Nouveau rendez-vous" });
    await formulaire.getByLabel(/^Véhicule/).selectOption({ label: `${plaque} · Peugeot 208` });
    await formulaire.getByLabel(/^Pont/).selectOption({ label: "Pont 3" });
    await formulaire.getByLabel(/^Jour/).fill(jour);
    await formulaire.getByLabel(/^Heure/).fill(heure);
    await formulaire.getByLabel(/^Motif/).fill("Bruit au freinage avant");
    await formulaire.getByRole("button", { name: "Enregistrer le rendez-vous" }).click();
    await expect(page.getByRole("button", { name: new RegExp(`Ouvrir l.ordre de travail.*\\(${plaque}\\)`) })).toBeVisible();
  });

  await test.step("ouvrir l'ordre de travail depuis le rendez-vous et prévoir deux tâches", async () => {
    await page.getByRole("button", { name: new RegExp(`Ouvrir l.ordre de travail.*\\(${plaque}\\)`) }).click();
    await expect(page).toHaveURL(/\/ordres\/\d+$/);
    await expect(page.getByRole("heading", { level: 1 })).toContainText(/OT-\d{4}-\d{3}/);
    await page.getByRole("button", { name: "Modifier", exact: true }).click();
    await page.getByRole("button", { name: "Ajouter une tâche" }).click();
    await page.getByRole("textbox", { name: "Tâche 1", exact: true }).fill("Remplacer les plaquettes avant");
    await page.getByRole("button", { name: "Ajouter une tâche" }).click();
    await page.getByRole("textbox", { name: "Tâche 2", exact: true }).fill("Essai routier");
    await page.getByRole("button", { name: "Enregistrer", exact: true }).click();
    await expect(page.getByText("Ordre de travail enregistré.")).toBeVisible();
  });

  await test.step("établir le devis : 2 pièces à 40 € + 1 h à 60 € = 168,00 € TTC", async () => {
    const devis = page.getByRole("region", { name: /Devis — pièces/ });
    await devis.getByRole("button", { name: "Ajouter une ligne" }).click();
    const ligne1 = devis.getByRole("group", { name: "Ligne 1" });
    await ligne1.getByLabel("Type").selectOption("piece");
    await ligne1.getByLabel(/^Désignation/).fill("Plaquettes avant");
    await ligne1.getByLabel(/^Quantité/).fill("2");
    await ligne1.getByLabel(/^PU HT/).fill("40");
    await devis.getByRole("button", { name: "Ajouter une ligne" }).click();
    const ligne2 = devis.getByRole("group", { name: "Ligne 2" });
    await ligne2.getByLabel("Type").selectOption("main_oeuvre");
    await ligne2.getByLabel(/^Désignation/).fill("Remplacement des plaquettes");
    await ligne2.getByLabel(/^Heures/).fill("1");
    await ligne2.getByLabel(/^PU HT/).fill("60");
    await expect(devis).toContainText(/168,00\s€/);
    await devis.getByRole("button", { name: "Enregistrer le devis" }).click();
    await expect(devis.getByRole("button", { name: "Marquer comme envoyé au client" })).toBeVisible();
    await expect(devis).toContainText(/140,00\s€/);
    await expect(devis).toContainText(/28,00\s€/);
    await expect(devis).toContainText(/168,00\s€/);
  });

  await test.step("marquer le devis envoyé puis accepté par le client", async () => {
    const devis = page.getByRole("region", { name: /Devis — pièces/ });
    await devis.getByRole("button", { name: "Marquer comme envoyé au client" }).click();
    await devis.getByRole("button", { name: "Accepté par le client" }).click();
    await expect(devis.getByText("Statut du devis : Accepté")).toBeVisible();
    await expect(devis.getByText(/^Accepté par le client le /)).toBeVisible();
  });

  await test.step("faire avancer l'intervention : « En cours », tâches cochées, « Prêt »", async () => {
    await page.getByRole("button", { name: "Passer à « En cours »" }).click();
    // Cases contrôlées par la réponse de l'API : on clique, puis on attend l'état coché.
    for (const tache of ["Remplacer les plaquettes avant", "Essai routier"]) {
      await page.getByLabel(tache).click();
      await expect(page.getByLabel(tache)).toBeChecked();
    }
    await expect(page.getByRole("button", { name: "Passer à « Prêt »" })).toBeEnabled();
    await page.getByRole("button", { name: "Passer à « Prêt »" }).click();
    await expect(page.getByRole("button", { name: "Passer à « Livré »" })).toBeVisible();
  });

  let lienFacture = "";
  await test.step("générer la facture et télécharger son PDF", async () => {
    await page.getByRole("button", { name: "Générer la facture" }).click();
    const fenetre = page.getByRole("dialog", { name: "Générer la facture" });
    await expect(fenetre).toContainText(/168,00\s€ TTC/);
    await fenetre.getByRole("button", { name: "Générer la facture" }).click();
    const pdf = page.getByRole("link", { name: "Télécharger le PDF" });
    await expect(pdf).toBeFocused();
    const reponse = await page.request.get((await pdf.getAttribute("href"))!);
    expect(reponse.status()).toBe(200);
    expect(reponse.headers()["content-type"]).toBe("application/pdf");
    expect((await reponse.body()).subarray(0, 5).toString()).toBe("%PDF-");
    lienFacture = (await page.getByRole("link", { name: "Voir la facture" }).getAttribute("href"))!;
  });

  await test.step("encaisser un paiement partiel puis le solde", async () => {
    await page.goto(lienFacture);
    const paiements = page.getByRole("region", { name: "Paiements" });
    await expect(paiements.getByText("Impayée")).toBeVisible();
    const montant = paiements.getByLabel(/^Montant/);
    await expect(montant).toHaveValue("168,00");
    await montant.fill("100");
    await paiements.getByLabel(/^Mode/).selectOption("cheque");
    await paiements.getByLabel("Référence").fill("0001234");
    await paiements.getByRole("button", { name: "Enregistrer le paiement" }).click();
    await expect(page.getByText(/Reste à payer : 68,00\s€\./)).toBeVisible();
    await expect(paiements.getByText("Partiellement payée")).toBeVisible();
    await expect(montant).toHaveValue("68,00");
    await expect(montant).toBeFocused();
    await paiements.getByRole("button", { name: "Enregistrer le paiement" }).click();
    await expect(paiements.getByText("Payée", { exact: true })).toBeVisible();
    await expect(paiements.getByRole("button", { name: "Enregistrer le paiement" })).toHaveCount(0);
    await expect(paiements.getByRole("row")).toHaveCount(3);
  });

  await test.step("retrouver le client par la plaque sans tirets depuis le champ de recherche", async () => {
    await page.goto("/");
    const recherche = page.getByRole("search").getByRole("searchbox", { name: "Rechercher" });
    await recherche.fill(plaque.replaceAll("-", "").toLowerCase());
    await recherche.press("Enter");
    await expect(page).toHaveURL(/\/recherche\?q=/);
    const vehicules = page.getByRole("region", { name: "Véhicules (1)" });
    await expect(vehicules).toContainText(plaque);
    await expect(vehicules).toContainText(`Camille ${nom}`);
    await expect(page.getByRole("region", { name: /^Clients/ })).toContainText(`Camille ${nom}`);
  });
});
