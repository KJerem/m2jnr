import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { VehiculeForm } from "@/components/vehicules/VehiculeForm";
import { ApiError } from "@/lib/api";
import { aujourdHui, normaliserImmatriculation, normaliserVin, type Vehicule, type VehiculeEntree } from "@/lib/vehicules";

const VEHICULE: Vehicule = {
  id: 4,
  client_id: 9,
  immatriculation: "GH-482-KL",
  marque: "Peugeot",
  modele: "308 SW",
  kilometrage: 84312,
  vin: "VF3LCYHZPKS123456",
  date_mise_en_circulation: "2019-03-01",
  proprietaire: { id: 9, nom: "Laurent", prenom: "Claire" },
  cree_le: "2026-11-09T09:00:00Z",
  modifie_le: "2026-11-09T09:00:00Z",
};

async function remplir(valeurs: Partial<Record<"immatriculation" | "marque" | "modele" | "kilometrage" | "vin", string>>) {
  const user = userEvent.setup();
  const champs = { immatriculation: /immatriculation/i, marque: /marque/i, modele: /modèle/i, kilometrage: /kilométrage/i, vin: /vin/i } as const;
  for (const [cle, valeur] of Object.entries(valeurs)) {
    await user.type(screen.getByLabelText(champs[cle as keyof typeof champs]), valeur);
  }
  return user;
}

describe("normalisation de la plaque", () => {
  it("ignore la casse, les espaces et les tirets et refuse le format non SIV", () => {
    expect(normaliserImmatriculation("gh 482 kl")).toBe("GH-482-KL");
    expect(normaliserImmatriculation("gh482kl")).toBe("GH-482-KL");
    expect(normaliserImmatriculation("GH-000-KL")).toBeNull();
    expect(normaliserImmatriculation("IO-123-AB")).toBeNull();
    expect(normaliserImmatriculation("GH-482")).toBeNull();
    expect(normaliserVin("vf3l cyhz pks1 23456")).toBe("VF3LCYHZPKS123456");
    expect(normaliserVin("VF3LCYHZPKS12345Q")).toBeNull();
  });

  it("calcule la date du jour à Paris", () => {
    expect(aujourdHui(new Date("2026-11-08T23:30:00Z"))).toBe("2026-11-09");
  });
});

describe("formulaire véhicule", () => {
  it("affiche la plaque normalisée en quittant le champ et envoie des valeurs typées", async () => {
    const envoyer = vi.fn<(e: VehiculeEntree) => Promise<Vehicule>>().mockResolvedValue(VEHICULE);
    const onSucces = vi.fn();
    render(<VehiculeForm mode="creation" envoyer={envoyer} onSucces={onSucces} />);

    const user = await remplir({ immatriculation: "gh 482 kl", marque: "Peugeot", modele: "308 SW", kilometrage: "84312", vin: "vf3lcyhzpks123456" });
    await user.tab();

    expect(screen.getByLabelText(/immatriculation/i)).toHaveValue("GH-482-KL");
    expect(screen.getByLabelText(/vin/i)).toHaveValue("VF3LCYHZPKS123456");
    await user.click(screen.getByRole("button", { name: "Ajouter le véhicule" }));
    await vi.waitFor(() => expect(onSucces).toHaveBeenCalledWith(VEHICULE));
    expect(envoyer).toHaveBeenCalledWith({
      immatriculation: "GH-482-KL",
      marque: "Peugeot",
      modele: "308 SW",
      kilometrage: 84312,
      vin: "VF3LCYHZPKS123456",
      date_mise_en_circulation: null,
    });
  });

  it("refuse un kilométrage négatif ou non numérique et une plaque invalide", async () => {
    const envoyer = vi.fn();
    render(<VehiculeForm mode="creation" envoyer={envoyer} onSucces={vi.fn()} />);
    const user = await remplir({ immatriculation: "AB-000-CD", marque: "Renault", modele: "Clio", kilometrage: "-5" });

    await user.click(screen.getByRole("button", { name: "Ajouter le véhicule" }));

    expect(await screen.findByText("Nombre entier positif attendu.")).toBeInTheDocument();
    expect(screen.getByText("Immatriculation invalide (format AA-123-AA).")).toBeInTheDocument();
    expect(envoyer).not.toHaveBeenCalled();
  });

  it("rattache le refus d'une plaque déjà enregistrée au champ immatriculation", async () => {
    const envoyer = vi.fn().mockRejectedValue(new ApiError(409, "immatriculation_existante", "Cette immatriculation est déjà enregistrée.", {}, { vehicule_id: 4 }));
    render(<VehiculeForm mode="creation" envoyer={envoyer} onSucces={vi.fn()} />);
    const user = await remplir({ immatriculation: "gh482kl", marque: "Peugeot", modele: "308", kilometrage: "10" });

    await user.click(screen.getByRole("button", { name: "Ajouter le véhicule" }));

    expect(await screen.findByText("Cette immatriculation est déjà enregistrée.")).toBeInTheDocument();
    expect(screen.getByLabelText(/immatriculation/i)).toHaveAttribute("aria-invalid", "true");
  });
});
