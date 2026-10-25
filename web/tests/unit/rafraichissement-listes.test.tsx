/**
 * Revue du sprint 5 (story S1.5) : après l'ajout ou la modification d'un véhicule, ou la
 * modification de son propriétaire, les listes qui montrent la plaque ou le nom (véhicules,
 * clients, ordres de travail, devis) sont rafraîchies.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SESSION_KEY } from "@/components/session/useSession";
import { FicheVehicule } from "@/components/vehicules/FicheVehicule";
import type { Vehicule } from "@/lib/vehicules";

const apiFetch = vi.fn();
vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return { ...original, apiFetch: (...args: unknown[]) => apiFetch(...args) };
});
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }), usePathname: () => "/vehicules/4" }));

const NADIA = { id: 1, email: "nadia@garage.test", prenom: "Nadia", nom: "Benali", nom_affiche: "Nadia Benali", role: "gerant" as const };

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

function page<T>(elements: T[]) {
  return { elements, total: elements.length, page: 1, taille: 20 };
}

beforeEach(() => {
  apiFetch.mockReset();
});

describe("liste des véhicules rafraîchie après une écriture (revue du sprint 5)", () => {
  it("modifier un véhicule invalide la liste des véhicules (et celles qui montrent sa plaque)", async () => {
    const modifie = { ...PEUGEOT, immatriculation: "GH-483-KL" };
    apiFetch.mockImplementation((chemin: string, options?: { method?: string }) => {
      if (options?.method === "PUT") return Promise.resolve(modifie);
      if (chemin === "/vehicules/4") return Promise.resolve(PEUGEOT);
      return Promise.resolve([]);
    });
    const user = userEvent.setup({ delay: null });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
    client.setQueryData(SESSION_KEY, { utilisateur: NADIA });
    const listes = [
      ["vehicules", "liste", "", 1],
      ["ordres", "liste", null, "", 1],
      ["devis", "liste", "", 1],
      ["clients", "liste", "", 1],
    ];
    for (const cle of listes) client.setQueryData(cle, page([]));
    render(
      <QueryClientProvider client={client}>
        <FicheVehicule vehiculeId={4} />
      </QueryClientProvider>,
    );

    await user.click(await screen.findByRole("button", { name: "Modifier" }));
    const plaque = screen.getByRole("textbox", { name: /^Immatriculation/ });
    await user.clear(plaque);
    await user.type(plaque, "GH-483-KL");
    await user.click(screen.getByRole("button", { name: "Enregistrer" }));

    expect(await screen.findByText("Véhicule enregistré.")).toBeInTheDocument();
    for (const cle of listes) expect(client.getQueryState(cle)?.isInvalidated, JSON.stringify(cle)).toBe(true);
  });
});
