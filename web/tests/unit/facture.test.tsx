import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PiedFacturation } from "@/components/devis/DevisOrdre";
import { DevisFactures } from "@/components/facturation/DevisFactures";
import { ListeDevis } from "@/components/facturation/ListeDevis";
import { ListeFactures } from "@/components/facturation/ListeFactures";
import type { DevisDetail, DevisResume } from "@/lib/devis";
import { formatEmission, formatJour, MESSAGE_FACTURE_INDISPONIBLE, numeroAVenir, peutFacturer, type FactureResume } from "@/lib/factures";

const apiFetch = vi.fn();
vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return { ...original, apiFetch: (...args: unknown[]) => apiFetch(...args) };
});
const navigation = vi.hoisted(() => ({ chemin: "/devis" }));
vi.mock("next/navigation", () => ({ usePathname: () => navigation.chemin, useRouter: () => ({ push: vi.fn(), replace: vi.fn() }) }));

const DEVIS: DevisDetail = {
  id: 7,
  ordre: { id: 1, numero: "OT-2026-001", statut: "termine" },
  statut: "accepte",
  envoye_le: "2026-12-01T09:10:00Z",
  decide_le: "2026-12-01T09:40:00Z",
  decide_par: { id: 1, nom: "Nadia Benali" },
  lignes: [{ id: 70, type: "piece", reference: null, designation: "Pièce", quantite: "2.00", prix_unitaire_ht_centimes: 4000, total_ht_centimes: 8000, position: 0 }],
  taux_tva_bp: 2000,
  totaux: { main_oeuvre_ht_centimes: 6000, pieces_ht_centimes: 8000, total_ht_centimes: 14000, total_tva_centimes: 2800, total_ttc_centimes: 16800 },
  cree_le: "2026-12-01T09:00:00Z",
  modifie_le: "2026-12-01T09:00:00Z",
  facture: null,
};

function avecRequetes(enfant: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}>{enfant}</QueryClientProvider>);
}

beforeEach(() => {
  apiFetch.mockReset();
});

describe("génération de la facture depuis le devis", () => {
  it.each(["a_faire", "en_cours"] as const)("est désactivée et expliquée tant que l'OT est « %s »", (statut) => {
    avecRequetes(<PiedFacturation statut={statut} devis={DEVIS} onEmise={vi.fn()} />);

    const bouton = screen.getByRole("button", { name: "Générer la facture" });
    expect(bouton).toBeDisabled();
    expect(bouton).toHaveAccessibleDescription(MESSAGE_FACTURE_INDISPONIBLE);
    expect(MESSAGE_FACTURE_INDISPONIBLE).toBe("Disponible quand le devis est accepté et l'intervention « Prêt ».");
  });

  it("demande confirmation puis émet la facture d'un OT « Prêt »", async () => {
    const user = userEvent.setup({ delay: null });
    const onEmise = vi.fn();
    const facture = { id: 3, numero: "F-2026-001", totaux: DEVIS.totaux };
    apiFetch.mockResolvedValue(facture);
    avecRequetes(<PiedFacturation statut="termine" devis={DEVIS} onEmise={onEmise} />);

    await user.click(screen.getByRole("button", { name: "Générer la facture" }));
    const fenetre = screen.getByRole("dialog", { name: "Générer la facture" });
    expect(fenetre).toHaveTextContent(/La facture F-\d{4}-… sera numérotée et ne pourra plus être modifiée\./);
    expect(fenetre).toHaveTextContent(/168,00\s€ TTC/);
    expect(apiFetch).not.toHaveBeenCalled();

    await user.click(within(fenetre).getByRole("button", { name: "Générer la facture" }));

    await vi.waitFor(() => expect(onEmise).toHaveBeenCalledWith(facture));
    expect(apiFetch).toHaveBeenCalledWith("/devis/7/facture", { method: "POST" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("annule sans rien émettre et rend le focus au bouton", async () => {
    const user = userEvent.setup({ delay: null });
    avecRequetes(<PiedFacturation statut="livre" devis={DEVIS} onEmise={vi.fn()} />);
    const bouton = screen.getByRole("button", { name: "Générer la facture" });

    await user.click(bouton);
    await user.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Annuler" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(bouton).toHaveFocus();
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("affiche le refus de l'API dans la fenêtre", async () => {
    const user = userEvent.setup({ delay: null });
    const { ApiError } = await import("@/lib/api");
    apiFetch.mockRejectedValue(new ApiError(409, "devis_deja_facture", "Ce devis est déjà facturé."));
    avecRequetes(<PiedFacturation statut="termine" devis={DEVIS} onEmise={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Générer la facture" }));
    await user.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Générer la facture" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Ce devis est déjà facturé.");
  });

  it("une fois facturé, propose le PDF et la facture au lieu du bouton", () => {
    avecRequetes(<PiedFacturation statut="livre" devis={{ ...DEVIS, facture: { id: 3, numero: "F-2026-001" } }} onEmise={vi.fn()} />);

    expect(screen.queryByRole("button", { name: "Générer la facture" })).not.toBeInTheDocument();
    const pdf = screen.getByRole("link", { name: "Télécharger le PDF" });
    expect(pdf).toHaveAttribute("href", "/api/factures/3/pdf");
    expect(pdf).toHaveAccessibleDescription(/Facture F-2026-001/);
    expect(screen.getByRole("link", { name: "Voir la facture" })).toHaveAttribute("href", "/factures/3");
  });

  it("suit la règle de l'API : « Prêt » ou « Livré »", () => {
    expect([peutFacturer("a_faire"), peutFacturer("en_cours"), peutFacturer("termine"), peutFacturer("livre")]).toEqual([false, false, true, true]);
    expect(numeroAVenir(new Date("2026-12-31T23:30:00Z"))).toBe("F-2027-…");
  });
});

const FACTURES: FactureResume[] = [
  {
    id: 3,
    numero: "F-2026-001",
    emise_le: "2026-12-02T09:00:00Z",
    echeance: "2027-01-01",
    ordre: { id: 1, numero: "OT-2026-001" },
    client: { nom: "Laurent", prenom: "Claire" },
    vehicule: { immatriculation: "GH-482-KL", marque: "Peugeot", modele: "308 SW" },
    total_ht_centimes: 37900,
    total_ttc_centimes: 45480,
    paiements: [{ id: 1, montant_centimes: 10000, mode: "cheque", recu_le: "2026-12-03T10:00:00Z", reference: "1234567", cree_par: { id: 1, nom: "Nadia Benali" } }],
    deja_paye_centimes: 10000,
    reste_centimes: 35480,
    statut_paiement: "partielle",
    en_retard: false,
  },
];

describe("onglet Factures", () => {
  it("donne à chaque lien PDF un nom accessible explicite", async () => {
    apiFetch.mockResolvedValue({ elements: FACTURES, total: 1, page: 1, taille: 50 });
    avecRequetes(<ListeFactures page={1} />);

    const lien = await screen.findByRole("link", { name: "Télécharger la facture F-2026-001 (PDF)" });
    expect(lien).toHaveAttribute("href", "/api/factures/3/pdf");
    expect(lien).toHaveTextContent("PDF");
    expect(screen.getByRole("link", { name: "F-2026-001" })).toHaveAttribute("href", "/factures/3");
    expect(screen.getByRole("img", { name: "Immatriculation GH-482-KL" })).toBeInTheDocument();
    expect(screen.getByText(/454,80\s€/)).toBeInTheDocument();
    expect(apiFetch).toHaveBeenCalledWith("/factures?page=1&taille=50", expect.anything());
  });

  it("dit quand il n'y a encore aucune facture", async () => {
    apiFetch.mockResolvedValue({ elements: [], total: 0, page: 1, taille: 50 });
    avecRequetes(<ListeFactures page={1} />);

    expect(await screen.findByText(/Aucune facture pour l'instant/)).toBeInTheDocument();
  });

  it("formate l'émission et l'échéance", () => {
    const maintenant = new Date("2026-12-10T10:00:00Z");
    expect(formatEmission("2026-12-02T09:00:00Z", maintenant)).toBe("mer. 2 déc.");
    expect(formatEmission("2025-10-24T15:00:00Z", maintenant)).toBe("ven. 24 oct. 2025");
    expect(formatJour("2027-01-01")).toBe("01/01/2027");
  });
});

const DEVIS_LISTE: DevisResume[] = [
  {
    id: 2,
    ordre: { id: 1, numero: "OT-2025-001", statut: "livre" },
    vehicule: { id: 4, immatriculation: "GH-482-KL", marque: "Peugeot", modele: "308 SW", kilometrage: 84312 },
    client: { id: 9, nom: "Laurent", prenom: "Claire" },
    statut: "accepte",
    envoye_le: "2025-10-24T07:30:00Z",
    decide_le: "2025-10-24T08:00:00Z",
    total_ht_centimes: 14000,
    total_ttc_centimes: 16800,
    cree_le: "2025-10-24T07:10:00Z",
    modifie_le: "2025-10-24T07:10:00Z",
    facture: null,
  },
];

describe("onglet Devis (revue du sprint 3)", () => {
  it("donne l'année d'un devis d'une année précédente, comme l'onglet Factures", async () => {
    apiFetch.mockResolvedValue({ elements: DEVIS_LISTE, total: 1, page: 1, taille: 50 });
    avecRequetes(<ListeDevis page={1} />);

    expect(await screen.findByText("ven. 24 oct. 2025")).toBeInTheDocument();
  });

  it("garde l'onglet affiché d'accord avec l'adresse, même quand la page est réutilisée", async () => {
    const user = userEvent.setup({ delay: null });
    apiFetch.mockResolvedValue({ elements: [], total: 0, page: 1, taille: 50 });
    navigation.chemin = "/devis";
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const page = () => (
      <QueryClientProvider client={client}>
        <DevisFactures onglet="devis" page={1} />
      </QueryClientProvider>
    );
    const { rerender } = render(page());
    const rendre = () => rerender(page());

    await user.click(screen.getByRole("tab", { name: "Factures" }));
    expect(window.location.pathname).toBe("/factures");
    navigation.chemin = window.location.pathname; // Next synchronise usePathname avec replaceState
    act(rendre);
    expect(screen.getByRole("tab", { name: "Factures" })).toHaveAttribute("aria-selected", "true");

    // Lien « Devis & factures » du menu : retour sur /devis sans remonter la page.
    navigation.chemin = "/devis";
    act(rendre);
    expect(screen.getByRole("tab", { name: "Devis" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "Factures" })).toHaveAttribute("aria-selected", "false");
  });
});
