import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { EmployesListe, messageAucunEmploye } from "@/components/employes/EmployesListe";
import { FicheEmploye, MESSAGE_SOI_MEME_DESACTIVER } from "@/components/employes/FicheEmploye";
import { EmployeCreationForm } from "@/components/employes/NouvelEmploye";
import { SESSION_KEY } from "@/components/session/useSession";
import { ToastProvider } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api";
import { cleEmploye, lienEmployes, libelleBlocage, MESSAGE_CONFIRMATION, MESSAGE_MOT_DE_PASSE_COURT, type Employe, type FiltresEmployes } from "@/lib/employes";

const apiFetch = vi.fn();
vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return { ...original, apiFetch: (...args: unknown[]) => apiFetch(...args) };
});
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }), usePathname: () => "/employes" }));

const KARIM: Employe = {
  id: 7,
  prenom: "Karim",
  nom: "B.",
  nom_affiche: "Karim B.",
  email: "karim@garage.test",
  role: "mecanicien",
  statut: "actif",
  bloque_jusqu_a: null,
  derniere_connexion: "2026-12-22T08:05:00Z",
  cree_le: "2026-11-02T09:00:00Z",
  valide_le: "2026-11-02T09:00:00Z",
  desactive_le: null,
};
const INES: Employe = { ...KARIM, id: 9, prenom: "Inès", nom: "Morel", nom_affiche: "Inès Morel", email: "ines.morel@exemple.test", role: "gerant", statut: "en_attente", derniere_connexion: null, valide_le: null };
const NADIA = { id: 1, email: "nadia@garage.test", prenom: "Nadia", nom: "Benali", nom_affiche: "Nadia Benali", role: "gerant" as const };
const SANS_FILTRE: FiltresEmployes = { q: "", role: null, statut: null, page: 1 };

function page(elements: Employe[]) {
  return { elements, total: elements.length, page: 1, taille: 20 };
}

function afficher(enfant: ReactNode, preparer?: (client: QueryClient) => void) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity }, mutations: { retry: false } } });
  client.setQueryData(SESSION_KEY, { utilisateur: NADIA });
  preparer?.(client);
  render(
    <QueryClientProvider client={client}>
      <ToastProvider>{enfant}</ToastProvider>
    </QueryClientProvider>,
  );
  return client;
}

beforeEach(() => {
  apiFetch.mockReset();
});

afterEach(() => {
  window.history.replaceState(null, "", "/");
});

describe("règles d'affichage", () => {
  it("écrit l'adresse de la liste et les messages de liste vide", () => {
    expect(lienEmployes({ q: "karim", statut: "actif", page: 2 })).toBe("/employes?q=karim&statut=actif&page=2");
    expect(lienEmployes({ q: "", page: 1 })).toBe("/employes");
    expect(messageAucunEmploye({ ...SANS_FILTRE, q: "xyz" })).toBe("Aucun employé ne correspond à « xyz ».");
    expect(messageAucunEmploye({ ...SANS_FILTRE, role: "gerant" })).toBe("Aucun employé dans ce filtre.");
    expect(libelleBlocage({ bloque_jusqu_a: "2026-11-02T14:02:00Z" })).toBe("Bloqué jusqu'à 15 h 02");
  });
});

describe("liste des employés", () => {
  it("montre nom, e-mail, rôle, statut avec pastille et blocage, dernière connexion", async () => {
    apiFetch.mockResolvedValue(page([INES, { ...KARIM, bloque_jusqu_a: "2026-11-02T14:02:00Z" }]));
    afficher(<EmployesListe initial={SANS_FILTRE} />);

    const ligneInes = (await screen.findByRole("link", { name: "Inès Morel" })).closest("tr")!;
    expect(within(ligneInes).getByText("En attente de validation")).toBeInTheDocument();
    expect(within(ligneInes).getByText("Jamais connecté")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Inès Morel" })).toHaveAttribute("href", "/employes/9");
    const ligneKarim = screen.getByRole("link", { name: "Karim B." }).closest("tr")!;
    expect(within(ligneKarim).getByText("Actif")).toBeInTheDocument();
    expect(within(ligneKarim).getByText("Bloqué jusqu'à 15 h 02")).toBeInTheDocument();
    expect(within(ligneKarim).getByText("Mécanicien")).toBeInTheDocument();
    expect(apiFetch).toHaveBeenCalledWith("/utilisateurs?page=1&taille=20", expect.anything());
  });

  it("filtre par statut : bouton à bascule, adresse mise à jour, nouvelle requête", async () => {
    apiFetch.mockResolvedValue(page([INES]));
    const user = userEvent.setup({ delay: null });
    afficher(<EmployesListe initial={SANS_FILTRE} />);
    await screen.findByRole("link", { name: "Inès Morel" });

    const filtre = within(screen.getByRole("group", { name: "Filtrer par statut" })).getByRole("button", { name: "En attente de validation" });
    await user.click(filtre);

    expect(filtre).toHaveAttribute("aria-pressed", "true");
    expect(window.location.pathname + window.location.search).toBe("/employes?statut=en_attente");
    expect(apiFetch).toHaveBeenLastCalledWith("/utilisateurs?page=1&taille=20&statut=en_attente", expect.anything());
  });

  it("annonce une recherche sans résultat", async () => {
    apiFetch.mockResolvedValue(page([]));
    afficher(<EmployesListe initial={{ ...SANS_FILTRE, q: "xyz" }} />);

    expect(await screen.findByText("Aucun employé ne correspond à « xyz ».")).toBeInTheDocument();
    expect(screen.getByRole("searchbox", { name: "Rechercher un employé" })).toHaveValue("xyz");
    expect(screen.getByText("Aucun résultat pour « xyz »")).toHaveAttribute("aria-live", "polite");
    expect(apiFetch).toHaveBeenCalledWith("/utilisateurs?page=1&taille=20&q=xyz", expect.anything());
  });
});

describe("formulaire « Nouvel employé »", () => {
  async function remplir(motDePasse: string, confirmation: string) {
    const user = userEvent.setup({ delay: null });
    await user.type(screen.getByLabelText(/^Prénom/), "Paul");
    await user.type(screen.getByLabelText(/^Nom/), "Girard");
    await user.type(screen.getByLabelText(/^E-mail/), "paul.girard@garage.test");
    await user.type(screen.getByLabelText(/^Mot de passe/), motDePasse);
    await user.type(screen.getByLabelText(/^Confirmer le mot de passe/), confirmation);
    await user.click(screen.getByRole("button", { name: "Créer le compte" }));
  }

  it("montre la règle des 12 caractères et refuse un mot de passe court ou mal confirmé", async () => {
    afficher(<EmployeCreationForm onSucces={vi.fn()} onAnnuler={vi.fn()} />);
    expect(screen.getByLabelText(/^Mot de passe/)).toHaveAccessibleDescription(/12 caractères au moins/);

    await remplir("court", "autre");

    expect(await screen.findByText(MESSAGE_MOT_DE_PASSE_COURT)).toBeInTheDocument();
    expect(screen.getByText(MESSAGE_CONFIRMATION)).toBeInTheDocument();
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("envoie le compte et rattache un e-mail déjà pris au champ", async () => {
    const message = "Un compte existe déjà avec cet e-mail.";
    apiFetch.mockRejectedValueOnce(new ApiError(409, "email_existant", message, { email: message }));
    const onSucces = vi.fn();
    afficher(<EmployeCreationForm onSucces={onSucces} onAnnuler={vi.fn()} />);

    await remplir("phrase de passe solide", "phrase de passe solide");

    expect(apiFetch).toHaveBeenCalledWith("/utilisateurs", {
      method: "POST",
      body: { prenom: "Paul", nom: "Girard", email: "paul.girard@garage.test", role: "mecanicien", mot_de_passe: "phrase de passe solide" },
    });
    expect(await screen.findByLabelText(/^E-mail/)).toHaveAccessibleDescription(message);
    expect(screen.getByLabelText(/^E-mail/)).toHaveFocus();
    expect(onSucces).not.toHaveBeenCalled();
  });
});

describe("fiche d'un employé", () => {
  function fiche(employe: Employe) {
    return afficher(<FicheEmploye employeId={employe.id} />, (client) => client.setQueryData(cleEmploye(employe.id), employe));
  }

  it("désactive après confirmation, annonce le résultat et rend le focus à la section", async () => {
    apiFetch.mockResolvedValue({ ...KARIM, statut: "desactive", desactive_le: "2026-12-22T10:00:00Z" });
    const user = userEvent.setup({ delay: null });
    fiche(KARIM);

    await user.click(screen.getByRole("button", { name: "Désactiver le compte" }));
    const dialogue = screen.getByRole("dialog", { name: "Désactiver le compte de Karim B. ?" });
    // Revue du sprint 5 : ses OT en cours ne disparaissent pas, ils sont à réaffecter.
    expect(dialogue).toHaveTextContent("Ses ordres de travail non livrés apparaîtront dans « À traiter maintenant » pour être confiés à un autre mécanicien.");
    expect(apiFetch).not.toHaveBeenCalled();
    await user.click(within(dialogue).getByRole("button", { name: "Désactiver" }));

    expect(apiFetch).toHaveBeenCalledWith("/utilisateurs/7/desactiver", { method: "POST", body: undefined });
    expect(await screen.findByText("Compte de Karim B. désactivé.")).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Réactiver le compte" })).toBeInTheDocument();
    await vi.waitFor(() => expect(screen.getByRole("heading", { name: "Accès" })).toHaveFocus());
  });

  it("un compte repris sans nom de famille se modifie sans en inventer un", async () => {
    const admin: Employe = { ...KARIM, prenom: "Admin", nom: "", nom_affiche: "Admin" };
    apiFetch.mockResolvedValue({ ...admin, email: "admin@garage.test" });
    const user = userEvent.setup({ delay: null });
    fiche(admin);

    await user.click(screen.getByRole("button", { name: "Modifier" }));
    const nom = screen.getByRole("textbox", { name: /^Nom/ });
    expect(nom).not.toBeRequired();
    expect(nom).toHaveAccessibleDescription("Facultatif : compte repris sans nom de famille.");
    const email = screen.getByRole("textbox", { name: /^E-mail/ });
    await user.clear(email);
    await user.type(email, "admin@garage.test");
    await user.click(screen.getByRole("button", { name: "Enregistrer" }));

    await vi.waitFor(() => expect(apiFetch).toHaveBeenCalledWith("/utilisateurs/7", { method: "PUT", body: { prenom: "Admin", nom: "", email: "admin@garage.test", role: "mecanicien" } }));
    expect(screen.queryByText("Champ obligatoire.")).not.toBeInTheDocument();
  });

  it("un nom déjà renseigné reste obligatoire à la modification", async () => {
    const user = userEvent.setup({ delay: null });
    fiche(KARIM);

    await user.click(screen.getByRole("button", { name: "Modifier" }));
    await user.clear(screen.getByRole("textbox", { name: /^Nom/ }));
    await user.click(screen.getByRole("button", { name: "Enregistrer" }));

    expect(await screen.findByText("Champ obligatoire.")).toBeInTheDocument();
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("annuler la confirmation ne change rien", async () => {
    const user = userEvent.setup({ delay: null });
    fiche(KARIM);

    await user.click(screen.getByRole("button", { name: "Désactiver le compte" }));
    await user.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Annuler" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("ne propose pas au gérant de se désactiver lui-même, et dit pourquoi", () => {
    fiche({ ...KARIM, id: NADIA.id, prenom: "Nadia", nom: "Benali", nom_affiche: "Nadia Benali", role: "gerant" });

    const bouton = screen.getByRole("button", { name: "Désactiver le compte" });
    expect(bouton).toBeDisabled();
    expect(bouton).toHaveAccessibleDescription(MESSAGE_SOI_MEME_DESACTIVER);
  });

  it("réinitialise le mot de passe dans une fenêtre qui vérifie les 12 caractères", async () => {
    apiFetch.mockResolvedValue(KARIM);
    const user = userEvent.setup({ delay: null });
    fiche({ ...KARIM, bloque_jusqu_a: "2026-11-02T14:02:00Z" });
    expect(screen.getByRole("button", { name: "Débloquer" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Réinitialiser le mot de passe" }));
    const dialogue = screen.getByRole("dialog", { name: "Nouveau mot de passe pour Karim B." });
    await user.type(within(dialogue).getByLabelText(/^Nouveau mot de passe/), "court");
    await user.click(within(dialogue).getByRole("button", { name: "Enregistrer le mot de passe" }));
    expect(await within(dialogue).findByText(MESSAGE_MOT_DE_PASSE_COURT)).toBeInTheDocument();
    expect(apiFetch).not.toHaveBeenCalled();

    await user.clear(within(dialogue).getByLabelText(/^Nouveau mot de passe/));
    await user.type(within(dialogue).getByLabelText(/^Nouveau mot de passe/), "nouvelle phrase solide");
    await user.type(within(dialogue).getByLabelText(/^Confirmer le mot de passe/), "nouvelle phrase solide");
    await user.click(within(dialogue).getByRole("button", { name: "Enregistrer le mot de passe" }));

    expect(apiFetch).toHaveBeenCalledWith("/utilisateurs/7/mot-de-passe", { method: "POST", body: { mot_de_passe: "nouvelle phrase solide" } });
    expect(await screen.findByText("Mot de passe de Karim B. réinitialisé.")).toBeInTheDocument();
  });
});
