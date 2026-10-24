import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { cleDevisOrdre } from "@/components/devis/donnees";
import { DevisOrdre, FormulaireDevis } from "@/components/devis/DevisOrdre";
import { cleOrdre } from "@/components/ordres/donnees";
import { FicheOrdre } from "@/components/ordres/FicheOrdre";
import { ToastProvider } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api";
import {
  calculerTotaux,
  formatQuantite,
  lireQuantite,
  MESSAGE_QUANTITE_DECIMALES,
  MESSAGE_QUANTITE_INVALIDE,
  MESSAGE_QUANTITE_MAX,
  MESSAGE_QUANTITE_POSITIVE,
  totalLigne,
  tva,
  versEntreeDevis,
  versFormulaireDevis,
  type DevisDetail,
  type LigneCalcul,
} from "@/lib/devis";
import { NBSP } from "@/lib/format";
import type { OrdreDetail } from "@/lib/ordres";

const apiFetch = vi.fn();
vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return { ...original, apiFetch: (...args: unknown[]) => apiFetch(...args) };
});
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }) }));

const mo = (q: number, pu: number): LigneCalcul => ({ type: "main_oeuvre", quantiteCentiemes: q, prixUnitaireCentimes: pu });
const piece = (q: number, pu: number): LigneCalcul => ({ type: "piece", quantiteCentiemes: q, prixUnitaireCentimes: pu });

/** Lignes de la maquette « détail d'un OR » (quantités en centièmes). */
const MAQUETTE = [mo(50, 7200), mo(150, 7200), mo(50, 7200), piece(100, 4850), piece(100, 9600), piece(100, 4290), piece(100, 1160)];

const euros = (texte: string) => texte.replace(/ /g, " ").replace(" €", `${NBSP}€`);

describe("calcul du devis : mêmes résultats que l'API", () => {
  it("2 pièces à 40 € + 1 h à 60 € = 140,00 € HT, 28,00 € de TVA, 168,00 € TTC", () => {
    expect(calculerTotaux([piece(200, 4000), mo(100, 6000)])).toEqual({
      main_oeuvre_ht_centimes: 6000,
      pieces_ht_centimes: 8000,
      total_ht_centimes: 14000,
      total_tva_centimes: 2800,
      total_ttc_centimes: 16800,
    });
  });

  it("maquette : 180,00 + 199,00 = 379,00 € HT, 75,80 € de TVA, 454,80 € TTC", () => {
    expect(calculerTotaux(MAQUETTE)).toEqual({
      main_oeuvre_ht_centimes: 18000,
      pieces_ht_centimes: 19900,
      total_ht_centimes: 37900,
      total_tva_centimes: 7580,
      total_ttc_centimes: 45480,
    });
  });

  it.each([
    [50, 7200, 3600], // 0,5 h × 72,00 €
    [125, 999, 1249], // 12,4875 € → 12,49 €
    [33, 1001, 330], // 3,3033 € → 3,30 €
    [50, 1, 1], // 0,005 € : le demi-centime monte
    [150, 1, 2],
    [1, 49, 0],
    [999_999, 10_000_000, 99_999_900_000],
  ])("ligne %i centièmes × %i centimes = %i centimes", (q, pu, attendu) => {
    expect(totalLigne(q, pu)).toBe(attendu);
  });

  it.each([
    [5, 1],
    [12, 2],
    [13, 3],
    [37900, 7580],
  ])("TVA de %i centimes HT = %i centimes", (ht, attendu) => {
    expect(tva(ht, 2000)).toBe(attendu);
  });

  it("additionne les lignes déjà arrondies (3 × 3,30 € = 9,90 € HT)", () => {
    expect(calculerTotaux([piece(33, 1001), piece(33, 1001), piece(33, 1001)]).total_ttc_centimes).toBe(1188);
  });

  it.each([
    ["0,5", 50],
    ["1.50", 150],
    ["1.500", 150],
    [" 2 ", 200],
    ["9999,99", 999_999],
  ])("lit la quantité « %s »", (saisie, centiemes) => {
    expect(lireQuantite(saisie)).toEqual({ ok: true, centiemes });
  });

  it.each([
    ["0", MESSAGE_QUANTITE_POSITIVE],
    ["-1", MESSAGE_QUANTITE_POSITIVE],
    ["1,005", MESSAGE_QUANTITE_DECIMALES],
    ["10000", MESSAGE_QUANTITE_MAX],
    ["deux", MESSAGE_QUANTITE_INVALIDE],
    ["", MESSAGE_QUANTITE_INVALIDE],
  ])("refuse la quantité « %s »", (saisie, message) => {
    expect(lireQuantite(saisie)).toEqual({ ok: false, message });
  });

  it("affiche « 0,5 h » pour la main-d'œuvre et « 1 » pour une pièce", () => {
    expect(formatQuantite("main_oeuvre", "0.50")).toBe(`0,5${NBSP}h`);
    expect(formatQuantite("piece", "1.00")).toBe("1");
  });

  it("envoie la quantité en texte décimal exact et le prix en centimes", () => {
    expect(versEntreeDevis({ lignes: [{ type: "main_oeuvre", reference: " MO-DIAG ", designation: " Diagnostic ", quantite: "0,5", prix: "72" }] })).toEqual({
      lignes: [{ type: "main_oeuvre", reference: "MO-DIAG", designation: "Diagnostic", quantite: "0.50", prix_unitaire_ht_centimes: 7200 }],
    });
  });
});

const DEVIS: DevisDetail = {
  id: 7,
  ordre: { id: 1, numero: "OT-2026-001", statut: "en_cours" },
  statut: "brouillon",
  envoye_le: null,
  decide_le: null,
  decide_par: null,
  lignes: [
    { id: 70, type: "main_oeuvre", reference: "MO-DIAG", designation: "Diagnostic freinage", quantite: "0.50", prix_unitaire_ht_centimes: 7200, total_ht_centimes: 3600, position: 0 },
    { id: 71, type: "piece", reference: "PLQ-308-AV", designation: "Jeu de plaquettes avant", quantite: "1.00", prix_unitaire_ht_centimes: 4850, total_ht_centimes: 4850, position: 1 },
  ],
  taux_tva_bp: 2000,
  totaux: { main_oeuvre_ht_centimes: 3600, pieces_ht_centimes: 4850, total_ht_centimes: 8450, total_tva_centimes: 1690, total_ttc_centimes: 10140 },
  cree_le: "2026-12-01T09:00:00Z",
  modifie_le: "2026-12-01T09:00:00Z",
  facture: null,
};

const ORDRE: OrdreDetail = {
  id: 1,
  numero: "OT-2026-001",
  statut: "en_cours",
  prioritaire: false,
  vehicule: { id: 4, immatriculation: "GH-482-KL", marque: "Peugeot", modele: "308 SW", kilometrage: 84312, vin: null, date_mise_en_circulation: null },
  client: { id: 9, nom: "Laurent", prenom: "Claire", contact: null },
  mecanicien: null,
  restitution_prevue: null,
  ouvert_le: "2026-12-01T07:10:00Z",
  cloture_le: null,
  taches_terminees: 0,
  taches_total: 0,
  duree_prevue_minutes: 0,
  en_retard: false,
  rendez_vous: null,
  demande_client: "Bruit au freinage",
  diagnostic: null,
  kilometrage_entree: null,
  cree_par: { id: 1, nom: "Nadia Benali" },
  taches: [],
  historique: [],
};

type Role = "gerant" | "mecanicien";

function avecRequetes(enfant: ReactNode, role: Role = "gerant", devis: DevisDetail | null | undefined = undefined) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity }, mutations: { retry: false } } });
  client.setQueryData(cleOrdre(ORDRE.id), ORDRE);
  client.setQueryData(["mecaniciens"], []);
  client.setQueryData(["session"], { utilisateur: { id: 1, email: "nadia@garage.test", nom: "Nadia Benali", role } });
  if (devis !== undefined) client.setQueryData(cleDevisOrdre(ORDRE.id), devis);
  return { client, ...render(<QueryClientProvider client={client}><ToastProvider>{enfant}</ToastProvider></QueryClientProvider>) };
}

function totalTtc(): string {
  const bloc = document.querySelector(".devis-totaux");
  return bloc?.querySelector("dd.devis-ttc")?.textContent ?? "";
}

beforeEach(() => {
  apiFetch.mockReset();
});

describe("formulaire du devis", () => {
  it("ajoute une ligne, recalcule les totaux en direct, retire une ligne et enregistre", async () => {
    const user = userEvent.setup({ delay: null });
    const onSucces = vi.fn();
    apiFetch.mockResolvedValue(DEVIS);
    avecRequetes(<FormulaireDevis ordreId={1} devis={null} onAnnuler={vi.fn()} onSucces={onSucces} />);

    // Une première ligne vide est proposée.
    const ligne1 = screen.getByRole("group", { name: "Ligne 1" });
    await user.selectOptions(within(ligne1).getByLabelText("Type"), "main_oeuvre");
    await user.type(within(ligne1).getByLabelText(/Désignation/), "Diagnostic freinage");
    await user.clear(within(ligne1).getByLabelText(/Heures/));
    await user.type(within(ligne1).getByLabelText(/Heures/), "0,5");
    await user.type(within(ligne1).getByLabelText(/PU HT/), "72");
    expect(totalTtc()).toBe(euros("43,20 €"));

    await user.click(screen.getByRole("button", { name: "Ajouter une ligne" }));
    const ligne2 = screen.getByRole("group", { name: "Ligne 2" });
    await user.type(within(ligne2).getByLabelText(/Désignation/), "Jeu de plaquettes avant");
    await user.type(within(ligne2).getByLabelText(/PU HT/), "48,50");
    expect(totalTtc()).toBe(euros("101,40 €"));
    expect(document.querySelector(".devis-totaux")).toHaveAttribute("aria-live", "polite");

    await user.click(screen.getByRole("button", { name: "Retirer la ligne 2" }));
    expect(screen.queryByRole("group", { name: "Ligne 2" })).not.toBeInTheDocument();
    expect(totalTtc()).toBe(euros("43,20 €"));
    expect(screen.getByRole("button", { name: "Ajouter une ligne" })).toHaveFocus();

    await user.click(screen.getByRole("button", { name: "Enregistrer le devis" }));
    await vi.waitFor(() => expect(onSucces).toHaveBeenCalledWith(DEVIS));
    expect(apiFetch).toHaveBeenCalledWith("/ordres/1/devis", {
      method: "POST",
      body: { lignes: [{ type: "main_oeuvre", reference: null, designation: "Diagnostic freinage", quantite: "0.50", prix_unitaire_ht_centimes: 7200 }] },
    });
  });

  it("signale en français une quantité invalide sur son champ, sans appeler l'API", async () => {
    const user = userEvent.setup({ delay: null });
    avecRequetes(<FormulaireDevis ordreId={1} devis={DEVIS} onAnnuler={vi.fn()} onSucces={vi.fn()} />);
    const ligne1 = screen.getByRole("group", { name: "Ligne 1" });
    const heures = within(ligne1).getByLabelText(/Heures/);

    await user.clear(heures);
    await user.type(heures, "0,333");
    await user.click(screen.getByRole("button", { name: "Enregistrer le devis" }));

    expect(await within(ligne1).findByText(MESSAGE_QUANTITE_DECIMALES)).toBeInTheDocument();
    expect(heures).toHaveAttribute("aria-invalid", "true");
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("rattache une erreur de l'API à la ligne concernée et modifie le devis existant", async () => {
    const user = userEvent.setup({ delay: null });
    apiFetch.mockRejectedValue(new ApiError(422, "validation", "Certains champs sont invalides.", { "lignes.1.prix_unitaire_ht_centimes": "Doit être inférieur ou égal à 10000000." }));
    avecRequetes(<FormulaireDevis ordreId={1} devis={DEVIS} onAnnuler={vi.fn()} onSucces={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Enregistrer le devis" }));

    const ligne2 = screen.getByRole("group", { name: "Ligne 2" });
    expect(await within(ligne2).findByText("Doit être inférieur ou égal à 10000000.")).toBeInTheDocument();
    expect(apiFetch).toHaveBeenCalledWith("/devis/7", expect.objectContaining({ method: "PUT" }));
  });

  it("reprend les lignes du devis enregistré dans le formulaire", () => {
    expect(versFormulaireDevis(DEVIS).lignes[0]).toEqual({ type: "main_oeuvre", reference: "MO-DIAG", designation: "Diagnostic freinage", quantite: "0,5", prix: "72,00" });
  });
});

describe("section devis de la fiche d'un OT", () => {
  it("montre au gérant les lignes et les totaux renvoyés par l'API", () => {
    avecRequetes(<DevisOrdre ordre={ORDRE} />, "gerant", DEVIS);

    const tableau = screen.getByRole("table", { name: "Lignes du devis" });
    expect(within(tableau).getAllByRole("columnheader").map((th) => th.textContent)).toEqual(["Référence", "Désignation", "Qté", "PU HT", "Total HT"]);
    expect(within(tableau).getByText(/^0,5\sh$/)).toBeInTheDocument();
    expect(within(tableau).getByText("PLQ-308-AV")).toHaveClass("mono");
    expect(totalTtc()).toBe(euros("101,40 €"));
    expect(screen.getByText(/^TVA 20\s%$/)).toBeInTheDocument();
  });

  it("propose de créer le devis quand l'OT n'en a pas", async () => {
    const user = userEvent.setup({ delay: null });
    avecRequetes(<DevisOrdre ordre={ORDRE} />, "gerant", null);

    expect(screen.getByText("Aucun devis pour cet ordre de travail.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Ajouter une ligne" }));
    expect(screen.getByRole("group", { name: "Ligne 1" })).toBeInTheDocument();
  });

  it("n'existe pas pour le mécanicien, qui ne demande jamais le devis", () => {
    avecRequetes(<FicheOrdre ordreId={ORDRE.id} />, "mecanicien");

    expect(screen.getByRole("heading", { name: "Travaux à réaliser" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /Devis/ })).not.toBeInTheDocument();
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("apparaît sur la fiche du gérant", async () => {
    apiFetch.mockRejectedValue(new ApiError(404, "introuvable", "Aucun devis pour cet ordre de travail."));
    avecRequetes(<FicheOrdre ordreId={ORDRE.id} />, "gerant");

    expect(screen.getByRole("heading", { name: /Devis — pièces/ })).toBeInTheDocument();
    expect(await screen.findByText("Aucun devis pour cet ordre de travail.")).toBeInTheDocument();
    expect(apiFetch).toHaveBeenCalledWith("/ordres/1/devis", expect.anything());
  });
});

describe("focus clavier de la section devis (revue du sprint 3)", () => {
  it("place le focus sur la première ligne à l'ouverture et le rend à « Modifier le devis » après Annuler", async () => {
    const user = userEvent.setup({ delay: null });
    avecRequetes(<DevisOrdre ordre={ORDRE} />, "gerant", DEVIS);

    await user.click(screen.getByRole("button", { name: "Modifier le devis" }));
    expect(within(screen.getByRole("group", { name: "Ligne 1" })).getByLabelText("Type")).toHaveFocus();

    await user.click(screen.getByRole("button", { name: "Annuler" }));
    expect(screen.getByRole("button", { name: "Modifier le devis" })).toHaveFocus();
  });

  it("place le focus sur la ligne ajoutée puis sur « Modifier le devis » après l'enregistrement", async () => {
    const user = userEvent.setup({ delay: null });
    apiFetch.mockResolvedValue(DEVIS);
    avecRequetes(<DevisOrdre ordre={ORDRE} />, "gerant", DEVIS);

    await user.click(screen.getByRole("button", { name: "Ajouter une ligne" }));
    const ligne3 = screen.getByRole("group", { name: "Ligne 3" });
    expect(within(ligne3).getByLabelText("Type")).toHaveFocus();

    await user.click(within(ligne3).getByRole("button", { name: "Retirer la ligne 3" }));
    await user.click(screen.getByRole("button", { name: "Enregistrer le devis" }));

    expect(await screen.findByText(/Devis enregistré/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Modifier le devis" })).toHaveFocus();
  });

  it("sans devis, rend le focus à « Ajouter une ligne » après Annuler", async () => {
    const user = userEvent.setup({ delay: null });
    avecRequetes(<DevisOrdre ordre={ORDRE} />, "gerant", null);

    await user.click(screen.getByRole("button", { name: "Ajouter une ligne" }));
    expect(within(screen.getByRole("group", { name: "Ligne 1" })).getByLabelText("Type")).toHaveFocus();

    await user.click(screen.getByRole("button", { name: "Annuler" }));
    expect(screen.getByRole("button", { name: "Ajouter une ligne" })).toHaveFocus();
  });

  it("après « Générer la facture », place le focus sur « Télécharger le PDF »", async () => {
    const user = userEvent.setup({ delay: null });
    const facture = { id: 3, numero: "F-2026-001", totaux: DEVIS.totaux };
    // Story S4.2 : seul un devis accepté se facture.
    const accepte: DevisDetail = { ...DEVIS, statut: "accepte", envoye_le: "2026-12-01T09:10:00Z", decide_le: "2026-12-01T09:40:00Z" };
    apiFetch.mockImplementation((chemin: string) =>
      Promise.resolve(chemin === "/devis/7/facture" ? facture : { ...accepte, facture: { id: 3, numero: "F-2026-001" } }),
    );
    avecRequetes(<DevisOrdre ordre={{ ...ORDRE, statut: "termine" }} />, "gerant", accepte);

    await user.click(screen.getByRole("button", { name: "Générer la facture" }));
    await user.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Générer la facture" }));

    const pdf = await screen.findByRole("link", { name: "Télécharger le PDF" });
    expect(pdf).toHaveFocus();
    expect(screen.getByText(/Facture F-2026-001 établie/)).toBeInTheDocument();
  });
});

describe("éditeur du devis à 1024 px (revue du sprint 3)", () => {
  it("garde 168 px au moins à la colonne « Type » : « Main-d'œuvre » n'est plus coupé par le chevron", () => {
    // Mesuré dans Chromium à 1024 px : le libellé fait 87 px, la flèche native et les marges
    // du select en prennent environ 70 ; à 140 px, on lisait « Main-d'œuvr ».
    const css = readFileSync(join(process.cwd(), "src/styles/app.css"), "utf8");
    const colonnes = /\.devis-ligne \{[^}]*grid-template-columns:\s*minmax\((\d+)px/.exec(css);
    expect(Number(colonnes?.[1])).toBeGreaterThanOrEqual(168);
  });
});
