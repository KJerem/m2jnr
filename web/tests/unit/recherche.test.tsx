import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ChampRecherche } from "@/components/recherche/ChampRecherche";
import { PageRecherche } from "@/components/recherche/PageRecherche";
import { ApiError } from "@/lib/api";
import { erreurSaisie, libelleNombre, lienRecherche, messageAucunResultat, MESSAGE_TROP_COURT, MESSAGE_TROP_LONG, nombreResultats, type ResultatsRecherche } from "@/lib/recherche";

const apiFetch = vi.fn();
vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return { ...original, apiFetch: (...args: unknown[]) => apiFetch(...args) };
});
const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push, replace: vi.fn() }) }));

const VIDE: ResultatsRecherche = { q: "xyz", clients: [], vehicules: [], ordres: [], factures: [] };
const PLEIN: ResultatsRecherche = {
  q: "gh482kl",
  clients: [{ id: 9, nom: "Laurent", prenom: "Claire", telephone: "0612483075", nb_vehicules: 2 }],
  vehicules: [{ id: 4, immatriculation: "GH-482-KL", marque: "Peugeot", modele: "308 SW", proprietaire: { id: 9, nom: "Laurent", prenom: "Claire" } }],
  ordres: [
    { id: 3, numero: "OT-2026-003", statut: "en_cours", immatriculation: "GH-482-KL", marque: "Peugeot", modele: "308 SW" },
    { id: 1, numero: "OT-2026-001", statut: "livre", immatriculation: "GH-482-KL", marque: "Peugeot", modele: "308 SW" },
  ],
  factures: [{ id: 5, numero: "F-2026-001", emise_le: "2026-12-22T09:00:00Z", total_ttc_centimes: 45480, client: { nom: "Laurent", prenom: "Claire" } }],
};

function afficher(q: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <PageRecherche q={q} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  apiFetch.mockReset();
  push.mockReset();
});

describe("règles de la saisie", () => {
  it("demande 2 à 100 caractères, espaces de bord retirés", () => {
    expect(erreurSaisie("")).toBe(MESSAGE_TROP_COURT);
    expect(erreurSaisie("  a  ")).toBe(MESSAGE_TROP_COURT);
    expect(erreurSaisie("ab")).toBeNull();
    expect(erreurSaisie("x".repeat(100))).toBeNull();
    expect(erreurSaisie("x".repeat(101))).toBe(MESSAGE_TROP_LONG);
  });

  it("encode la saisie dans l'adresse de la page", () => {
    expect(lienRecherche(" gh482kl ")).toBe("/recherche?q=gh482kl");
    expect(lienRecherche("O'Brien & fils 50 %")).toBe("/recherche?q=O'Brien%20%26%20fils%2050%20%25");
  });

  it("écrit le message d'absence de résultat et le nombre", () => {
    expect(messageAucunResultat("xyz")).toBe("Aucun résultat pour « xyz ». Vérifiez l'orthographe, ou cherchez un numéro de téléphone ou une immatriculation.");
    expect(libelleNombre(1)).toBe("1 résultat");
    expect(libelleNombre(5)).toBe("5 résultats");
    expect(nombreResultats(PLEIN)).toBe(5);
  });
});

describe("champ « Rechercher »", () => {
  it("a une étiquette, le texte d'aide de la maquette et un rôle de recherche", () => {
    render(<ChampRecherche />);
    expect(screen.getByRole("search")).toBeInTheDocument();
    const champ = screen.getByRole("searchbox", { name: "Rechercher" });
    expect(champ).toHaveAttribute("placeholder", "Plaque, client, n° d'OT");
    expect(screen.getByRole("button", { name: "Lancer la recherche" })).toHaveAttribute("type", "submit");
  });

  it("mène à la page de résultats avec Entrée", async () => {
    const user = userEvent.setup({ delay: null });
    render(<ChampRecherche />);
    await user.type(screen.getByRole("searchbox", { name: "Rechercher" }), "  gh482kl {Enter}");
    expect(push).toHaveBeenCalledWith("/recherche?q=gh482kl");
  });

  it("signale une saisie trop courte sous le champ, sans quitter la page, puis l'efface à la frappe", async () => {
    const user = userEvent.setup({ delay: null });
    render(<ChampRecherche />);
    const champ = screen.getByRole("searchbox", { name: "Rechercher" });
    await user.type(champ, "a");
    await user.click(screen.getByRole("button", { name: "Lancer la recherche" }));
    expect(push).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent(MESSAGE_TROP_COURT);
    expect(champ).toHaveAttribute("aria-invalid", "true");
    expect(champ).toHaveAccessibleDescription(MESSAGE_TROP_COURT);
    expect(champ).toHaveFocus();
    await user.type(champ, "b");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

describe("page « Recherche »", () => {
  it("interroge l'API avec la saisie encodée et annonce le chargement", async () => {
    apiFetch.mockReturnValue(new Promise(() => {}));
    afficher("O'Brien 50 %");
    expect(screen.getByRole("heading", { level: 1, name: "Recherche" })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Recherche en cours…");
    expect(apiFetch).toHaveBeenCalledWith("/recherche?q=O'Brien%2050%20%25", expect.anything());
    expect(screen.getByRole("searchbox", { name: "Rechercher" })).toHaveValue("O'Brien 50 %");
  });

  it("groupe les résultats avec leur nombre dans chaque titre, chacun étant un lien", async () => {
    apiFetch.mockResolvedValue(PLEIN);
    afficher("gh482kl");
    expect(await screen.findByText("5 résultats pour « gh482kl ».")).toHaveAttribute("role", "status");

    const clients = screen.getByRole("region", { name: "Clients (1)" });
    expect(within(clients).getByRole("link", { name: /Claire Laurent/ })).toHaveAttribute("href", "/clients/9");
    expect(within(clients).getByText(/2 véhicules/)).toBeInTheDocument();

    const vehicules = screen.getByRole("region", { name: "Véhicules (1)" });
    const lienVehicule = within(vehicules).getByRole("link");
    expect(lienVehicule).toHaveAttribute("href", "/vehicules/4");
    expect(lienVehicule).toHaveTextContent("GH-482-KL");
    expect(lienVehicule).toHaveTextContent("Peugeot 308 SW");

    const ordres = screen.getByRole("region", { name: "Ordres de travail (2)" });
    const [enCours, livre] = within(ordres).getAllByRole("link");
    expect(enCours).toHaveAttribute("href", "/ordres/3");
    expect(enCours).toHaveTextContent("OT-2026-003");
    expect(enCours).toHaveTextContent("En cours");
    expect(livre).toHaveTextContent("Livré");

    const factures = screen.getByRole("region", { name: "Factures (1)" });
    const lienFacture = within(factures).getByRole("link");
    expect(lienFacture).toHaveAttribute("href", "/factures/5");
    expect(lienFacture).toHaveTextContent("F-2026-001");
    expect(lienFacture).toHaveTextContent("454,80 €");
  });

  it("n'affiche que les rubriques qui ont des résultats", async () => {
    apiFetch.mockResolvedValue({ ...VIDE, q: "laurent", clients: PLEIN.clients });
    afficher("laurent");
    expect(await screen.findByRole("region", { name: "Clients (1)" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: /Véhicules/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: /Factures/ })).not.toBeInTheDocument();
    expect(screen.getByText("1 résultat pour « laurent ».")).toBeInTheDocument();
  });

  it("donne un message clair quand il n'y a aucun résultat", async () => {
    apiFetch.mockResolvedValue(VIDE);
    afficher("xyz");
    expect(await screen.findByText(messageAucunResultat("xyz"))).toHaveAttribute("role", "status");
    expect(screen.queryByRole("region")).not.toBeInTheDocument();
  });

  it("affiche le 422 de l'API sous le champ, sans encadré d'erreur", async () => {
    apiFetch.mockRejectedValue(new ApiError(422, "validation", MESSAGE_TROP_COURT, { q: MESSAGE_TROP_COURT }));
    afficher("a");
    expect(await screen.findByRole("alert")).toHaveTextContent(MESSAGE_TROP_COURT);
    expect(screen.getByRole("searchbox", { name: "Rechercher" })).toHaveAccessibleDescription(MESSAGE_TROP_COURT);
    expect(screen.queryByText(/Aucun résultat/)).not.toBeInTheDocument();
  });

  it("affiche une autre erreur dans un encadré", async () => {
    apiFetch.mockRejectedValue(new ApiError(500, "erreur", "Le serveur a renvoyé une erreur. Réessayez."));
    afficher("diallo");
    expect(await screen.findByRole("alert")).toHaveTextContent("Le serveur a renvoyé une erreur. Réessayez.");
  });

  it("n'interroge pas l'API sans saisie", () => {
    afficher("   ");
    expect(apiFetch).not.toHaveBeenCalled();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("annonce les 20 premiers résultats d'une rubrique pleine", async () => {
    const clients = Array.from({ length: 20 }, (_, i) => ({ ...PLEIN.clients[0]!, id: i + 1, nom: `Bernard${i}` }));
    apiFetch.mockResolvedValue({ ...VIDE, q: "bernard", clients });
    afficher("bernard");
    const rubrique = await screen.findByRole("region", { name: "Clients (20)" });
    expect(within(rubrique).getByText("Les 20 premiers : précisez la recherche.")).toBeInTheDocument();
  });
});
