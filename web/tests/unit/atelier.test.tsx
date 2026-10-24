import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CarteKanban } from "@/components/atelier/Kanban";
import { ActionPrincipale } from "@/components/atelier/VueTablette";
import { rafraichirApresOrdre } from "@/components/ordres/actions";
import { cleOrdre } from "@/components/ordres/donnees";
import { FicheOrdre } from "@/components/ordres/FicheOrdre";
import { TachesCochables } from "@/components/ordres/TachesCochables";
import { ToastProvider } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api";
import { basculerTache, libellePasserA, messageTachesRestantes, peutPasserA, trierCartes, type OrdreDetail } from "@/lib/ordres";

const apiFetch = vi.fn();
vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return { ...original, apiFetch: (...args: unknown[]) => apiFetch(...args) };
});
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }) }));

const ORDRE: OrdreDetail = {
  id: 1,
  numero: "OT-2026-001",
  statut: "en_cours",
  prioritaire: false,
  vehicule: { id: 4, immatriculation: "GH-482-KL", marque: "Peugeot", modele: "308 SW", kilometrage: 84312, vin: null, date_mise_en_circulation: null },
  client: { id: 9, nom: "Laurent", prenom: "Claire", contact: null },
  mecanicien: { id: 2, nom: "Karim B." },
  restitution_prevue: null,
  ouvert_le: "2026-11-16T07:10:00Z",
  cloture_le: null,
  taches_terminees: 1,
  taches_total: 2,
  duree_prevue_minutes: 120,
  en_retard: false,
  rendez_vous: null,
  demande_client: "Bruit au freinage",
  diagnostic: null,
  kilometrage_entree: null,
  cree_par: { id: 1, nom: "Nadia Benali" },
  taches: [
    { id: 10, libelle: "Diagnostic bruit de freinage", duree_prevue_minutes: 30, position: 0, terminee: true, terminee_le: "2026-11-16T08:15:00Z", terminee_par: { id: 2, nom: "Karim B." } },
    { id: 11, libelle: "Remplacement plaquettes", duree_prevue_minutes: 90, position: 1, terminee: false, terminee_le: null, terminee_par: null },
  ],
  historique: [],
};

function avecRequetes(enfant: ReactNode, ordre: OrdreDetail = ORDRE) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity }, mutations: { retry: false } } });
  client.setQueryData(cleOrdre(ordre.id), ordre);
  client.setQueryData(["session"], { utilisateur: { id: 2, email: "karim@garage.test", nom: "Karim B.", role: "mecanicien" } });
  return { client, ...render(<QueryClientProvider client={client}><ToastProvider>{enfant}</ToastProvider></QueryClientProvider>) };
}

beforeEach(() => {
  apiFetch.mockReset();
});

describe("carte du kanban", () => {
  it("propose de passer à l'étape suivante avec un bouton nommé et accessible au clavier", async () => {
    const onAvancer = vi.fn();
    const user = userEvent.setup();
    render(<CarteKanban ordre={{ ...ORDRE, statut: "a_faire" }} enCours={false} onAvancer={onAvancer} />);

    const bouton = screen.getByRole("button", { name: /^Passer à « En cours »/ });
    expect(bouton).toHaveAccessibleName(/^Passer à « En cours »\s*: OT-2026-001$/);
    await user.tab();
    await user.tab();
    expect(bouton).toHaveFocus();
    await user.keyboard("{Enter}");

    expect(onAvancer).toHaveBeenCalledWith(expect.objectContaining({ id: 1 }), "en_cours");
  });

  it("n'affiche plus de bouton pour un véhicule livré", () => {
    render(<CarteKanban ordre={{ ...ORDRE, statut: "livre" }} enCours={false} onAvancer={vi.fn()} />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(libellePasserA("termine")).toBe("Passer à « Prêt »");
  });

  it("classe les cartes urgentes d'abord puis par heure de restitution", () => {
    const a = { ...ORDRE, id: 1, restitution_prevue: "2026-11-16T16:30:00Z" };
    const b = { ...ORDRE, id: 2, restitution_prevue: "2026-11-16T10:00:00Z" };
    const c = { ...ORDRE, id: 3, restitution_prevue: null, prioritaire: true };
    const d = { ...ORDRE, id: 4, restitution_prevue: null };
    expect(trierCartes([a, b, c, d]).map((o) => o.id)).toEqual([3, 2, 1, 4]);
  });
});

describe("tâches cochables de la vue tablette", () => {
  it("coche la tâche tout de suite puis garde la réponse de l'API", async () => {
    let repondre: (o: OrdreDetail) => void = () => {};
    apiFetch.mockImplementation(() => new Promise((resolve) => (repondre = resolve)));
    const user = userEvent.setup();
    const { client } = avecRequetes(<TachesCochables ordre={ORDRE} variante="tablette" />);

    await user.click(screen.getByLabelText(/Remplacement plaquettes/));

    expect(apiFetch).toHaveBeenCalledWith("/ordres/1/taches/11/terminer", { method: "POST" });
    expect(client.getQueryData<OrdreDetail>(cleOrdre(1))?.taches[1]?.terminee).toBe(true);
    expect(client.getQueryData<OrdreDetail>(cleOrdre(1))?.taches_terminees).toBe(2);
    repondre(basculerTache(ORDRE, 11, true, { id: 2, nom: "Karim B." }, new Date("2026-11-16T09:00:00Z")));
    await vi.waitFor(() => expect(client.getQueryData<OrdreDetail>(cleOrdre(1))?.taches[1]?.terminee_le).toBe("2026-11-16T09:00:00.000Z"));
  });

  it("annule la coche et affiche l'erreur si l'API refuse", async () => {
    apiFetch.mockRejectedValue(new ApiError(409, "ordre_livre", "Un ordre de travail livré ne peut plus être modifié."));
    const user = userEvent.setup();
    const { client } = avecRequetes(<TachesCochables ordre={ORDRE} variante="tablette" />);

    await user.click(screen.getByLabelText(/Remplacement plaquettes/));

    expect(await screen.findByText("Un ordre de travail livré ne peut plus être modifié.")).toBeInTheDocument();
    expect(client.getQueryData<OrdreDetail>(cleOrdre(1))?.taches[1]?.terminee).toBe(false);
    expect(client.getQueryData<OrdreDetail>(cleOrdre(1))?.taches_terminees).toBe(1);
  });

  it("verrouille les cases d'un ordre livré", () => {
    avecRequetes(<TachesCochables ordre={{ ...ORDRE, statut: "livre" }} />);
    for (const caseACocher of screen.getAllByRole("checkbox")) expect(caseACocher).toBeDisabled();
  });
});

describe("action principale de la vue tablette", () => {
  it("n'active « Terminer l'intervention » que lorsque toutes les tâches sont faites", () => {
    const { unmount } = avecRequetes(<ActionPrincipale ordre={ORDRE} />);
    expect(screen.getByRole("button", { name: "Terminer l'intervention" })).toBeDisabled();
    expect(screen.getByText("Encore 1 tâche à terminer.")).toBeInTheDocument();
    unmount();

    const fini = basculerTache(ORDRE, 11, true, null);
    avecRequetes(<ActionPrincipale ordre={fini} />, fini);
    expect(screen.getByRole("button", { name: "Terminer l'intervention" })).toBeEnabled();
  });

  it("propose d'abord de démarrer un ordre en attente", () => {
    avecRequetes(<ActionPrincipale ordre={{ ...ORDRE, statut: "a_faire" }} />);
    expect(screen.getByRole("button", { name: "Démarrer l'intervention" })).toBeEnabled();
  });
});

describe("données rafraîchies après une action sur un OT", () => {
  /** Requêtes en cache qui affichent le statut ou les tâches de l'OT ailleurs que sur sa fiche. */
  const CLES_DEPENDANTES = [
    ["ordres", "atelier"],
    ["ordres", "mes-travaux", 2],
    ["planning", "2026-11-16"],
    ["rendez-vous", "a-venir"],
    ["vehicules", 4, "historique"],
  ] as const;

  function remplirCache(client: QueryClient) {
    for (const cle of CLES_DEPENDANTES) client.setQueryData(cle, []);
  }

  function invalidees(client: QueryClient) {
    return CLES_DEPENDANTES.filter((cle) => client.getQueryState(cle)?.isInvalidated).map((cle) => cle[0] + (cle[1] ? `/${cle[1]}` : ""));
  }

  const TOUTES = ["ordres/atelier", "ordres/mes-travaux", "planning/2026-11-16", "rendez-vous/a-venir", "vehicules/4"];

  it("un changement de statut rafraîchit kanban, planning, rendez-vous et historique du véhicule", async () => {
    apiFetch.mockResolvedValue({ ...ORDRE, statut: "en_cours" });
    const user = userEvent.setup();
    const { client } = avecRequetes(<ActionPrincipale ordre={{ ...ORDRE, statut: "a_faire" }} />);
    remplirCache(client);

    await user.click(screen.getByRole("button", { name: "Démarrer l'intervention" }));

    await vi.waitFor(() => expect(invalidees(client)).toEqual(TOUTES));
    // La fiche reçoit directement la réponse de l'API (pas de rechargement inutile).
    expect(client.getQueryState(cleOrdre(1))?.isInvalidated).toBe(false);
    expect(client.getQueryData<OrdreDetail>(cleOrdre(1))?.statut).toBe("en_cours");
  });

  it("une tâche cochée rafraîchit aussi le planning et l'historique du véhicule", async () => {
    apiFetch.mockResolvedValue(basculerTache(ORDRE, 11, true, { id: 2, nom: "Karim B." }));
    const user = userEvent.setup();
    const { client } = avecRequetes(<TachesCochables ordre={ORDRE} />);
    remplirCache(client);

    await user.click(screen.getByLabelText(/Remplacement plaquettes/));

    await vi.waitFor(() => expect(invalidees(client)).toEqual(TOUTES));
  });

  it("rafraichirApresOrdre couvre toutes les vues qui montrent un OT", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity } } });
    remplirCache(client);
    client.setQueryData(cleOrdre(1), ORDRE);
    client.setQueryData(["clients", "liste", 1], []);

    await rafraichirApresOrdre(client);

    expect(invalidees(client)).toEqual(TOUTES);
    expect(client.getQueryState(cleOrdre(1))?.isInvalidated).toBe(false);
    expect(client.getQueryState(["clients", "liste", 1])?.isInvalidated).toBe(false);
  });
});

describe("« Passer à « Prêt » » tant que des tâches restent ouvertes", () => {
  it("la règle est la même partout : Prêt exige toutes les tâches terminées", () => {
    expect(peutPasserA(ORDRE, "termine")).toBe(false);
    expect(peutPasserA(ORDRE, "livre")).toBe(true);
    expect(peutPasserA({ ...ORDRE, taches_terminees: 0 }, "en_cours")).toBe(true);
    expect(peutPasserA(basculerTache(ORDRE, 11, true, null), "termine")).toBe(true);
    expect(messageTachesRestantes(1)).toBe("Encore 1 tâche à terminer.");
    expect(messageTachesRestantes(2)).toBe("Encore 2 tâches à terminer.");
  });

  it("la carte du kanban désactive le bouton et dit combien de tâches restent", () => {
    const onAvancer = vi.fn();
    render(<CarteKanban ordre={ORDRE} enCours={false} onAvancer={onAvancer} />);

    const bouton = screen.getByRole("button", { name: /^Passer à « Prêt »/ });
    expect(bouton).toBeDisabled();
    expect(bouton).toHaveAccessibleDescription("Encore 1 tâche à terminer.");
  });

  it("la fiche de l'OT désactive son action principale de la même façon", () => {
    avecRequetes(<FicheOrdre ordreId={1} />);

    const bouton = screen.getByRole("button", { name: "Passer à « Prêt »" });
    expect(bouton).toBeDisabled();
    expect(bouton).toHaveAccessibleDescription("Encore 1 tâche à terminer.");
  });

  it("la fiche réactive le bouton quand toutes les tâches sont faites", () => {
    const fini = basculerTache(ORDRE, 11, true, null);
    avecRequetes(<FicheOrdre ordreId={1} />, fini);

    const bouton = screen.getByRole("button", { name: "Passer à « Prêt »" });
    expect(bouton).toBeEnabled();
    expect(bouton).not.toHaveAccessibleDescription();
  });
});
