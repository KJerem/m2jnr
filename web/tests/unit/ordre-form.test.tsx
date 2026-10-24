import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { OrdreForm } from "@/components/ordres/OrdreForm";
import { ApiError } from "@/lib/api";
import { formatDureeHM, formatRestitution, ordreVide, versSaisieDateHeure, type OrdreDetail, type OrdreEntree } from "@/lib/ordres";
import type { Vehicule } from "@/lib/vehicules";

const VEHICULES: Vehicule[] = [
  {
    id: 4,
    client_id: 9,
    immatriculation: "GH-482-KL",
    marque: "Peugeot",
    modele: "308 SW",
    kilometrage: 84312,
    vin: null,
    date_mise_en_circulation: null,
    proprietaire: { id: 9, nom: "Laurent", prenom: "Claire" },
    cree_le: "2026-11-09T09:00:00Z",
    modifie_le: "2026-11-09T09:00:00Z",
  },
  {
    id: 5,
    client_id: 10,
    immatriculation: "EK-730-PA",
    marque: "Volkswagen",
    modele: "Golf 7",
    kilometrage: 112450,
    vin: null,
    date_mise_en_circulation: null,
    proprietaire: { id: 10, nom: "Petit", prenom: "Thomas" },
    cree_le: "2026-11-09T09:00:00Z",
    modifie_le: "2026-11-09T09:00:00Z",
  },
];
const MECANICIENS = [
  { id: 2, nom: "Karim B." },
  { id: 3, nom: "Sophie M." },
];
const ORDRE = { id: 1, numero: "OT-2026-001" } as OrdreDetail;

function rendre(envoyer = vi.fn<(e: OrdreEntree) => Promise<OrdreDetail>>().mockResolvedValue(ORDRE), vehiculeId: number | null = 4) {
  const onSucces = vi.fn();
  render(<OrdreForm mode="creation" valeursInitiales={ordreVide(vehiculeId)} vehicules={VEHICULES} mecaniciens={MECANICIENS} envoyer={envoyer} onSucces={onSucces} />);
  return { envoyer, onSucces, user: userEvent.setup({ delay: null }) };
}

// Beaucoup de saisie au clavier simulée : délai élargi quand toute la suite tourne en parallèle.
describe("lignes de tâches du formulaire d'ordre de travail", () => {
  it("ajoute des lignes, totalise les durées et envoie les tâches dans l'ordre", async () => {
    const { envoyer, onSucces, user } = rendre();
    await user.type(screen.getByLabelText(/demande du client/i), "Bruit au freinage");

    await user.click(screen.getByRole("button", { name: "Ajouter une tâche" }));
    expect(screen.getByLabelText(/^tâche 1/i)).toHaveFocus();
    await user.type(screen.getByLabelText(/^tâche 1/i), "Diagnostic bruit de freinage");
    await user.selectOptions(screen.getByLabelText(/durée de la tâche 1/i), "30");
    await user.click(screen.getByRole("button", { name: "Ajouter une tâche" }));
    await user.type(screen.getByLabelText(/^tâche 2/i), "Remplacement plaquettes et disques avant");
    await user.selectOptions(screen.getByLabelText(/durée de la tâche 2/i), "120");

    expect(screen.getByText(/2 tâches · 2\sh\s30 prévues/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Ouvrir l'ordre de travail" }));

    await vi.waitFor(() => expect(onSucces).toHaveBeenCalledWith(ORDRE));
    expect(envoyer).toHaveBeenCalledWith({
      vehicule_id: 4,
      demande_client: "Bruit au freinage",
      diagnostic: null,
      prioritaire: false,
      kilometrage_entree: null,
      restitution_prevue: null,
      mecanicien_id: null,
      taches: [
        { libelle: "Diagnostic bruit de freinage", duree_prevue_minutes: 30 },
        { libelle: "Remplacement plaquettes et disques avant", duree_prevue_minutes: 120 },
      ],
    });
  });

  it("retire une ligne au clavier et rend le focus au bouton d'ajout", async () => {
    const { envoyer, user } = rendre();
    await user.type(screen.getByLabelText(/demande du client/i), "Vidange");
    await user.click(screen.getByRole("button", { name: "Ajouter une tâche" }));
    await user.type(screen.getByLabelText(/^tâche 1/i), "Vidange");
    await user.click(screen.getByRole("button", { name: "Ajouter une tâche" }));
    await user.type(screen.getByLabelText(/^tâche 2/i), "Filtre à air");

    screen.getByRole("button", { name: "Retirer la tâche 1" }).focus();
    await user.keyboard("{Enter}");

    expect(screen.queryByLabelText(/^tâche 2/i)).not.toBeInTheDocument();
    expect(screen.getByLabelText(/^tâche 1/i)).toHaveValue("Filtre à air");
    expect(screen.getByRole("button", { name: "Ajouter une tâche" })).toHaveFocus();
    await user.click(screen.getByRole("button", { name: "Ouvrir l'ordre de travail" }));
    await vi.waitFor(() => expect(envoyer).toHaveBeenCalled());
    expect(envoyer.mock.calls[0]?.[0].taches).toEqual([{ libelle: "Filtre à air", duree_prevue_minutes: 60 }]);
  });

  it("refuse une ligne sans libellé et rattache l'erreur à la ligne", async () => {
    const { envoyer, user } = rendre();
    await user.type(screen.getByLabelText(/demande du client/i), "Vidange");
    await user.click(screen.getByRole("button", { name: "Ajouter une tâche" }));

    await user.click(screen.getByRole("button", { name: "Ouvrir l'ordre de travail" }));

    const ligne = screen.getByLabelText(/^tâche 1/i);
    expect(await screen.findByText("Champ obligatoire.")).toBeInTheDocument();
    expect(ligne).toHaveAttribute("aria-invalid", "true");
    expect(envoyer).not.toHaveBeenCalled();
  });

  it("exige un véhicule et refuse un kilométrage inférieur au dernier relevé", async () => {
    const { envoyer, user } = rendre(undefined, null);
    await user.type(screen.getByLabelText(/demande du client/i), "Vidange");
    await user.click(screen.getByRole("button", { name: "Ouvrir l'ordre de travail" }));
    expect(await screen.findByText("Un ordre de travail doit être rattaché à un véhicule.")).toBeInTheDocument();

    const select = screen.getByLabelText(/^véhicule/i);
    expect(within(select).getByRole("group", { name: "Claire Laurent" })).toBeInTheDocument();
    await user.selectOptions(select, "4");
    expect(screen.getByText(/Dernier relevé : 84\s312\skm/)).toBeInTheDocument();
    await user.type(screen.getByLabelText(/kilométrage d'entrée/i), "80000");
    await user.click(screen.getByRole("button", { name: "Ouvrir l'ordre de travail" }));

    expect(await screen.findByText(/ne peut pas être inférieur à celui du véhicule/)).toBeInTheDocument();
    expect(envoyer).not.toHaveBeenCalled();
  });

  it("rattache une erreur de l'API à la ligne de tâche concernée", async () => {
    const envoyer = vi.fn().mockRejectedValue(new ApiError(422, "validation", "Certains champs sont invalides.", { "taches.0.libelle": "200 caractères maximum." }));
    const { user } = rendre(envoyer);
    await user.type(screen.getByLabelText(/demande du client/i), "Vidange");
    await user.click(screen.getByRole("button", { name: "Ajouter une tâche" }));
    await user.type(screen.getByLabelText(/^tâche 1/i), "Vidange");

    await user.click(screen.getByRole("button", { name: "Ouvrir l'ordre de travail" }));

    expect(await screen.findByText("200 caractères maximum.")).toBeInTheDocument();
    expect(screen.getByLabelText(/^tâche 1/i)).toHaveAttribute("aria-invalid", "true");
  });
});

describe("formats des ordres de travail", () => {
  it("affiche les durées et la restitution à l'heure de Paris", () => {
    expect(formatDureeHM(150)).toBe("2 h 30");
    expect(formatDureeHM(45)).toBe("45 min");
    expect(formatDureeHM(120)).toBe("2 h");
    const maintenant = new Date("2026-11-16T10:00:00Z");
    expect(formatRestitution("2026-11-16T16:30:00Z", maintenant)).toBe("17 h 30");
    expect(formatRestitution("2026-11-17T16:30:00Z", maintenant)).toBe("mar. 17 nov. à 17 h 30");
    expect(versSaisieDateHeure("2026-11-16T16:30:00Z")).toBe("2026-11-16T17:30");
  });
});
