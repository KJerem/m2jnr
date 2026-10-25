import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ClientsListe, lienClients, messageAucunClient } from "@/components/clients/ClientsListe";
import { lienOrdres, messageAucunOrdre, OrdresListe } from "@/components/ordres/OrdresListe";
import { SESSION_KEY } from "@/components/session/useSession";
import { ChampRechercheListe, DELAI_RECHERCHE_MS, MESSAGE_RECHERCHE_COURTE } from "@/components/ui/ChampRechercheListe";
import { lienVehicules, messageAucunVehicule, VehiculesListe } from "@/components/vehicules/VehiculesListe";
import type { Vehicule } from "@/lib/vehicules";
import { lienFactures } from "@/lib/factures";
import { aucunResultat, lienListe, texteDeRecherche } from "@/lib/pages";

const apiFetch = vi.fn();
vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return { ...original, apiFetch: (...args: unknown[]) => apiFetch(...args) };
});
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }), usePathname: () => window.location.pathname, useSearchParams: () => new URLSearchParams(window.location.search) }));

const NADIA = { id: 1, email: "nadia@garage.test", prenom: "Nadia", nom: "Benali", nom_affiche: "Nadia Benali", role: "gerant" as const };
const KARIM = { id: 7, email: "karim@garage.test", prenom: "Karim", nom: "B.", nom_affiche: "Karim B.", role: "mecanicien" as const };

const PEUGEOT: Vehicule = {
  id: 4,
  immatriculation: "GH-482-KL",
  marque: "Peugeot",
  modele: "308 SW",
  kilometrage: 84312,
  client_id: 12,
  vin: "VF3LBHZTEFS123456",
  date_mise_en_circulation: null,
  proprietaire: { id: 12, nom: "Laurent", prenom: "Claire" },
  cree_le: "2026-11-02T09:00:00Z",
  modifie_le: "2026-11-02T09:00:00Z",
};

function page<T>(elements: T[], total = elements.length) {
  return { elements, total, page: 1, taille: 20 };
}

function afficher(enfant: ReactNode, utilisateur: typeof NADIA | typeof KARIM = NADIA) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  client.setQueryData(SESSION_KEY, { utilisateur });
  return render(<QueryClientProvider client={client}>{enfant}</QueryClientProvider>);
}

beforeEach(() => {
  apiFetch.mockReset();
});

afterEach(() => {
  vi.useRealTimers();
  window.history.replaceState(null, "", "/");
});

describe("adresses et messages des listes", () => {
  it("écrit l'adresse d'une liste sans paramètre vide ni page 1", () => {
    expect(lienListe("/clients", { q: "laurent", page: 2 })).toBe("/clients?q=laurent&page=2");
    expect(lienListe("/clients", { q: "", page: 1 })).toBe("/clients");
    expect(lienClients("é è")).toBe("/clients?q=%C3%A9+%C3%A8");
    expect(lienVehicules("gh482", 3)).toBe("/vehicules?q=gh482&page=3");
    expect(lienOrdres("en_cours", 1, "clio")).toBe("/ordres?statut=en_cours&q=clio");
    expect(lienFactures("impayee", 2, "laurent")).toBe("/factures?paiement=impayee&q=laurent&page=2");
  });

  it("lit ?q= sans espaces de bord, 100 caractères au plus", () => {
    expect(texteDeRecherche("  laurent ")).toBe("laurent");
    expect(texteDeRecherche(["a", "b"])).toBe("");
    expect(texteDeRecherche(undefined)).toBe("");
    expect(texteDeRecherche("x".repeat(150))).toHaveLength(100);
    // Moins de 2 caractères : l'API la refuserait, la liste s'affiche sans filtre.
    expect(texteDeRecherche(" a ")).toBe("");
    expect(texteDeRecherche("ab")).toBe("ab");
  });

  it("dit clairement qu'une recherche ne trouve rien", () => {
    expect(aucunResultat("Aucun client", "xyz")).toBe("Aucun client ne correspond à « xyz ».");
    expect(messageAucunClient("xyz", 0)).toBe("Aucun client ne correspond à « xyz ».");
    expect(messageAucunClient("", 0)).toBe("Aucun client pour l'instant. Créez la première fiche.");
    expect(messageAucunVehicule("xyz")).toBe("Aucun véhicule ne correspond à « xyz ».");
    expect(messageAucunOrdre("en_cours", "xyz")).toBe("Aucun ordre de travail « En cours » ne correspond à « xyz ».");
    expect(messageAucunOrdre(null, "")).toBe("Aucun ordre de travail pour l'instant.");
  });
});

describe("champ de recherche d'une liste", () => {
  it("est un formulaire de recherche avec une étiquette visible", () => {
    render(<ChampRechercheListe libelle="Rechercher un client" onRecherche={vi.fn()} />);
    expect(screen.getByRole("search", { name: "Rechercher un client" })).toBeInTheDocument();
    expect(screen.getByRole("searchbox", { name: "Rechercher un client" })).toHaveAttribute("type", "search");
  });

  it("lance la recherche 300 ms après la dernière frappe, une seule fois", async () => {
    vi.useFakeTimers();
    const onRecherche = vi.fn();
    render(<ChampRechercheListe libelle="Rechercher un client" onRecherche={onRecherche} />);
    const champ = screen.getByRole("searchbox", { name: "Rechercher un client" });

    fireEvent.change(champ, { target: { value: "lau" } });
    act(() => vi.advanceTimersByTime(DELAI_RECHERCHE_MS - 50));
    fireEvent.change(champ, { target: { value: "laurent" } });
    act(() => vi.advanceTimersByTime(DELAI_RECHERCHE_MS - 1));
    expect(onRecherche).not.toHaveBeenCalled();

    act(() => vi.advanceTimersByTime(1));
    expect(onRecherche).toHaveBeenCalledTimes(1);
    expect(onRecherche).toHaveBeenCalledWith("laurent");
  });

  it("applique la saisie en attente dès que le champ perd le focus (clic sur une ligne)", () => {
    vi.useFakeTimers();
    const onRecherche = vi.fn();
    render(<ChampRechercheListe libelle="Rechercher un client" onRecherche={onRecherche} />);
    const champ = screen.getByRole("searchbox", { name: "Rechercher un client" });

    fireEvent.change(champ, { target: { value: "laurent" } });
    fireEvent.blur(champ);

    expect(onRecherche).toHaveBeenCalledTimes(1);
    expect(onRecherche).toHaveBeenCalledWith("laurent");
    act(() => vi.advanceTimersByTime(DELAI_RECHERCHE_MS));
    expect(onRecherche).toHaveBeenCalledTimes(1);
    // Sans saisie en attente, quitter le champ ne relance rien.
    fireEvent.focus(champ);
    fireEvent.blur(champ);
    expect(onRecherche).toHaveBeenCalledTimes(1);
  });

  it("Entrée lance la recherche tout de suite, sans second appel après le délai", async () => {
    const onRecherche = vi.fn();
    const user = userEvent.setup({ delay: null });
    render(<ChampRechercheListe libelle="Rechercher un client" onRecherche={onRecherche} />);

    await user.type(screen.getByRole("searchbox", { name: "Rechercher un client" }), "  diallo {Enter}");

    expect(onRecherche).toHaveBeenCalledTimes(1);
    expect(onRecherche).toHaveBeenCalledWith("diallo");
    await new Promise((fin) => setTimeout(fin, DELAI_RECHERCHE_MS + 50));
    expect(onRecherche).toHaveBeenCalledTimes(1);
  });

  it("refuse un seul caractère avec Entrée, message rattaché au champ", async () => {
    const onRecherche = vi.fn();
    const user = userEvent.setup({ delay: null });
    render(<ChampRechercheListe libelle="Rechercher un client" onRecherche={onRecherche} />);
    const champ = screen.getByRole("searchbox", { name: "Rechercher un client" });

    await user.type(champ, "a{Enter}");

    expect(onRecherche).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent(MESSAGE_RECHERCHE_COURTE);
    expect(champ).toHaveAttribute("aria-invalid", "true");
    expect(champ).toHaveAccessibleDescription(MESSAGE_RECHERCHE_COURTE);
    expect(champ).toHaveFocus();
  });

  it("« Effacer » vide le champ, relance la liste complète et rend le focus au champ", async () => {
    const onRecherche = vi.fn();
    const user = userEvent.setup({ delay: null });
    render(<ChampRechercheListe libelle="Rechercher un client" valeurInitiale="laurent" onRecherche={onRecherche} />);

    await user.click(screen.getByRole("button", { name: "Effacer" }));

    expect(onRecherche).toHaveBeenCalledWith("");
    const champ = screen.getByRole("searchbox", { name: "Rechercher un client" });
    expect(champ).toHaveValue("");
    expect(champ).toHaveFocus();
    expect(screen.queryByRole("button", { name: "Effacer" })).not.toBeInTheDocument();
  });

  it("annonce poliment le nombre de résultats", () => {
    const { rerender } = render(<ChampRechercheListe libelle="Rechercher un client" valeurInitiale="laurent" onRecherche={vi.fn()} total={null} />);
    const annonce = screen.getByRole("status");
    expect(annonce).toHaveAttribute("aria-live", "polite");
    expect(annonce).toHaveTextContent("");

    rerender(<ChampRechercheListe libelle="Rechercher un client" valeurInitiale="laurent" onRecherche={vi.fn()} total={3} />);
    expect(annonce).toHaveTextContent("3 résultats pour « laurent »");
    rerender(<ChampRechercheListe libelle="Rechercher un client" valeurInitiale="laurent" onRecherche={vi.fn()} total={0} />);
    expect(annonce).toHaveTextContent("Aucun résultat pour « laurent »");
  });
});

describe("liste des véhicules", () => {
  it("cherche côté serveur, garde ?q= dans l'adresse et montre le message de liste vide", async () => {
    apiFetch.mockImplementation((chemin: string) => Promise.resolve(chemin.includes("q=") ? page([]) : page([PEUGEOT])));
    const user = userEvent.setup({ delay: null });
    afficher(<VehiculesListe page={1} q="" />);
    expect(await screen.findByRole("link", { name: "Fiche du véhicule GH-482-KL" })).toHaveAttribute("href", "/vehicules/4");
    expect(apiFetch).toHaveBeenCalledWith("/vehicules?page=1&taille=20", expect.anything());

    await user.type(screen.getByRole("searchbox", { name: "Rechercher un véhicule" }), "zz-999{Enter}");

    expect(await screen.findByText("Aucun véhicule ne correspond à « zz-999 ».")).toBeInTheDocument();
    expect(apiFetch).toHaveBeenLastCalledWith("/vehicules?page=1&taille=20&q=zz-999", expect.anything());
    expect(`${window.location.pathname}${window.location.search}`).toBe("/vehicules?q=zz-999");
    expect(screen.getByText("Aucun résultat pour « zz-999 »")).toHaveAttribute("aria-live", "polite");
  });

  it("une nouvelle recherche repart de la page 1 et la pagination garde la recherche", async () => {
    apiFetch.mockResolvedValue(page([PEUGEOT], 45));
    const user = userEvent.setup({ delay: null });
    afficher(<VehiculesListe page={3} q="" />);
    await screen.findByRole("link", { name: "Fiche du véhicule GH-482-KL" });
    expect(apiFetch).toHaveBeenCalledWith("/vehicules?page=3&taille=20", expect.anything());

    await user.type(screen.getByRole("searchbox", { name: "Rechercher un véhicule" }), "peugeot{Enter}");

    await waitFor(() => expect(apiFetch).toHaveBeenLastCalledWith("/vehicules?page=1&taille=20&q=peugeot", expect.anything()));
    const pagination = await screen.findByRole("navigation", { name: /pagination/i });
    expect(within(pagination).getByRole("link", { name: "Suivant" })).toHaveAttribute("href", "/vehicules?q=peugeot&page=2");
  });

  it("montre au mécanicien le propriétaire par son nom, sans lien vers la fiche client", async () => {
    apiFetch.mockResolvedValue(page([PEUGEOT]));
    afficher(<VehiculesListe page={1} q="" />, KARIM);
    await screen.findByRole("link", { name: "Fiche du véhicule GH-482-KL" });
    expect(screen.getByText("Claire Laurent")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Claire Laurent" })).not.toBeInTheDocument();
  });
});

describe("autres listes", () => {
  it("clients : la recherche de l'adresse est relue, le message vide la reprend", async () => {
    apiFetch.mockResolvedValue(page([]));
    afficher(<ClientsListe page={1} q="dupont" />);
    expect(await screen.findByText("Aucun client ne correspond à « dupont ».")).toBeInTheDocument();
    expect(apiFetch).toHaveBeenCalledWith("/clients?page=1&taille=20&q=dupont", expect.anything());
    expect(screen.getByRole("searchbox", { name: "Rechercher un client" })).toHaveValue("dupont");
  });

  it("ordres : les filtres de statut gardent la recherche", async () => {
    apiFetch.mockResolvedValue(page([]));
    afficher(<OrdresListe page={1} statut="en_cours" q="clio" />);
    expect(await screen.findByText("Aucun ordre de travail « En cours » ne correspond à « clio ».")).toBeInTheDocument();
    expect(apiFetch).toHaveBeenCalledWith("/ordres?page=1&taille=50&statut=en_cours&q=clio", expect.anything());
    const filtres = screen.getByRole("navigation", { name: "Filtrer par statut" });
    expect(within(filtres).getByRole("link", { name: "Tous" })).toHaveAttribute("href", "/ordres?q=clio");
  });
});

describe("listes qui suivent l'adresse (revue du sprint 5)", () => {
  // Retour arrière : Next.js réaffiche la page avec les paramètres de son premier rendu
  // (sans ?q=), mais useSearchParams donne l'adresse réelle.
  it("après un retour arrière, la recherche de l'adresse revient dans le champ et la liste", async () => {
    apiFetch.mockResolvedValue(page([]));
    window.history.replaceState(null, "", "/clients?q=laurent");
    afficher(<ClientsListe page={1} q="" />);

    expect(await screen.findByText("Aucun client ne correspond à « laurent ».")).toBeInTheDocument();
    expect(screen.getByRole("searchbox", { name: "Rechercher un client" })).toHaveValue("laurent");
    expect(apiFetch).toHaveBeenCalledWith("/clients?page=1&taille=20&q=laurent", expect.anything());
    expect(apiFetch).not.toHaveBeenCalledWith("/clients?page=1&taille=20", expect.anything());
  });

  it("une navigation vers la liste sans ?q= (lien du menu) vide le champ et la recherche", async () => {
    apiFetch.mockResolvedValue(page([]));
    const user = userEvent.setup({ delay: null });
    window.history.replaceState(null, "", "/ordres");
    const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
    client.setQueryData(SESSION_KEY, { utilisateur: NADIA });
    const vue = () => (
      <QueryClientProvider client={client}>
        <OrdresListe page={1} statut={null} q="" />
      </QueryClientProvider>
    );
    const { rerender } = render(vue());
    await user.type(screen.getByRole("searchbox", { name: "Rechercher un ordre de travail" }), "clio{Enter}");
    expect(await screen.findByText("Aucun ordre de travail ne correspond à « clio ».")).toBeInTheDocument();
    expect(`${window.location.pathname}${window.location.search}`).toBe("/ordres?q=clio");

    // Lien « Ordres de travail » du menu : même page, adresse sans paramètre.
    window.history.pushState(null, "", "/ordres");
    rerender(vue());

    expect(await screen.findByText("Aucun ordre de travail pour l'instant.")).toBeInTheDocument();
    expect(screen.getByRole("searchbox", { name: "Rechercher un ordre de travail" })).toHaveValue("");
    expect(screen.queryByText(/pour « clio »/)).not.toBeInTheDocument();
  });

  it("une recherche en cours de frappe n'est pas effacée quand l'adresse rattrape la recherche transmise", async () => {
    apiFetch.mockResolvedValue(page([]));
    window.history.replaceState(null, "", "/clients");
    afficher(<ClientsListe page={1} q="" />);
    const champ = screen.getByRole("searchbox", { name: "Rechercher un client" });

    fireEvent.change(champ, { target: { value: "lau" } });
    fireEvent.submit(champ);
    expect(await screen.findByText("Aucun client ne correspond à « lau ».")).toBeInTheDocument();
    fireEvent.change(champ, { target: { value: "laur" } });

    expect(champ).toHaveValue("laur");
    expect(`${window.location.pathname}${window.location.search}`).toBe("/clients?q=lau");
  });
});

describe("recherche d'un seul caractère dans l'adresse (revue du sprint 5)", () => {
  it("/ordres?q=a affiche la liste sans filtre, sans annoncer une recherche vide", async () => {
    apiFetch.mockResolvedValue(page([]));
    window.history.replaceState(null, "", "/ordres?q=a");
    afficher(<OrdresListe page={1} statut={null} q="" />);

    expect(await screen.findByText("Aucun ordre de travail pour l'instant.")).toBeInTheDocument();
    expect(screen.queryByText(/ne correspond à « a »/)).not.toBeInTheDocument();
    expect(apiFetch).toHaveBeenCalledWith("/ordres?page=1&taille=50", expect.anything());
    expect(apiFetch).not.toHaveBeenCalledWith(expect.stringContaining("q=a"), expect.anything());
  });
});
