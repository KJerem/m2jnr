import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { cleDevisOrdre } from "@/components/devis/donnees";
import { DevisOrdre } from "@/components/devis/DevisOrdre";
import { ListeDevis } from "@/components/facturation/ListeDevis";
import { ToastProvider } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api";
import { AIDE_ENVOI, BADGE_DEVIS, devisModifiable, LIBELLE_DEVIS, MESSAGE_DEVIS_VERROUILLE, phraseStatutDevis, type DevisDetail, type StatutDevis } from "@/lib/devis";
import { factureDisponible, MESSAGE_FACTURE_INDISPONIBLE } from "@/lib/factures";
import type { OrdreDetail } from "@/lib/ordres";

const apiFetch = vi.fn();
vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return { ...original, apiFetch: (...args: unknown[]) => apiFetch(...args) };
});
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }), usePathname: () => "/devis" }));

const BROUILLON: DevisDetail = {
  id: 7,
  ordre: { id: 1, numero: "OT-2026-001", statut: "termine" },
  statut: "brouillon",
  envoye_le: null,
  decide_le: null,
  decide_par: null,
  lignes: [
    { id: 70, type: "piece", reference: null, designation: "Pièce", quantite: "2.00", prix_unitaire_ht_centimes: 4000, total_ht_centimes: 8000, position: 0 },
    { id: 71, type: "main_oeuvre", reference: null, designation: "Main-d'œuvre", quantite: "1.00", prix_unitaire_ht_centimes: 6000, total_ht_centimes: 6000, position: 1 },
  ],
  taux_tva_bp: 2000,
  totaux: { main_oeuvre_ht_centimes: 6000, pieces_ht_centimes: 8000, total_ht_centimes: 14000, total_tva_centimes: 2800, total_ttc_centimes: 16800 },
  cree_le: "2026-12-22T09:00:00Z",
  modifie_le: "2026-12-22T09:00:00Z",
  facture: null,
};
const ENVOYE: DevisDetail = { ...BROUILLON, statut: "envoye", envoye_le: "2026-12-22T09:15:00Z" };
const ACCEPTE: DevisDetail = { ...ENVOYE, statut: "accepte", decide_le: "2026-12-22T09:40:00Z", decide_par: { id: 1, nom: "Nadia Benali" } };
const REFUSE: DevisDetail = { ...ENVOYE, statut: "refuse", decide_le: "2026-12-22T09:40:00Z", decide_par: { id: 1, nom: "Nadia Benali" } };

const ORDRE = {
  id: 1,
  numero: "OT-2026-001",
  statut: "termine",
  prioritaire: false,
  vehicule: { id: 4, immatriculation: "GH-482-KL", marque: "Peugeot", modele: "308 SW", kilometrage: 84312, vin: null, date_mise_en_circulation: null },
  client: { id: 9, nom: "Laurent", prenom: "Claire", contact: null },
  mecanicien: null,
  restitution_prevue: null,
  ouvert_le: "2026-12-22T07:10:00Z",
  cloture_le: null,
  taches_terminees: 0,
  taches_total: 0,
  duree_prevue_minutes: 0,
  en_retard: false,
  rendez_vous: null,
  demande_client: "Bruit au freinage",
  diagnostic: null,
  kilometrage_entree: null,
  cree_par: { id: 1, nom: "Nadia Benali" },
  taches: [],
  historique: [],
} satisfies OrdreDetail;

function afficher(devis: DevisDetail, ordre: OrdreDetail = ORDRE) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity }, mutations: { retry: false } } });
  client.setQueryData(cleDevisOrdre(ordre.id), devis);
  render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <DevisOrdre ordre={ordre} />
      </ToastProvider>
    </QueryClientProvider>,
  );
  return client;
}

const bouton = (nom: string) => screen.queryByRole("button", { name: nom });

beforeEach(() => {
  apiFetch.mockReset();
});

describe("statut du devis : badge et boutons selon l'état", () => {
  it.each<[StatutDevis, string]>([
    ["brouillon", "Brouillon"],
    ["envoye", "Envoyé"],
    ["accepte", "Accepté"],
    ["refuse", "Refusé"],
  ])("badge « %s » : pastille et mot", (statut, mot) => {
    afficher({ ...ACCEPTE, statut });

    const badge = screen.getByText(mot, { selector: ".et-status" });
    expect(badge).toHaveClass(`et-status-${BADGE_DEVIS[statut]}`);
    expect(badge.querySelector(".et-dot")).not.toBeNull();
    expect(badge).toHaveTextContent(`Statut du devis : ${mot}`);
    expect(LIBELLE_DEVIS[statut]).toBe(mot);
  });

  it("brouillon : modifiable, « Marquer comme envoyé au client » sans prétendre envoyer un message", () => {
    afficher(BROUILLON);

    expect(bouton("Modifier le devis")).toBeInTheDocument();
    expect(bouton("Ajouter une ligne")).toBeInTheDocument();
    expect(bouton("Marquer comme envoyé au client")).toBeEnabled();
    expect(screen.getByText(AIDE_ENVOI)).toBeInTheDocument();
    expect(AIDE_ENVOI).toMatch(/n'envoie ni e-mail ni SMS/);
    expect(bouton("Accepté par le client")).not.toBeInTheDocument();
    expect(bouton("Générer la facture")).toBeDisabled();
    expect(bouton("Générer la facture")).toHaveAccessibleDescription(MESSAGE_FACTURE_INDISPONIBLE);
  });

  it("envoyé : plus d'édition, réponse du client à noter, verrouillage expliqué", () => {
    afficher(ENVOYE);

    expect(bouton("Modifier le devis")).not.toBeInTheDocument();
    expect(bouton("Ajouter une ligne")).not.toBeInTheDocument();
    expect(bouton("Marquer comme envoyé au client")).not.toBeInTheDocument();
    expect(bouton("Accepté par le client")).toBeEnabled();
    expect(bouton("Refusé par le client")).toBeEnabled();
    expect(screen.getByText(MESSAGE_DEVIS_VERROUILLE)).toBeInTheDocument();
    expect(screen.getByText(/^Envoyé au client le mar\. 22 déc\. à 10\sh\s15, en attente de sa réponse\.$/)).toBeInTheDocument();
    expect(bouton("Générer la facture")).toBeDisabled();
  });

  it("accepté sur un OT « Prêt » : facture disponible, aucune autre action", () => {
    afficher(ACCEPTE);

    expect(bouton("Générer la facture")).toBeEnabled();
    for (const nom of ["Modifier le devis", "Accepté par le client", "Refusé par le client", "Nouveau devis"]) {
      expect(bouton(nom)).not.toBeInTheDocument();
    }
    expect(screen.getByText(/^Accepté par le client le mar\. 22 déc\. à 10\sh\s40, noté par Nadia Benali\.$/)).toBeInTheDocument();
  });

  it("accepté sur un OT encore « En cours » : facture désactivée et expliquée", () => {
    afficher(ACCEPTE, { ...ORDRE, statut: "en_cours" });

    expect(bouton("Générer la facture")).toBeDisabled();
    expect(MESSAGE_FACTURE_INDISPONIBLE).toBe("Disponible quand le devis est accepté et l'intervention « Prêt ».");
  });

  it("refusé : « Nouveau devis », ni édition ni facture", () => {
    afficher(REFUSE);

    expect(bouton("Nouveau devis")).toBeEnabled();
    expect(bouton("Modifier le devis")).not.toBeInTheDocument();
    expect(bouton("Générer la facture")).not.toBeInTheDocument();
  });

  it("règles partagées avec l'API", () => {
    expect([BROUILLON, ENVOYE, ACCEPTE, REFUSE].map(devisModifiable)).toEqual([true, false, false, false]);
    expect(devisModifiable({ statut: "brouillon", facture: { id: 1, numero: "F-2026-001" } })).toBe(false);
    expect(factureDisponible("termine", "accepte")).toBe(true);
    expect(factureDisponible("livre", "accepte")).toBe(true);
    expect(factureDisponible("termine", "envoye")).toBe(false);
    expect(factureDisponible("en_cours", "accepte")).toBe(false);
    expect(phraseStatutDevis(BROUILLON)).toBe("Brouillon : le devis se modifie librement.");
    // Décision d'une année précédente : l'année est écrite (devis de 2025 rouvert en 2026).
    const en2026 = new Date("2026-10-25T10:00:00Z");
    expect(phraseStatutDevis({ ...ACCEPTE, decide_le: "2025-10-24T07:30:00Z" }, en2026).replace(/\s/g, " ")).toBe(
      "Accepté par le client le ven. 24 oct. 2025 à 9 h 30, noté par Nadia Benali.",
    );
    expect(phraseStatutDevis({ ...ENVOYE, envoye_le: "2025-12-31T22:30:00Z" }, en2026).replace(/\s/g, " ")).toBe(
      "Envoyé au client le mer. 31 déc. 2025 à 23 h 30, en attente de sa réponse.",
    );
  });
});

describe("statut du devis : actions, focus et retours", () => {
  it("marque le devis envoyé, puis place le focus sur « Accepté par le client »", async () => {
    const user = userEvent.setup({ delay: null });
    apiFetch.mockResolvedValue(ENVOYE);
    afficher(BROUILLON);

    await user.click(screen.getByRole("button", { name: "Marquer comme envoyé au client" }));

    expect(apiFetch).toHaveBeenCalledWith("/devis/7/statut", { method: "POST", body: { nouveau: "envoye" } });
    expect(await screen.findByRole("button", { name: "Accepté par le client" })).toHaveFocus();
    expect(await screen.findByText("Devis marqué comme envoyé au client.")).toBeInTheDocument();
  });

  it("acceptation : le focus va sur « Générer la facture » quand l'OT est « Prêt »", async () => {
    const user = userEvent.setup({ delay: null });
    apiFetch.mockResolvedValue(ACCEPTE);
    afficher(ENVOYE);

    await user.click(screen.getByRole("button", { name: "Accepté par le client" }));

    expect(apiFetch).toHaveBeenCalledWith("/devis/7/statut", { method: "POST", body: { nouveau: "accepte" } });
    await vi.waitFor(() => expect(screen.getByRole("button", { name: "Générer la facture" })).toHaveFocus());
    expect(screen.getByText("Devis accepté par le client.")).toBeInTheDocument();
  });

  it("acceptation sur un OT en cours : le focus va sur la phrase d'état", async () => {
    const user = userEvent.setup({ delay: null });
    apiFetch.mockResolvedValue(ACCEPTE);
    afficher(ENVOYE, { ...ORDRE, statut: "en_cours" });

    await user.click(screen.getByRole("button", { name: "Accepté par le client" }));

    await vi.waitFor(() => expect(screen.getByText(/^Accepté par le client le/)).toHaveFocus());
  });

  it("le refus demande confirmation ; Annuler ne change rien et rend le focus", async () => {
    const user = userEvent.setup({ delay: null });
    afficher(ENVOYE);
    const refuser = screen.getByRole("button", { name: "Refusé par le client" });

    await user.click(refuser);
    const fenetre = screen.getByRole("dialog", { name: "Refusé par le client" });
    expect(fenetre).toHaveTextContent(/168,00\s€ TTC sera marqué refusé par le client/);
    await user.click(within(fenetre).getByRole("button", { name: "Annuler" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(refuser).toHaveFocus();
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("refus confirmé, puis « Nouveau devis » reprend les lignes et crée un devis", async () => {
    const user = userEvent.setup({ delay: null });
    apiFetch.mockResolvedValueOnce(REFUSE).mockResolvedValueOnce({ ...BROUILLON, id: 8 });
    afficher(ENVOYE);

    await user.click(screen.getByRole("button", { name: "Refusé par le client" }));
    await user.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Confirmer le refus" }));

    expect(apiFetch).toHaveBeenCalledWith("/devis/7/statut", { method: "POST", body: { nouveau: "refuse" } });
    const nouveau = await screen.findByRole("button", { name: "Nouveau devis" });
    expect(nouveau).toHaveFocus();
    expect(await screen.findByText("Devis refusé par le client.")).toBeInTheDocument();

    await user.click(nouveau);
    expect(screen.getAllByRole("group", { name: /^Ligne \d$/ })).toHaveLength(2);
    await user.click(screen.getByRole("button", { name: "Enregistrer le devis" }));

    await vi.waitFor(() => expect(apiFetch).toHaveBeenCalledTimes(2));
    expect(apiFetch).toHaveBeenLastCalledWith("/ordres/1/devis", expect.objectContaining({ method: "POST" }));
  });

  it("annonce le refus de l'API sans changer le statut affiché", async () => {
    const user = userEvent.setup({ delay: null });
    apiFetch.mockRejectedValue(new ApiError(409, "transition_devis_interdite", "Le devis est déjà « Envoyé »."));
    afficher(BROUILLON);

    await user.click(screen.getByRole("button", { name: "Marquer comme envoyé au client" }));

    expect(await screen.findByText("Le devis est déjà « Envoyé ».")).toBeInTheDocument();
    expect(screen.getByText("Brouillon", { selector: ".et-status" })).toBeInTheDocument();
  });
});

describe("onglet Devis : colonne Statut", () => {
  it("affiche le statut de chaque devis en badge", async () => {
    const resume = {
      id: 7,
      ordre: BROUILLON.ordre,
      vehicule: { id: 4, immatriculation: "GH-482-KL", marque: "Peugeot", modele: "308 SW", kilometrage: 84312 },
      client: { id: 9, nom: "Laurent", prenom: "Claire" },
      statut: "envoye" as const,
      envoye_le: "2026-12-22T09:15:00Z",
      decide_le: null,
      total_ht_centimes: 14000,
      total_ttc_centimes: 16800,
      cree_le: "2026-12-22T09:00:00Z",
      modifie_le: "2026-12-22T09:00:00Z",
      facture: null,
    };
    apiFetch.mockResolvedValue({ elements: [resume], total: 1, page: 1, taille: 50 });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const enveloppe = (enfant: ReactNode) => <QueryClientProvider client={client}>{enfant}</QueryClientProvider>;
    render(enveloppe(<ListeDevis page={1} />));

    const ligne = (await screen.findByRole("link", { name: "OT-2026-001" })).closest("tr");
    expect(ligne).not.toBeNull();
    expect(within(ligne as HTMLElement).getByText("Envoyé")).toHaveClass("et-status-en-cours");
    expect(screen.getAllByRole("columnheader").map((th) => th.textContent)).toContain("Statut");
  });
});
