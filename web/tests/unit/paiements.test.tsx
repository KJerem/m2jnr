import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ListeFactures } from "@/components/facturation/ListeFactures";
import { BadgesPaiement, cleFacture, PaiementsFacture } from "@/components/facturation/PaiementsFacture";
import { ToastProvider } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api";
import {
  filtrePaiement,
  lienFactures,
  lireMontant,
  MESSAGE_MONTANT_INVALIDE,
  MESSAGE_MONTANT_NUL,
  messageTropPercu,
  montantSaisi,
  type FactureDetail,
  type FactureResume,
} from "@/lib/factures";

const apiFetch = vi.fn();
vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return { ...original, apiFetch: (...args: unknown[]) => apiFetch(...args) };
});

const FACTURE: FactureDetail = {
  id: 3,
  numero: "F-2026-002",
  emise_le: "2026-12-22T09:40:00Z",
  echeance: "2027-01-21",
  devis_id: 7,
  ordre: { id: 1, numero: "OT-2026-003" },
  client: { nom: "Laurent", prenom: "Claire", telephone: "0612483075", email: null, adresse: null, code_postal: null, ville: null },
  date_prestation: null,
  vehicule: { immatriculation: "GH-482-KL", marque: "Peugeot", modele: "308 SW", kilometrage: 84312 },
  garage: { raison_sociale: "Garage Établi SARL", adresse: "12 rue des Ateliers, 69007 Lyon", siret: "0", tva_intracommunautaire: "FR0", capital: "10 000 €", rcs: "RCS", telephone: "0", email: "x" },
  lignes: [],
  taux_tva_bp: 2000,
  totaux: { main_oeuvre_ht_centimes: 6000, pieces_ht_centimes: 8000, total_ht_centimes: 14000, total_tva_centimes: 2800, total_ttc_centimes: 16800 },
  paiements: [],
  deja_paye_centimes: 0,
  reste_centimes: 16800,
  statut_paiement: "impayee",
  en_retard: false,
};

const PAIEMENT = { id: 1, montant_centimes: 5000, mode: "cheque" as const, recu_le: "2026-12-22T09:15:00Z", reference: "1234567", cree_par: { id: 1, nom: "Nadia Benali" } };
const PARTIELLE: FactureDetail = { ...FACTURE, paiements: [PAIEMENT], deja_paye_centimes: 5000, reste_centimes: 11800, statut_paiement: "partielle" };
const PAYEE: FactureDetail = {
  ...FACTURE,
  paiements: [PAIEMENT, { ...PAIEMENT, id: 2, montant_centimes: 11800, mode: "carte", reference: null, recu_le: "2026-12-22T10:15:00Z" }],
  deja_paye_centimes: 16800,
  reste_centimes: 0,
  statut_paiement: "payee",
};

/** « Reste à payer : 118,00 € » (montant en grand, focalisable). */
function resteAPayer(): HTMLElement {
  return screen.getByText((_, element) => element?.tagName === "P" && /^Reste à payer :/.test(element.textContent ?? ""));
}

/** Comme la page : le panneau lit la facture dans le cache de requêtes ; l'API simulée
 * renvoie `apres` au paiement, et la facture relue est alors celle-là. */
function HoteFacture({ avant, apres }: { avant: FactureDetail; apres: FactureDetail }) {
  const { data } = useQuery({ queryKey: cleFacture(avant.id), queryFn: () => (apiFetch.mock.calls.length > 0 ? apres : avant), initialData: avant });
  return <PaiementsFacture facture={data} />;
}

function avecRequetes(enfant: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>{enfant}</ToastProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  apiFetch.mockReset();
});

describe("règles du montant saisi", () => {
  it("pré-remplit avec le reste à payer, virgule française", () => {
    expect(montantSaisi(16800)).toBe("168,00");
    expect(montantSaisi(1240)).toBe("12,40");
    expect(montantSaisi(5)).toBe("0,05");
  });

  it("lit les euros en centimes et refuse zéro, le texte et le trop-perçu", () => {
    expect(lireMontant("50", 16800)).toEqual({ centimes: 5000 });
    expect(lireMontant("120,5", 16800)).toEqual({ centimes: 12050 });
    expect(lireMontant(" 168.00 € ", 16800)).toEqual({ centimes: 16800 });
    expect(lireMontant("0", 16800)).toEqual({ erreur: MESSAGE_MONTANT_NUL });
    expect(lireMontant("0,00", 16800)).toEqual({ erreur: MESSAGE_MONTANT_NUL });
    expect(lireMontant("-5", 16800)).toEqual({ erreur: MESSAGE_MONTANT_INVALIDE });
    expect(lireMontant("douze", 16800)).toEqual({ erreur: MESSAGE_MONTANT_INVALIDE });
    expect(lireMontant("12,345", 16800)).toEqual({ erreur: MESSAGE_MONTANT_INVALIDE });
    expect(lireMontant("12,41", 1240)).toEqual({ erreur: messageTropPercu(1240) });
    expect(messageTropPercu(1240)).toMatch(/^Le paiement dépasse le reste à payer \(12,40\s€\)\.$/);
  });

  it("lit le filtre de l'adresse et construit celle de l'onglet", () => {
    expect(filtrePaiement("partielle")).toBe("partielle");
    expect(filtrePaiement("autre")).toBe("toutes");
    expect(filtrePaiement(undefined)).toBe("toutes");
    expect(lienFactures("toutes")).toBe("/factures");
    expect(lienFactures("impayee")).toBe("/factures?paiement=impayee");
    expect(lienFactures("payee", 2)).toBe("/factures?paiement=payee&page=2");
  });
});

describe("badges du statut de paiement", () => {
  it.each([
    ["impayee", "Impayée", "et-status-attente"],
    ["partielle", "Partiellement payée", "et-status-en-cours"],
    ["payee", "Payée", "et-status-pret"],
  ] as const)("%s : pastille et mot", (statut, mot, classe) => {
    const { container } = render(<BadgesPaiement statut={statut} enRetard={false} />);
    const badge = screen.getByText(mot);
    expect(badge).toHaveClass("et-status", classe);
    expect(badge.querySelector(".et-dot")).not.toBeNull();
    expect(container).not.toHaveTextContent("En retard");
  });

  it("écrit « En retard » en toutes lettres, pas seulement en couleur", () => {
    render(<BadgesPaiement statut="partielle" enRetard />);
    expect(screen.getByText("En retard")).toHaveClass("et-status-urgent");
  });
});

describe("panneau « Paiements »", () => {
  it("montre le solde et pré-remplit le montant avec le reste à payer", () => {
    avecRequetes(<PaiementsFacture facture={PARTIELLE} />);
    const panneau = screen.getByRole("region", { name: "Paiements" });
    expect(within(panneau).getByText("Partiellement payée")).toBeInTheDocument();
    expect(panneau).toHaveTextContent(/Déjà payé\s*50,00\s€/);
    expect(resteAPayer()).toHaveTextContent(/118,00\s€/);
    const ligne = within(panneau).getAllByRole("row")[1]!;
    expect(ligne).toHaveTextContent("mar. 22 déc. à 10 h 15");
    expect(ligne).toHaveTextContent("Chèque");
    expect(ligne).toHaveTextContent("1234567");
    expect(ligne).toHaveTextContent(/50,00\s€/);
    expect(screen.getByLabelText(/Montant/)).toHaveValue("118,00");
    expect(screen.getByLabelText(/Mode/)).toHaveValue("carte");
    expect(screen.getByRole("option", { name: "Carte bancaire (terminal)" })).toBeInTheDocument();
  });

  it("dit qu'aucun paiement n'est enregistré", () => {
    avecRequetes(<PaiementsFacture facture={FACTURE} />);
    expect(screen.getByText("Aucun paiement enregistré.")).toBeInTheDocument();
    expect(screen.getByLabelText(/Montant/)).toHaveValue("168,00");
  });

  it("cache le formulaire quand la facture est payée", () => {
    avecRequetes(<PaiementsFacture facture={PAYEE} />);
    expect(screen.queryByRole("form")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Enregistrer le paiement" })).not.toBeInTheDocument();
    expect(screen.getAllByText("Payée").length).toBeGreaterThan(0);
    expect(screen.getAllByRole("row")).toHaveLength(3);
  });

  it("refuse un montant invalide ou trop élevé sous le champ, sans appeler l'API", async () => {
    const user = userEvent.setup({ delay: null });
    avecRequetes(<PaiementsFacture facture={PARTIELLE} />);
    const montant = screen.getByLabelText(/Montant/);

    await user.clear(montant);
    await user.type(montant, "0");
    await user.click(screen.getByRole("button", { name: "Enregistrer le paiement" }));
    expect(montant).toHaveAccessibleDescription(MESSAGE_MONTANT_NUL);
    expect(montant).toHaveAttribute("aria-invalid", "true");
    expect(montant).toHaveFocus();

    await user.clear(montant);
    await user.type(montant, "118,01");
    await user.click(screen.getByRole("button", { name: "Enregistrer le paiement" }));
    expect(montant).toHaveAccessibleDescription(messageTropPercu(11800));
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("enregistre un paiement partiel : envoi, toast, nouveau reste et focus sur le montant", async () => {
    const user = userEvent.setup({ delay: null });
    apiFetch.mockResolvedValue(PARTIELLE);
    avecRequetes(<HoteFacture avant={FACTURE} apres={PARTIELLE} />);
    const montant = screen.getByLabelText(/Montant/);

    await user.clear(montant);
    await user.type(montant, "50");
    await user.selectOptions(screen.getByLabelText(/Mode/), "cheque");
    await user.type(screen.getByLabelText(/Référence/), " 1234567 ");
    await user.click(screen.getByRole("button", { name: "Enregistrer le paiement" }));

    expect(apiFetch).toHaveBeenCalledWith("/factures/3/paiements", { method: "POST", body: { montant_centimes: 5000, mode: "cheque", reference: "1234567" } });
    expect(await screen.findByText(/Paiement de 50,00\s€ enregistré\. Reste à payer : 118,00\s€\./)).toBeInTheDocument();
    expect(screen.getByText("Partiellement payée")).toBeInTheDocument();
    expect(screen.getByLabelText(/Montant/)).toHaveValue("118,00");
    expect(screen.getByLabelText(/Référence/)).toHaveValue("");
    await vi.waitFor(() => expect(screen.getByLabelText(/Montant/)).toHaveFocus());
  });

  it("solde la facture : formulaire retiré, focus sur le reste à payer", async () => {
    const user = userEvent.setup({ delay: null });
    apiFetch.mockResolvedValue(PAYEE);
    avecRequetes(<HoteFacture avant={PARTIELLE} apres={PAYEE} />);
    await user.click(screen.getByRole("button", { name: "Enregistrer le paiement" }));
    expect(apiFetch).toHaveBeenCalledWith("/factures/3/paiements", { method: "POST", body: { montant_centimes: 11800, mode: "carte" } });
    expect(await screen.findByText(/facture F-2026-002 payée\./)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Enregistrer le paiement" })).not.toBeInTheDocument();
    await vi.waitFor(() => expect(resteAPayer()).toHaveFocus());
  });

  it("envoie la date et l'heure saisies, lues à l'heure du garage par l'API", async () => {
    const user = userEvent.setup({ delay: null });
    apiFetch.mockResolvedValue(PARTIELLE);
    avecRequetes(<PaiementsFacture facture={FACTURE} />);
    const date = screen.getByLabelText(/Reçu le/);
    await user.type(date, "2026-12-22T10:15");
    await user.click(screen.getByRole("button", { name: "Enregistrer le paiement" }));
    expect(apiFetch).toHaveBeenCalledWith("/factures/3/paiements", { method: "POST", body: { montant_centimes: 16800, mode: "carte", recu_le: "2026-12-22T10:15" } });
  });

  it("rattache le trop-perçu de l'API au montant, avec le reste renvoyé", async () => {
    const user = userEvent.setup({ delay: null });
    apiFetch.mockRejectedValue(new ApiError(409, "trop_percu", messageTropPercu(1240), {}, { reste_centimes: 1240 }));
    avecRequetes(<PaiementsFacture facture={FACTURE} />);
    await user.click(screen.getByRole("button", { name: "Enregistrer le paiement" }));
    const montant = screen.getByLabelText(/Montant/);
    await vi.waitFor(() => expect(montant).toHaveAccessibleDescription(messageTropPercu(1240)));
    expect(montant).toHaveFocus();
  });

  it("rattache une erreur 422 de l'API à son champ", async () => {
    const user = userEvent.setup({ delay: null });
    const message = "La date de réception ne peut pas être dans le futur.";
    apiFetch.mockRejectedValue(new ApiError(422, "validation", "Certains champs sont invalides.", { recu_le: message }));
    avecRequetes(<PaiementsFacture facture={FACTURE} />);
    await user.click(screen.getByRole("button", { name: "Enregistrer le paiement" }));
    const date = screen.getByLabelText(/Reçu le/);
    await vi.waitFor(() => expect(date).toHaveAccessibleDescription(message));
    expect(date).toHaveFocus();
  });
});

describe("onglet Factures", () => {
  const RESUME: FactureResume = {
    id: 3,
    numero: "F-2026-002",
    emise_le: "2026-12-22T09:40:00Z",
    echeance: "2027-01-21",
    ordre: { id: 1, numero: "OT-2026-003" },
    client: { nom: "Laurent", prenom: "Claire" },
    vehicule: { immatriculation: "GH-482-KL", marque: "Peugeot", modele: "308 SW" },
    total_ht_centimes: 14000,
    total_ttc_centimes: 16800,
    paiements: [PAIEMENT],
    deja_paye_centimes: 5000,
    reste_centimes: 11800,
    statut_paiement: "partielle",
    en_retard: true,
  };

  it("montre le statut de paiement et le reste, puis filtre avec des boutons à bascule", async () => {
    const user = userEvent.setup({ delay: null });
    apiFetch.mockResolvedValue({ elements: [RESUME], total: 1, page: 1, taille: 50 });
    avecRequetes(<ListeFactures page={1} />);

    const ligne = (await screen.findAllByRole("row"))[1]!;
    expect(within(ligne).getByText("Partiellement payée")).toBeInTheDocument();
    expect(within(ligne).getByText("En retard")).toBeInTheDocument();
    expect(ligne).toHaveTextContent(/118,00\s€/);

    const groupe = screen.getByRole("group", { name: "Filtrer par statut de paiement" });
    const toutes = within(groupe).getByRole("button", { name: "Toutes" });
    const partielles = within(groupe).getByRole("button", { name: "Partielles" });
    expect(toutes).toHaveAttribute("aria-pressed", "true");
    expect(apiFetch).toHaveBeenLastCalledWith("/factures?page=1&taille=50", expect.anything());

    await user.click(partielles);
    expect(partielles).toHaveAttribute("aria-pressed", "true");
    expect(toutes).toHaveAttribute("aria-pressed", "false");
    expect(partielles).toHaveFocus();
    expect(apiFetch).toHaveBeenLastCalledWith("/factures?page=1&taille=50&statut_paiement=partielle", expect.anything());
    expect(window.location.search).toBe("?paiement=partielle");
  });

  it("dit quand un filtre ne contient aucune facture", async () => {
    apiFetch.mockResolvedValue({ elements: [], total: 0, page: 1, taille: 50 });
    avecRequetes(<ListeFactures page={1} paiement="payee" />);
    expect(await screen.findByText("Aucune facture dans ce filtre.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Payées" })).toHaveAttribute("aria-pressed", "true");
    expect(apiFetch).toHaveBeenCalledWith("/factures?page=1&taille=50&statut_paiement=payee", expect.anything());
  });
});
