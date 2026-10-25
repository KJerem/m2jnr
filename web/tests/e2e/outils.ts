/**
 * Outils des parcours de recette : connexion, appels à l'API comme le navigateur (cookie de
 * session, jeton CSRF), données uniques à chaque exécution (les parcours se rejouent sur la
 * même base sans conflit : plaque et téléphone tirés d'un identifiant d'exécution, voir
 * donnees.ts, et créneau de rendez-vous cherché parmi les créneaux libres du pont).
 *
 * Les comptes de démonstration ne reçoivent jamais de mauvais mot de passe : ils ne doivent
 * pas être bloqués (5 échecs = 15 minutes).
 */
import { expect, request, type APIRequestContext, type Page } from "@playwright/test";
import { EXECUTION, numeroExecution, plaqueUnique, premierCreneauLibre, telephoneUnique } from "./donnees";

export { numeroExecution, plaqueUnique, telephoneUnique };

export const GERANT = { email: "nadia@garage.test", motDePasse: process.env.E2E_MDP_GERANT ?? "Gerant-Demo-2026!" };
export const MECANICIEN = { email: "karim@garage.test", motDePasse: process.env.E2E_MDP_MECANICIEN ?? "Meca-Demo-2026!" };

const BASE = process.env.E2E_BASE_URL ?? "http://localhost:3000";

/** « 2026-12-24 » dans `jours` jours (calendrier de Paris). */
export function jourDansNJours(jours: number): string {
  const date = new Date(Date.now() + jours * 86_400_000);
  return new Intl.DateTimeFormat("fr-CA", { timeZone: "Europe/Paris", year: "numeric", month: "2-digit", day: "2-digit" }).format(date);
}

export async function seConnecter(page: Page, compte: { email: string; motDePasse: string }): Promise<void> {
  await page.goto("/connexion");
  await page.getByLabel("E-mail").fill(compte.email);
  await page.getByLabel("Mot de passe").fill(compte.motDePasse);
  await page.getByRole("button", { name: "Se connecter" }).click();
  await expect(page).not.toHaveURL(/\/connexion/);
}

/** Client HTTP connecté, qui envoie le jeton CSRF comme le navigateur. */
export class Api {
  private constructor(
    private readonly contexte: APIRequestContext,
    private readonly jeton: string,
  ) {}

  static async connecter(compte: { email: string; motDePasse: string }): Promise<Api> {
    const contexte = await request.newContext({ baseURL: BASE });
    const csrf = await contexte.get("/api/auth/csrf");
    expect(csrf.ok()).toBeTruthy();
    const { jeton } = (await csrf.json()) as { jeton: string };
    const api = new Api(contexte, jeton);
    await api.post("/api/auth/login", { email: compte.email, mot_de_passe: compte.motDePasse });
    return api;
  }

  async get<T>(chemin: string): Promise<T> {
    const reponse = await this.contexte.get(chemin);
    expect(reponse.ok(), `${chemin} : ${await reponse.text()}`).toBeTruthy();
    return (await reponse.json()) as T;
  }

  async post<T>(chemin: string, corps?: unknown): Promise<T> {
    const reponse = await this.contexte.post(chemin, { data: corps ?? {}, headers: { "X-CSRF-Token": this.jeton } });
    expect(reponse.ok(), `${chemin} : ${await reponse.text()}`).toBeTruthy();
    // 204 (refus d'une inscription, par exemple) : pas de corps.
    return (reponse.status() === 204 ? undefined : await reponse.json()) as T;
  }

  async fermer(): Promise<void> {
    await this.contexte.dispose();
  }
}

export interface OrdreCree {
  id: number;
  numero: string;
  plaque: string;
  client: string;
}

/**
 * Client, véhicule et OT créés par l'API (comme le gérant), pour ne pas dépendre de l'état
 * des données de démonstration.
 */
export async function creerOrdre(api: Api, options: { decalage: number; mecanicienId?: number; taches?: string[] }): Promise<OrdreCree> {
  const plaque = plaqueUnique(options.decalage);
  const nom = `Recette${numeroExecution(options.decalage)}`;
  const client = await api.post<{ id: number }>("/api/clients", { nom, prenom: "Camille", telephone: telephoneUnique(options.decalage), consentement_rappels: false });
  const vehicule = await api.post<{ id: number }>(`/api/clients/${client.id}/vehicules`, { immatriculation: plaque, marque: "Renault", modele: "Kangoo", kilometrage: 61200 });
  const ordre = await api.post<{ id: number; numero: string }>("/api/ordres", {
    vehicule_id: vehicule.id,
    demande_client: "Contrôle avant départ en vacances.",
    mecanicien_id: options.mecanicienId ?? null,
    taches: (options.taches ?? []).map((libelle) => ({ libelle, duree_prevue_minutes: 30 })),
  });
  return { id: ordre.id, numero: ordre.numero, plaque, client: `Camille ${nom}` };
}

/** Facture émise par l'API sur un OT neuf (devis de 168,00 € TTC accepté, OT « Prêt »). */
export async function creerFacture(api: Api, decalage: number): Promise<{ id: number; numero: string; ordre: OrdreCree }> {
  const ordre = await creerOrdre(api, { decalage });
  const devis = await api.post<{ id: number }>(`/api/ordres/${ordre.id}/devis`, {
    lignes: [
      { type: "piece", designation: "Plaquettes avant", quantite: "2", prix_unitaire_ht_centimes: 4000 },
      { type: "main_oeuvre", designation: "Main-d’œuvre", quantite: "1", prix_unitaire_ht_centimes: 6000 },
    ],
  });
  await api.post(`/api/devis/${devis.id}/statut`, { nouveau: "envoye" });
  await api.post(`/api/devis/${devis.id}/statut`, { nouveau: "accepte" });
  await api.post(`/api/ordres/${ordre.id}/statut`, { nouveau: "en_cours" });
  await api.post(`/api/ordres/${ordre.id}/statut`, { nouveau: "termine" });
  const facture = await api.post<{ id: number; numero: string }>(`/api/devis/${devis.id}/facture`);
  return { ...facture, ordre };
}

/**
 * Créneau libre sur le pont nommé, lu dans les rendez-vous déjà pris (GET /api/rendez-vous) :
 * à partir d'un jour propre à l'exécution (dans 30 à 329 jours), le premier jour qui a une
 * place. Une exécution précédente restée en base ne provoque plus de chevauchement (409).
 */
export async function creneauLibre(api: Api, nomPont: string, dureeMinutes = 60): Promise<{ jour: string; heure: string }> {
  const ponts = await api.get<{ id: number; nom: string }[]>("/api/ponts");
  const pont = ponts.find((p) => p.nom === nomPont);
  expect(pont, `le pont « ${nomPont} » doit exister (seed)`).toBeDefined();
  const depart = 30 + (EXECUTION % 300);
  for (let jours = depart; jours < depart + 60; jours += 1) {
    const jour = jourDansNJours(jours);
    const pris = await api.get<{ debut: string; fin: string }[]>(`/api/rendez-vous?du=${jour}&au=${jour}&pont_id=${pont!.id}`);
    const heure = premierCreneauLibre(pris, dureeMinutes);
    if (heure) return { jour, heure };
  }
  throw new Error(`aucun créneau libre sur ${nomPont} pendant 60 jours`);
}
