import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ClientForm } from "@/components/clients/ClientForm";
import { FicheFacture } from "@/components/facturation/FicheFacture";
import { ToastProvider } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api";
import { CLIENT_VIDE, lignesAdresse, MESSAGE_CODE_POSTAL, versEntree, type Client } from "@/lib/clients";
import { mentionPrestation, type FactureDetail } from "@/lib/factures";

const apiFetch = vi.fn();
vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return { ...original, apiFetch: (...args: unknown[]) => apiFetch(...args) };
});
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }), usePathname: () => "/factures/3" }));

const CLIENT: Client = {
  id: 9,
  nom: "Laurent",
  prenom: "Claire",
  telephone: "0612483075",
  email: null,
  adresse: "14 rue des Établis",
  code_postal: "69003",
  ville: "Lyon",
  consentement_rappels: false,
  nombre_vehicules: 1,
  cree_le: "2026-12-21T09:00:00Z",
  modifie_le: "2026-12-21T09:00:00Z",
};

const FACTURE: FactureDetail = {
  id: 3,
  numero: "F-2026-004",
  emise_le: "2026-12-23T08:30:00Z",
  echeance: "2027-01-22",
  date_prestation: "2026-12-22",
  devis_id: 7,
  ordre: { id: 1, numero: "OT-2026-003" },
  client: { nom: "Laurent", prenom: "Claire", telephone: "0612483075", email: null, adresse: "14 rue des Établis", code_postal: "69003", ville: "Lyon" },
  vehicule: { immatriculation: "GH-482-KL", marque: "Peugeot", modele: "308 SW", kilometrage: 84312 },
  garage: { raison_sociale: "Garage Établi SARL", adresse: "12 rue des Ateliers, 69007 Lyon", siret: "0", tva_intracommunautaire: "FR0", capital: "10 000 €", rcs: "RCS", telephone: "0", email: "x" },
  lignes: [],
  taux_tva_bp: 2000,
  totaux: { main_oeuvre_ht_centimes: 0, pieces_ht_centimes: 0, total_ht_centimes: 0, total_tva_centimes: 0, total_ttc_centimes: 0 },
  paiements: [],
  deja_paye_centimes: 0,
  reste_centimes: 0,
  statut_paiement: "payee",
  en_retard: false,
};

function avecRequetes(enfant: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>{enfant}</ToastProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  apiFetch.mockReset();
});

describe("règles de l'adresse", () => {
  it("donne les lignes renseignées de l'adresse", () => {
    expect(lignesAdresse(CLIENT)).toEqual(["14 rue des Établis", "69003 Lyon"]);
    expect(lignesAdresse({ adresse: null, code_postal: null, ville: "Lyon" })).toEqual(["Lyon"]);
    expect(lignesAdresse({})).toEqual([]);
  });

  it("envoie null pour une adresse laissée vide", () => {
    expect(versEntree({ ...CLIENT_VIDE, nom: "Laurent", telephone: "0612483075", adresse: "  ", ville: " Lyon " })).toMatchObject({ adresse: null, code_postal: null, ville: "Lyon" });
  });

  it("n'annonce la date de prestation que si elle diffère du jour d'émission à Paris", () => {
    expect(mentionPrestation("2026-12-22", "2026-12-23T08:30:00Z")).toBe("Prestation réalisée le 22/12/2026");
    expect(mentionPrestation("2026-12-23", "2026-12-23T08:30:00Z")).toBeNull();
    // 23 h 30 UTC le 22 = 0 h 30 le 23 à Paris : même jour que la prestation du 23.
    expect(mentionPrestation("2026-12-23", "2026-12-22T23:30:00Z")).toBeNull();
    expect(mentionPrestation(null, "2026-12-23T08:30:00Z")).toBeNull();
  });
});

describe("formulaire client : adresse", () => {
  it("propose l'adresse, le code postal et la ville, facultatifs, dans un groupe nommé", () => {
    render(<ClientForm mode="creation" envoyer={vi.fn()} onSucces={vi.fn()} />);
    const groupe = screen.getByRole("group", { name: /Adresse postale, facultative/ });
    expect(within(groupe).getByLabelText("Adresse")).not.toBeRequired();
    expect(within(groupe).getByLabelText("Code postal")).toHaveAttribute("autocomplete", "postal-code");
    expect(within(groupe).getByLabelText("Ville")).toHaveAttribute("autocomplete", "address-level2");
  });

  it("refuse un code postal qui n'a pas 5 chiffres, sous le champ", async () => {
    const user = userEvent.setup({ delay: null });
    const envoyer = vi.fn();
    render(<ClientForm mode="creation" envoyer={envoyer} onSucces={vi.fn()} />);
    await user.type(screen.getByLabelText(/^nom/i), "Laurent");
    await user.type(screen.getByLabelText(/téléphone/i), "06 12 48 30 75");
    await user.type(screen.getByLabelText("Code postal"), "6900");
    await user.click(screen.getByRole("button", { name: "Créer le client" }));
    expect(await screen.findByText(MESSAGE_CODE_POSTAL)).toBeInTheDocument();
    expect(screen.getByLabelText("Code postal")).toHaveAttribute("aria-invalid", "true");
    expect(envoyer).not.toHaveBeenCalled();
  });

  it("envoie l'adresse saisie", async () => {
    const user = userEvent.setup({ delay: null });
    const envoyer = vi.fn().mockResolvedValue(CLIENT);
    render(<ClientForm mode="creation" envoyer={envoyer} onSucces={vi.fn()} />);
    await user.type(screen.getByLabelText(/^nom/i), "Laurent");
    await user.type(screen.getByLabelText(/téléphone/i), "06 12 48 30 75");
    await user.type(screen.getByLabelText("Adresse"), "14 rue des Établis");
    await user.type(screen.getByLabelText("Code postal"), "69003");
    await user.type(screen.getByLabelText("Ville"), "Lyon");
    await user.click(screen.getByRole("button", { name: "Créer le client" }));
    await vi.waitFor(() => expect(envoyer).toHaveBeenCalledWith(expect.objectContaining({ adresse: "14 rue des Établis", code_postal: "69003", ville: "Lyon" }), false));
  });

  it("rattache l'erreur de l'API au code postal", async () => {
    const user = userEvent.setup({ delay: null });
    const envoyer = vi.fn().mockRejectedValue(new ApiError(422, "validation", "Certains champs sont invalides.", { code_postal: MESSAGE_CODE_POSTAL }));
    render(<ClientForm mode="creation" envoyer={envoyer} onSucces={vi.fn()} />);
    await user.type(screen.getByLabelText(/^nom/i), "Laurent");
    await user.type(screen.getByLabelText(/téléphone/i), "06 12 48 30 75");
    await user.click(screen.getByRole("button", { name: "Créer le client" }));
    await vi.waitFor(() => expect(screen.getByLabelText("Code postal")).toHaveAccessibleDescription(MESSAGE_CODE_POSTAL));
  });
});

describe("page de la facture : mentions", () => {
  it("montre l'adresse figée du client et la date de la prestation", async () => {
    apiFetch.mockResolvedValue(FACTURE);
    avecRequetes(<FicheFacture factureId={3} />);
    const client = await screen.findByRole("region", { name: "Client" });
    expect(within(client).getByText("14 rue des Établis")).toBeInTheDocument();
    expect(within(client).getByText("69003 Lyon")).toBeInTheDocument();
    expect(screen.getByText(/prestation réalisée le 22\/12\/2026/)).toBeInTheDocument();
  });

  it("une facture émise avant le sprint 4 s'affiche sans adresse ni date de prestation", async () => {
    apiFetch.mockResolvedValue({ ...FACTURE, date_prestation: null, client: { ...FACTURE.client, adresse: null, code_postal: null, ville: null } });
    avecRequetes(<FicheFacture factureId={3} />);
    const client = await screen.findByRole("region", { name: "Client" });
    expect(within(client).queryByRole("group")).not.toBeInTheDocument();
    expect(client.querySelector("address")).toBeNull();
    expect(screen.queryByText(/prestation réalisée/)).not.toBeInTheDocument();
  });
});
