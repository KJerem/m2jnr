import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { estVueTablette } from "@/components/layout/AppShell";
import { RendezVousForm } from "@/components/rendez-vous/RendezVousForm";
import { ApiError } from "@/lib/api";
import { ElementDuPlanning } from "@/components/planning/Planning";
import type { OrdreResume } from "@/lib/ordres";
import { decalerJour, elementSuivant, estDansLePasse, formatCreneau, formatJour, grouperParJour, jourDuPont, libelleReport, MESSAGE_PASSE, type Planning, type RendezVous, type RendezVousEntree } from "@/lib/rendezvous";
import type { Vehicule } from "@/lib/vehicules";

vi.mock("next/navigation", () => ({ usePathname: () => "/", useRouter: () => ({ push: vi.fn(), replace: vi.fn() }) }));

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
];
const PONTS = [
  { id: 1, nom: "Pont 1" },
  { id: 2, nom: "Pont 2" },
];
// Lundi 16 novembre 2026, 10 h 00 à Paris.
const MAINTENANT = () => new Date("2026-11-16T09:00:00Z");

function rdv(id: number, debut: string, fin: string, pont = PONTS[0]!): RendezVous {
  return {
    id,
    debut,
    fin,
    duree_minutes: 60,
    motif: "Vidange",
    pont,
    vehicule: { id: 4, immatriculation: "GH-482-KL", marque: "Peugeot", modele: "308 SW", kilometrage: 84312 },
    client: { id: 9, nom: "Laurent", prenom: "Claire", contact: null },
    ordre: null,
  };
}

function rendre(envoyer = vi.fn<(e: RendezVousEntree) => Promise<RendezVous>>().mockResolvedValue(rdv(1, "2026-11-16T09:30:00Z", "2026-11-16T10:30:00Z"))) {
  const onSucces = vi.fn();
  render(<RendezVousForm vehicules={VEHICULES} ponts={PONTS} envoyer={envoyer} onSucces={onSucces} maintenant={MAINTENANT} />);
  return { envoyer, onSucces, user: userEvent.setup({ delay: null }) };
}

async function remplir(user: ReturnType<typeof userEvent.setup>, jour: string, heure: string) {
  await user.selectOptions(screen.getByLabelText(/^véhicule/i), "4");
  await user.selectOptions(screen.getByLabelText(/^pont/i), "2");
  fireEvent.change(screen.getByLabelText(/^jour/i), { target: { value: jour } });
  fireEvent.change(screen.getByLabelText(/^heure/i), { target: { value: heure } });
  await user.selectOptions(screen.getByLabelText(/^durée/i), "90");
  await user.type(screen.getByLabelText(/^motif/i), "Remplacement des plaquettes avant");
}

describe("formulaire de rendez-vous", () => {
  it("exige véhicule, pont, jour, heure et motif", async () => {
    const { envoyer, user } = rendre();

    await user.click(screen.getByRole("button", { name: "Enregistrer le rendez-vous" }));

    expect(await screen.findAllByText("Champ obligatoire.")).toHaveLength(5);
    for (const champ of [/^véhicule/i, /^pont/i, /^jour/i, /^heure/i, /^motif/i]) {
      expect(screen.getByLabelText(champ)).toHaveAttribute("aria-invalid", "true");
    }
    expect(envoyer).not.toHaveBeenCalled();
  });

  it("refuse un créneau déjà passé à l'heure de Paris", async () => {
    const { envoyer, user } = rendre();
    await remplir(user, "2026-11-16", "09:45");

    await user.click(screen.getByRole("button", { name: "Enregistrer le rendez-vous" }));

    expect(await screen.findByText(MESSAGE_PASSE)).toBeInTheDocument();
    expect(screen.getByLabelText(/^jour/i)).toHaveAttribute("aria-invalid", "true");
    expect(envoyer).not.toHaveBeenCalled();
  });

  it("envoie le début à l'heure de Paris et garde le pont et le jour pour le suivant", async () => {
    const { envoyer, onSucces, user } = rendre();
    await remplir(user, "2026-11-16", "10:30");

    await user.click(screen.getByRole("button", { name: "Enregistrer le rendez-vous" }));

    await vi.waitFor(() => expect(onSucces).toHaveBeenCalled());
    expect(envoyer).toHaveBeenCalledWith({ vehicule_id: 4, pont_id: 2, debut: "2026-11-16T10:30", duree_minutes: 90, motif: "Remplacement des plaquettes avant" });
    expect(screen.getByLabelText(/^pont/i)).toHaveValue("2");
    expect(screen.getByLabelText(/^jour/i)).toHaveValue("2026-11-16");
    expect(screen.getByLabelText(/^motif/i)).toHaveValue("");
  });

  it("rattache le créneau occupé au champ heure", async () => {
    const envoyer = vi.fn().mockRejectedValue(new ApiError(409, "creneau_occupe", "Le Pont 2 est déjà occupé de 9 h 00 à 10 h 30.", {}, { rendez_vous_id: 3 }));
    const { user } = rendre(envoyer);
    await remplir(user, "2026-11-17", "09:30");

    await user.click(screen.getByRole("button", { name: "Enregistrer le rendez-vous" }));

    expect(await screen.findByText("Le Pont 2 est déjà occupé de 9 h 00 à 10 h 30.")).toBeInTheDocument();
    expect(screen.getByLabelText(/^heure/i)).toHaveAttribute("aria-invalid", "true");
  });
});

describe("outils du planning", () => {
  it("compare le créneau saisi à l'heure de Paris", () => {
    const maintenant = new Date("2026-11-16T09:00:00Z");
    expect(estDansLePasse("2026-11-16", "09:59", maintenant)).toBe(true);
    expect(estDansLePasse("2026-11-16", "10:00", maintenant)).toBe(false);
    expect(estDansLePasse("2026-11-15", "23:00", maintenant)).toBe(true);
  });

  it("navigue de jour en jour, changements de mois et d'heure compris", () => {
    expect(decalerJour("2026-10-31", 1)).toBe("2026-11-01");
    expect(decalerJour("2026-10-25", -1)).toBe("2026-10-24");
    expect(decalerJour("2027-01-01", -1)).toBe("2026-12-31");
    expect(formatJour("2026-10-22")).toBe("jeu. 22 oct.");
    expect(formatCreneau("2026-11-16T08:00:00Z", "2026-11-16T09:30:00Z")).toBe("9 h 00 – 10 h 30");
  });

  it("groupe par jour de Paris : 23 h 30 appartient au jour même", () => {
    const groupes = grouperParJour([rdv(1, "2026-11-16T22:30:00Z", "2026-11-16T23:00:00Z"), rdv(2, "2026-11-16T23:30:00Z", "2026-11-17T00:00:00Z")]);
    expect(groupes.map((g) => [g.jour, g.rendezVous.map((r) => r.id)])).toEqual([
      ["2026-11-16", [1]],
      ["2026-11-17", [2]],
    ]);
  });

  it("trouve l'élément suivant sur le même pont", () => {
    const element = (r: RendezVous) => ({ type: "rendez_vous" as const, heure: r.debut, rendez_vous: r, ordre: null, report: false });
    const a = rdv(1, "2026-11-16T07:00:00Z", "2026-11-16T09:30:00Z");
    const b = rdv(2, "2026-11-16T09:30:00Z", "2026-11-16T13:30:00Z");
    const planning: Planning = { jour: "2026-11-16", a_planifier: [], ponts: [{ ...PONTS[0]!, charge_minutes: 390, capacite_minutes: 480, elements: [element(a), element(b)] }] };
    expect(elementSuivant(planning, 1, 1)?.rendez_vous.id).toBe(2);
    expect(elementSuivant(planning, 1, 2)).toBeNull();
    expect(elementSuivant(planning, 2, 1)).toBeNull();
  });

  it("place un OT reporté en tête du pont et propose ensuite le premier créneau du jour", () => {
    // OT du mardi 3 novembre encore sur le Pont 1 le mercredi 4 (minuit à Paris = 23 h 00 UTC).
    const veille = rdv(1, "2026-11-03T08:00:00Z", "2026-11-03T09:00:00Z");
    const matin = rdv(2, "2026-11-04T07:00:00Z", "2026-11-04T08:30:00Z");
    const planning: Planning = {
      jour: "2026-11-04",
      a_planifier: [],
      ponts: [
        {
          ...PONTS[0]!,
          charge_minutes: 330,
          capacite_minutes: 480,
          elements: [
            { type: "ordre", heure: "2026-11-03T23:00:00Z", rendez_vous: veille, ordre: null, report: true },
            { type: "rendez_vous", heure: matin.debut, rendez_vous: matin, ordre: null, report: false },
          ],
        },
      ],
    };
    expect(elementSuivant(planning, 1, 1)?.rendez_vous.id).toBe(2);
    expect(libelleReport(veille)).toBe(`Reporté du mar. 3 nov. (${formatCreneau(veille.debut, veille.fin)})`);
    expect(formatCreneau(veille.debut, veille.fin).replace(/ /g, " ")).toBe("9 h 00 – 10 h 00");
    // La vue tablette lit le planning d'aujourd'hui pour un rendez-vous passé, sinon celui du rendez-vous.
    const mercredi = new Date("2026-11-04T10:00:00Z");
    expect(jourDuPont(veille.debut, mercredi)).toBe("2026-11-04");
    expect(jourDuPont("2026-11-06T08:00:00Z", mercredi)).toBe("2026-11-06");
  });

  it("affiche le jour d'origine d'un OT reporté au lieu de son créneau", () => {
    const veille = rdv(1, "2026-11-03T08:00:00Z", "2026-11-03T09:00:00Z");
    const ordre: OrdreResume = {
      id: 7,
      numero: "OT-2026-007",
      statut: "en_cours",
      prioritaire: false,
      vehicule: veille.vehicule,
      client: veille.client,
      mecanicien: null,
      restitution_prevue: null,
      ouvert_le: "2026-11-03T08:00:00Z",
      cloture_le: null,
      taches_terminees: 1,
      taches_total: 2,
      duree_prevue_minutes: 270,
      en_retard: false,
      rendez_vous: null,
    };
    render(<ElementDuPlanning element={{ type: "ordre", heure: "2026-11-03T23:00:00Z", rendez_vous: veille, ordre, report: true }} />);

    // Testing Library ramène les espaces insécables à des espaces simples.
    expect(screen.getByText("Reporté du mar. 3 nov. (9 h 00 – 10 h 00)")).toBeInTheDocument();
    expect(screen.getByText("OT-2026-007")).toBeInTheDocument();
  });

  it("reconnaît la route de la vue tablette (sans barre latérale)", () => {
    expect(estVueTablette("/ordres/12/tablette")).toBe(true);
    expect(estVueTablette("/ordres/12")).toBe(false);
    expect(estVueTablette("/ordres/nouveau/tablette")).toBe(false);
  });
});
