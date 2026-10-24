import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { Onglets } from "@/components/ui/Onglets";
import { ListeInterventions, MESSAGE_AUCUNE_INTERVENTION, type Intervention } from "@/components/vehicules/HistoriqueVehicule";
import { formatDateAnnee } from "@/lib/format";

const ONGLETS = [
  { id: "informations", libelle: "Informations", contenu: <p>Caractéristiques du véhicule</p> },
  { id: "historique", libelle: "Historique", contenu: <p>Interventions passées</p> },
];

describe("onglets de la fiche véhicule", () => {
  it("expose tablist, tab et tabpanel reliés entre eux", () => {
    render(<Onglets label="Fiche du véhicule" onglets={ONGLETS} />);

    expect(screen.getByRole("tablist", { name: "Fiche du véhicule" })).toBeInTheDocument();
    const informations = screen.getByRole("tab", { name: "Informations" });
    const historique = screen.getByRole("tab", { name: "Historique" });
    expect(informations).toHaveAttribute("aria-selected", "true");
    expect(historique).toHaveAttribute("aria-selected", "false");
    expect(informations).toHaveAttribute("tabindex", "0");
    expect(historique).toHaveAttribute("tabindex", "-1");
    const panneau = screen.getByRole("tabpanel", { name: "Informations" });
    expect(panneau).toHaveTextContent("Caractéristiques du véhicule");
    expect(informations).toHaveAttribute("aria-controls", panneau.id);
  });

  it("se pilote au clavier : flèches en boucle, Début et Fin", async () => {
    const user = userEvent.setup({ delay: null });
    render(<Onglets label="Fiche du véhicule" onglets={ONGLETS} />);

    await user.tab();
    expect(screen.getByRole("tab", { name: "Informations" })).toHaveFocus();
    await user.keyboard("{ArrowRight}");
    const historique = screen.getByRole("tab", { name: "Historique" });
    expect(historique).toHaveFocus();
    expect(historique).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel", { name: "Historique" })).toHaveTextContent("Interventions passées");
    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "Informations" })).toHaveFocus();
    await user.keyboard("{End}");
    expect(historique).toHaveFocus();
    await user.keyboard("{Home}");
    expect(screen.getByRole("tab", { name: "Informations" })).toHaveAttribute("aria-selected", "true");
    // Tab quitte la liste d'onglets pour le panneau (un seul onglet dans l'ordre de tabulation).
    await user.tab();
    expect(screen.getByRole("tabpanel", { name: "Informations" })).toHaveFocus();
  });
});

describe("historique des interventions", () => {
  it("affiche « Aucune intervention pour ce véhicule. » quand la liste est vide", () => {
    render(<ListeInterventions interventions={[]} />);
    expect(screen.getByText(MESSAGE_AUCUNE_INTERVENTION)).toBeInTheDocument();
    expect(MESSAGE_AUCUNE_INTERVENTION).toBe("Aucune intervention pour ce véhicule.");
  });

  it("garde l'ordre de l'API et montre date, numéro, statut, demande et kilométrage", () => {
    const interventions: Intervention[] = [
      {
        id: 7,
        numero: "OT-2026-003",
        statut: "en_cours",
        demande_client: "Bruit au freinage",
        diagnostic: null,
        kilometrage_entree: 84312,
        ouvert_le: "2026-10-14T07:10:00Z",
        cloture_le: null,
        mecanicien: { id: 2, nom: "Karim B." },
        taches: [
          { libelle: "Diagnostic", terminee: true },
          { libelle: "Plaquettes", terminee: false },
        ],
      },
      {
        id: 2,
        numero: "OT-2025-014",
        statut: "livre",
        demande_client: "Révision des 75 000 km",
        diagnostic: "Rien à signaler.",
        kilometrage_entree: 75120,
        ouvert_le: "2025-10-14T07:30:00Z",
        cloture_le: "2025-10-14T16:00:00Z",
        mecanicien: null,
        taches: [],
      },
    ];
    render(<ListeInterventions interventions={interventions} />);

    const liens = screen.getAllByRole("link");
    expect(liens.map((l) => l.textContent)).toEqual(["OT-2026-003", "OT-2025-014"]);
    expect(liens[0]).toHaveAttribute("href", "/ordres/7");
    expect(screen.getByText("mer. 14 oct. 2026")).toBeInTheDocument();
    expect(screen.getByText("En cours")).toBeInTheDocument();
    expect(screen.getByText("Livré")).toBeInTheDocument();
    expect(screen.getByText(/^84\s312\skm$/)).toBeInTheDocument();
    expect(screen.getByText(/Diagnostic : Rien à signaler/)).toBeInTheDocument();
    expect(formatDateAnnee("2025-10-14T07:30:00Z")).toBe("mar. 14 oct. 2025");
  });
});
