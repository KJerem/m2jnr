import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { InscriptionForm } from "@/components/auth/InscriptionForm";
import { ValidationCompte } from "@/components/employes/ValidationCompte";
import { SESSION_KEY } from "@/components/session/useSession";
import { ToastProvider } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api";
import { MESSAGE_CONFIRMATION, MESSAGE_MOT_DE_PASSE_COURT, type Employe } from "@/lib/employes";
import { MESSAGE_DEMANDE_ENREGISTREE } from "@/lib/inscription";
import { PAGES_PUBLIQUES } from "@/lib/session";
import { lienATraiter } from "@/lib/tableauDeBord";

const apiFetch = vi.fn();
vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return { ...original, apiFetch: (...args: unknown[]) => apiFetch(...args) };
});
const routeur = { replace: vi.fn(), refresh: vi.fn(), push: vi.fn() };
vi.mock("next/navigation", () => ({ useRouter: () => routeur }));

const INES_SESSION = { id: 12, email: "ines.morel@exemple.test", prenom: "Inès", nom: "Morel", nom_affiche: "Inès Morel", role: "gerant" as const };
const INES: Employe = {
  ...INES_SESSION,
  statut: "en_attente",
  bloque_jusqu_a: null,
  derniere_connexion: null,
  cree_le: "2027-01-05T09:12:00Z",
  valide_le: null,
  desactive_le: null,
};

function afficher(enfant: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <ToastProvider>{enfant}</ToastProvider>
    </QueryClientProvider>,
  );
  return client;
}

/** GET /auth/inscription d'abord, puis la réponse donnée à POST /auth/register. */
function repondre(premierCompte: boolean, inscription: () => Promise<unknown>) {
  apiFetch.mockImplementation((chemin: string) => (chemin === "/auth/inscription" ? Promise.resolve({ premier_compte: premierCompte }) : inscription()));
}

async function remplir(motDePasse = "une phrase de passe solide", confirmation = motDePasse) {
  const user = userEvent.setup({ delay: null });
  await user.type(screen.getByLabelText(/^Prénom/), "Inès");
  await user.type(screen.getByLabelText(/^Nom/), "Morel");
  await user.type(screen.getByLabelText(/^E-mail/), "ines.morel@exemple.test");
  await user.type(screen.getByLabelText(/^Mot de passe/), motDePasse);
  await user.type(screen.getByLabelText(/^Confirmer le mot de passe/), confirmation);
  await user.click(screen.getByRole("button", { name: "Créer le compte" }));
}

beforeEach(() => {
  apiFetch.mockReset();
  routeur.replace.mockReset();
  routeur.push.mockReset();
});

describe("formulaire d'inscription", () => {
  it("montre la règle des 12 caractères et refuse un mot de passe court ou mal confirmé", async () => {
    repondre(false, () => Promise.reject(new Error("inattendu")));
    afficher(<InscriptionForm />);
    expect(screen.getByLabelText(/^Mot de passe/)).toHaveAccessibleDescription(/12 caractères au moins/);

    await remplir("court", "autre");

    expect(await screen.findByText(MESSAGE_MOT_DE_PASSE_COURT)).toBeInTheDocument();
    expect(screen.getByText(MESSAGE_CONFIRMATION)).toBeInTheDocument();
    expect(apiFetch).not.toHaveBeenCalledWith("/auth/register", expect.anything());
  });

  it("affiche le panneau de confirmation neutre d'une demande en attente", async () => {
    repondre(false, () => Promise.resolve({ compte_actif: false, message: MESSAGE_DEMANDE_ENREGISTREE, utilisateur: null }));
    afficher(<InscriptionForm />);
    expect(await screen.findByText(/utilisable après sa validation par un gérant/)).toBeInTheDocument();

    await remplir();

    expect(apiFetch).toHaveBeenCalledWith("/auth/register", {
      method: "POST",
      body: { prenom: "Inès", nom: "Morel", email: "ines.morel@exemple.test", mot_de_passe: "une phrase de passe solide" },
      redirigerSi401: false,
    });
    const titre = await screen.findByRole("heading", { name: "Demande envoyée" });
    await vi.waitFor(() => expect(titre).toHaveFocus());
    expect(screen.getByText(MESSAGE_DEMANDE_ENREGISTREE)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Retour à la connexion" })).toHaveAttribute("href", "/connexion");
    expect(screen.queryByRole("button", { name: "Créer le compte" })).not.toBeInTheDocument();
    expect(routeur.replace).not.toHaveBeenCalled();
  });

  it("connecte le premier compte du garage et ouvre l'accueil", async () => {
    repondre(true, () => Promise.resolve({ compte_actif: true, message: "Compte créé. Vous êtes le gérant du garage.", utilisateur: INES_SESSION }));
    const client = afficher(<InscriptionForm />);
    expect(await screen.findByText(/Premier compte du garage/)).toBeInTheDocument();

    await remplir();

    await vi.waitFor(() => expect(routeur.replace).toHaveBeenCalledWith("/"));
    expect(client.getQueryData(SESSION_KEY)).toEqual({ utilisateur: INES_SESSION });
  });

  it("rattache une erreur de l'API au champ et propose le lien « J'ai déjà un compte »", async () => {
    repondre(false, () => Promise.reject(new ApiError(422, "validation", "Certains champs sont invalides.", { email: "Adresse e-mail invalide." })));
    afficher(<InscriptionForm />);
    expect(screen.getByRole("link", { name: "J'ai déjà un compte" })).toHaveAttribute("href", "/connexion");

    await remplir();

    expect(await screen.findByLabelText(/^E-mail/)).toHaveAccessibleDescription("Adresse e-mail invalide.");
  });

  it("est une page publique, comme la connexion", () => {
    expect(PAGES_PUBLIQUES).toEqual(["/connexion", "/inscription"]);
  });
});

describe("validation d'une inscription par le gérant", () => {
  it("valide le compte avec le rôle choisi, mécanicien par défaut", async () => {
    apiFetch.mockResolvedValue({ ...INES, statut: "actif", role: "mecanicien" });
    const onValide = vi.fn();
    const user = userEvent.setup({ delay: null });
    afficher(<ValidationCompte employe={INES} onValide={onValide} />);
    expect(screen.getByLabelText("Rôle du compte")).toHaveValue("mecanicien");

    await user.click(screen.getByRole("button", { name: "Valider le compte" }));

    expect(apiFetch).toHaveBeenCalledWith("/utilisateurs/12/valider", { method: "POST", body: { role: "mecanicien" } });
    expect(await screen.findByText("Compte d'Inès Morel validé : mécanicien.")).toBeInTheDocument();
    expect(onValide).toHaveBeenCalled();
  });

  it("refuse la demande après confirmation et revient à la liste", async () => {
    apiFetch.mockResolvedValue(undefined);
    const user = userEvent.setup({ delay: null });
    afficher(<ValidationCompte employe={INES} onValide={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Refuser" }));
    const dialogue = screen.getByRole("dialog", { name: "Refuser la demande d'Inès Morel ?" });
    expect(apiFetch).not.toHaveBeenCalled();
    await user.click(within(dialogue).getByRole("button", { name: "Refuser la demande" }));

    expect(apiFetch).toHaveBeenCalledWith("/utilisateurs/12/refuser", { method: "POST" });
    await vi.waitFor(() => expect(routeur.push).toHaveBeenCalledWith("/employes"));
  });

  it("« Compte à valider » du tableau de bord mène à la fiche de l'employé", () => {
    expect(lienATraiter({ type: "compte_a_valider", titre: "Compte à valider", detail: "Inès Morel · ines.morel@exemple.test", ordre_id: null, numero: null, utilisateur_id: 12 })).toBe("/employes/12");
    expect(lienATraiter({ type: "retard", titre: "…", detail: "…", ordre_id: 4, numero: "OT-2026-004", utilisateur_id: null })).toBe("/ordres/4");
  });
});
