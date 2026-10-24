import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Interventions, TableauDeBord } from "@/components/tableau-de-bord/TableauDeBord";
import { NBSP } from "@/lib/format";
import type { OrdreResume } from "@/lib/ordres";
import { filtrerInterventions, libelleVariation, montantSansSymbole, restitution, sousTitre, titreJour, type TableauDeBord as Donnees } from "@/lib/tableauDeBord";

const apiFetch = vi.fn();
vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return { ...original, apiFetch: (...args: unknown[]) => apiFetch(...args) };
});
// Le champ « Rechercher » de l'en-tête (S1.3) navigue avec le routeur de Next.js.
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }) }));

// Samedi 24 octobre 2026, 14 h 40 à Paris.
const MAINTENANT = new Date("2026-10-24T12:40:00Z");

function ordre(surcharges: Partial<OrdreResume>): OrdreResume {
  return {
    id: 1,
    numero: "OT-2026-001",
    statut: "en_cours",
    prioritaire: false,
    vehicule: { id: 1, immatriculation: "GA-664-SN", marque: "Dacia", modele: "Sandero", kilometrage: 45210 },
    client: { id: 1, nom: "Kone", prenom: "Aminata", contact: null },
    mecanicien: { id: 3, nom: "Sophie M." },
    restitution_prevue: null,
    ouvert_le: "2026-10-24T06:25:00Z",
    cloture_le: null,
    taches_terminees: 0,
    taches_total: 0,
    duree_prevue_minutes: 0,
    en_retard: false,
    rendez_vous: null,
    ...surcharges,
  };
}

const EN_RETARD = ordre({ id: 1, numero: "OT-2026-004", prioritaire: true, restitution_prevue: "2026-10-24T10:00:00Z", en_retard: true });
const PRET = ordre({ id: 2, numero: "OT-2026-006", statut: "termine", restitution_prevue: "2026-10-24T14:00:00Z", vehicule: { id: 2, immatriculation: "HB-205-MZ", marque: "Toyota", modele: "Yaris", kilometrage: 15800 } });
const DEMAIN = ordre({ id: 3, numero: "OT-2026-007", restitution_prevue: "2026-10-25T10:00:00Z", mecanicien: null });
const LIVRE = ordre({ id: 4, numero: "OT-2026-002", statut: "livre", restitution_prevue: "2026-10-24T09:00:00Z", cloture_le: "2026-10-24T08:15:00Z" });
const ORDRES = [EN_RETARD, PRET, DEMAIN, LIVRE];

beforeEach(() => {
  apiFetch.mockReset();
});

describe("interventions du jour", () => {
  it("filtre avec des boutons à bascule qui annoncent leur état et leur nombre", async () => {
    const user = userEvent.setup({ delay: null });
    render(<Interventions ordres={ORDRES} maintenant={MAINTENANT} />);

    const groupe = screen.getByRole("group", { name: "Filtrer les interventions" });
    const toutes = within(groupe).getByRole("button", { name: "Toutes · 4" });
    const aRestituer = within(groupe).getByRole("button", { name: "À restituer · 1" });
    const enRetard = within(groupe).getByRole("button", { name: "En retard · 1" });
    expect(toutes).toHaveAttribute("aria-pressed", "true");
    expect(enRetard).toHaveAttribute("aria-pressed", "false");
    expect(screen.getAllByRole("row")).toHaveLength(5);

    await user.click(enRetard);
    expect(enRetard).toHaveAttribute("aria-pressed", "true");
    expect(toutes).toHaveAttribute("aria-pressed", "false");
    const lignes = screen.getAllByRole("row").slice(1);
    expect(lignes).toHaveLength(1);
    expect(within(lignes[0]!).getByRole("link", { name: "OT-2026-004" })).toHaveAttribute("href", "/ordres/1");

    await user.click(aRestituer);
    expect(within(screen.getAllByRole("row")[1]!).getByRole("link")).toHaveTextContent("OT-2026-006");
    await user.keyboard("{Tab}{Enter}");
    expect(enRetard).toHaveAttribute("aria-pressed", "true");
  });

  it("écrit le retard en toutes lettres, en couleur de danger, et les autres restitutions", () => {
    render(<Interventions ordres={ORDRES} maintenant={MAINTENANT} />);
    const [, retard, pret, demain, livre] = screen.getAllByRole("row");

    const cellule = within(retard!).getByText(/en retard/);
    expect(cellule).toHaveTextContent(/^12\sh\s00 · en retard$/);
    expect(cellule).toHaveClass("danger-text");
    expect(within(retard!).getByText("Urgent")).toBeInTheDocument();
    expect(within(pret!).getByText(/^16\sh\s00$/)).not.toHaveClass("danger-text");
    expect(within(demain!).getByText("dim. 25 oct.")).toBeInTheDocument();
    expect(within(demain!).getByText("Non affecté")).toBeInTheDocument();
    expect(within(livre!).getByText(/^Rendu 10\sh\s15$/)).toBeInTheDocument();
    expect(within(retard!).getByRole("img", { name: "Immatriculation GA-664-SN" })).toHaveClass("et-plate-sm");
  });

  it("calcule les cellules et les filtres comme l'écran", () => {
    expect(restitution(EN_RETARD, MAINTENANT)).toEqual({ texte: `12${NBSP}h${NBSP}00 · en retard`, retard: true });
    expect(restitution(LIVRE, MAINTENANT)).toEqual({ texte: `Rendu 10${NBSP}h${NBSP}15`, retard: false });
    expect(restitution(ordre({ restitution_prevue: "2026-10-23T10:00:00Z", en_retard: true }), MAINTENANT)).toEqual({ texte: "ven. 23 oct. · en retard", retard: true });
    expect(restitution(ordre({}), MAINTENANT)).toEqual({ texte: "—", retard: false });
    expect(filtrerInterventions(ORDRES, "a_restituer")).toEqual([PRET]);
    expect(filtrerInterventions(ORDRES, "en_retard")).toEqual([EN_RETARD]);
  });

  it("dit quand un filtre ne trouve rien", async () => {
    const user = userEvent.setup({ delay: null });
    render(<Interventions ordres={[PRET]} maintenant={MAINTENANT} />);

    await user.click(screen.getByRole("button", { name: "En retard · 0" }));

    expect(screen.getByRole("status")).toHaveTextContent("Aucune intervention « En retard ».");
  });
});

describe("en-tête et tuiles", () => {
  it("formate le titre, le sous-titre, le montant et la variation", () => {
    expect(titreJour("2026-10-24")).toBe("Atelier — samedi 24 oct.");
    expect(sousTitre(3, 3)).toBe("3 ponts ouverts · 3 mécaniciens actifs");
    expect(sousTitre(1, 1)).toBe("1 pont ouvert · 1 mécanicien actif");
    expect(montantSansSymbole(284650)).toBe("2 846,50");
    expect(libelleVariation(12, "2026-10-17")).toBe(`+12${NBSP}% vs sam. dernier`);
    expect(libelleVariation(-5, "2026-10-17")).toBe(`−5${NBSP}% vs sam. dernier`);
    expect(libelleVariation(null, "2026-10-17")).toBeNull();
  });

  it("affiche le tableau de bord avec la bande signal sur les retards", async () => {
    const donnees: Donnees = {
      jour: "2026-10-24",
      ponts_actifs: 3,
      mecaniciens_actifs: 3,
      kpis: {
        vehicules_atelier: 7,
        entres_aujourdhui: 2,
        prets_a_restituer: 1,
        a_restituer_aujourdhui: 1,
        en_retard: 1,
        rendez_vous_aujourdhui: 6,
        prochain_rendez_vous: "2026-10-24T13:00:00Z",
        facture_aujourdhui_ttc_centimes: 284650,
        facture_semaine_derniere_ttc_centimes: 254152,
        jour_comparaison: "2026-10-17",
        variation_pct: 12,
      },
      interventions: ORDRES,
      arrivees: [
        {
          rendez_vous_id: 9,
          heure: "2026-10-24T13:00:00Z",
          fin: "2026-10-24T14:00:00Z",
          motif: "Révision 60 000 km",
          pont: { id: 1, nom: "Pont 1" },
          vehicule: { id: 5, immatriculation: "DL-552-VK", marque: "Renault", modele: "Captur", kilometrage: 60000 },
          client: { id: 6, nom: "Roux", prenom: "Isabelle" },
          ordre_id: null,
        },
      ],
      a_traiter: [{ type: "retard", titre: "Aminata Kone attend", detail: "Dacia Sandero · OT-2026-004 · promis à 12 h 00, retard de 2 h 40", ordre_id: 1, numero: "OT-2026-004" }],
    };
    apiFetch.mockResolvedValue(donnees);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <TableauDeBord />
      </QueryClientProvider>,
    );

    expect(await screen.findByRole("heading", { level: 1, name: "Atelier — samedi 24 oct." })).toBeInTheDocument();
    expect(screen.getByText("3 ponts ouverts · 3 mécaniciens actifs")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Nouvelle intervention" })).toHaveAttribute("href", "/ordres/nouveau");
    const tuileRetard = screen.getByText("En retard", { selector: ".et-kpi-label" }).closest(".et-kpi");
    expect(tuileRetard).toHaveClass("et-kpi-signal");
    expect(screen.getByText(/prochain à 15\sh\s00/)).toBeInTheDocument();
    expect(screen.getByText(/\+12\s% vs sam\. dernier/)).toBeInTheDocument();
    expect(screen.getByText("Isabelle Roux · Renault Captur")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Aminata Kone attend/ })).toHaveAttribute("href", "/ordres/1");
    expect(apiFetch).toHaveBeenCalledWith("/tableau-de-bord", expect.anything());
  });
});
