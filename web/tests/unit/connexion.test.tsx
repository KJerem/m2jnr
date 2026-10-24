import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LoginForm } from "@/components/auth/LoginForm";
import { SESSION_KEY, useDeconnexion, useSession } from "@/components/session/useSession";
import { ApiError, apiFetch } from "@/lib/api";
import { cheminDeRetour } from "@/lib/session";

const routeur = { replace: vi.fn(), refresh: vi.fn(), push: vi.fn() };
vi.mock("next/navigation", () => ({ useRouter: () => routeur }));

function json(status: number, corps: unknown) {
  return new Response(JSON.stringify(corps), { status, headers: { "Content-Type": "application/json" } });
}

function avecQuery(children: ReactNode, client = new QueryClient({ defaultOptions: { queries: { retry: false } } })) {
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  document.cookie = "csrf_token=jeton-test; path=/";
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  fetchMock.mockReset();
  routeur.replace.mockReset();
  document.cookie = "csrf_token=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/";
  vi.unstubAllGlobals();
});

async function saisirEtEnvoyer(email: string, motDePasse: string) {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText(/e-mail/i), email);
  await user.type(screen.getByLabelText(/mot de passe/i), motDePasse);
  await user.click(screen.getByRole("button", { name: "Se connecter" }));
}

describe("formulaire de connexion", () => {
  it("affiche le message de l'API quand les identifiants sont refusés", async () => {
    fetchMock.mockResolvedValueOnce(json(401, { code: "identifiants_invalides", message: "Identifiants invalides.", champs: {} }));
    render(avecQuery(<LoginForm suivant="/" />));

    await saisirEtEnvoyer("nadia@garage.test", "mauvais");

    expect(await screen.findByRole("alert")).toHaveTextContent("Identifiants invalides.");
    expect(screen.getByLabelText(/mot de passe/i)).toHaveValue("");
    expect(routeur.replace).not.toHaveBeenCalled();
  });

  it("affiche l'heure de déblocage quand le compte est bloqué", async () => {
    const message = "Compte bloqué jusqu'à 15 h 02 après 5 essais erronés.";
    fetchMock.mockResolvedValueOnce(json(423, { code: "compte_bloque", message, champs: {} }));
    render(avecQuery(<LoginForm suivant="/" />));

    await saisirEtEnvoyer("nadia@garage.test", "mauvais");

    expect(await screen.findByRole("alert")).toHaveTextContent(message);
  });

  it("envoie le jeton CSRF puis redirige vers la page demandée", async () => {
    fetchMock.mockResolvedValueOnce(json(200, { utilisateur: { id: 1, email: "nadia@garage.test", nom: "Nadia Benali", role: "gerant" } }));
    render(avecQuery(<LoginForm suivant="/clients" />));

    await saisirEtEnvoyer("nadia@garage.test", "bon-mot-de-passe");

    await vi.waitFor(() => expect(routeur.replace).toHaveBeenCalledWith("/clients"));
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("/api/auth/login");
    expect((init?.headers as Record<string, string>)["X-CSRF-Token"]).toBe("jeton-test");
    expect(JSON.parse(String(init?.body))).toEqual({ email: "nadia@garage.test", mot_de_passe: "bon-mot-de-passe" });
  });

  it("demande les deux champs avant d'appeler l'API", async () => {
    render(avecQuery(<LoginForm suivant="/" />));
    await userEvent.setup().click(screen.getByRole("button", { name: "Se connecter" }));

    expect(screen.getByRole("alert")).toHaveTextContent("Saisissez votre e-mail et votre mot de passe.");
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("déconnexion", () => {
  const SESSION = { utilisateur: { id: 1, email: "nadia@garage.test", nom: "Nadia Benali", role: "gerant" } };

  function PiedDeMenu() {
    const { utilisateur } = useSession();
    const deconnexion = useDeconnexion();
    return (
      <button type="button" onClick={() => deconnexion.mutate()}>
        Se déconnecter ({utilisateur?.nom})
      </button>
    );
  }

  it("va exactement sur /connexion sans relancer /auth/me", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    client.setQueryData(SESSION_KEY, SESSION);
    client.setQueryData(["clients", 1], { elements: [], total: 0, page: 1, taille: 20 });
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }));
    render(avecQuery(<PiedDeMenu />, client));

    await userEvent.setup().click(screen.getByRole("button", { name: /Se déconnecter/ }));

    await vi.waitFor(() => expect(routeur.replace).toHaveBeenCalledWith("/connexion"));
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0]![0]).toBe("/api/auth/logout");
    expect(routeur.replace).toHaveBeenCalledTimes(1);
  });

  it("vide le cache à l'arrivée sur la page de connexion", () => {
    const client = new QueryClient();
    client.setQueryData(SESSION_KEY, SESSION);
    client.setQueryData(["clients", 1], { elements: [], total: 0, page: 1, taille: 20 });

    render(avecQuery(<LoginForm suivant="/" />, client));

    expect(client.getQueryCache().getAll()).toHaveLength(0);
  });
});

describe("apiFetch", () => {
  it("demande un jeton CSRF quand le cookie manque", async () => {
    document.cookie = "csrf_token=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/";
    fetchMock.mockResolvedValueOnce(json(200, { jeton: "jeton-neuf" })).mockResolvedValueOnce(new Response(null, { status: 204 }));

    await apiFetch<void>("/auth/logout", { method: "POST" });

    expect(fetchMock.mock.calls[0]![0]).toBe("/api/auth/csrf");
    expect((fetchMock.mock.calls[1]![1]?.headers as Record<string, string>)["X-CSRF-Token"]).toBe("jeton-neuf");
  });

  it("lève une ApiError typée avec les champs et les détails", async () => {
    fetchMock.mockResolvedValueOnce(json(409, { code: "doublon_telephone", message: "Un client avec ce téléphone existe déjà.", champs: {}, clients: [{ id: 3 }] }));

    const erreur = await apiFetch("/clients", { method: "POST", body: {} }).catch((e: unknown) => e);

    expect(erreur).toBeInstanceOf(ApiError);
    expect(erreur).toMatchObject({ status: 409, code: "doublon_telephone", details: { clients: [{ id: 3 }] } });
  });

  it("n'envoie pas de jeton CSRF sur un GET", async () => {
    fetchMock.mockResolvedValueOnce(json(200, []));

    await apiFetch("/devis");

    expect((fetchMock.mock.calls[0]![1]?.headers as Record<string, string>)["X-CSRF-Token"]).toBeUndefined();
  });
});

describe("chemin de retour après connexion", () => {
  it("n'accepte que des chemins internes", () => {
    expect(cheminDeRetour("/clients?page=2")).toBe("/clients?page=2");
    expect(cheminDeRetour("https://exemple.test")).toBe("/");
    expect(cheminDeRetour("//exemple.test")).toBe("/");
    expect(cheminDeRetour("/connexion")).toBe("/");
    expect(cheminDeRetour(null)).toBe("/");
  });
});
