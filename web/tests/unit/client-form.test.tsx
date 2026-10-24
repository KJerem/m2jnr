import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ClientForm } from "@/components/clients/ClientForm";
import { ApiError } from "@/lib/api";
import { normaliserTelephone, type Client, type ClientEntree } from "@/lib/clients";
import { formatTelephone, NBSP } from "@/lib/format";

const CLIENT: Client = {
  id: 9,
  nom: "Laurent",
  prenom: "Claire",
  telephone: "0612345678",
  email: null,
  consentement_rappels: false,
  nombre_vehicules: 0,
  cree_le: "2026-11-04T09:00:00Z",
  modifie_le: "2026-11-04T09:00:00Z",
};

function doublon() {
  return new ApiError(409, "doublon_telephone", "Un client avec ce téléphone existe déjà.", {}, { clients: [{ id: 3, nom: "Laurent", prenom: "Marc" }] });
}

async function remplir(nom: string, telephone: string) {
  const user = userEvent.setup({ delay: null });
  if (nom) await user.type(screen.getByLabelText(/^nom/i), nom);
  if (telephone) await user.type(screen.getByLabelText(/téléphone/i), telephone);
  return user;
}

describe("formulaire client", () => {
  it("exige le nom et le téléphone sans appeler l'API", async () => {
    const envoyer = vi.fn();
    render(<ClientForm mode="creation" envoyer={envoyer} onSucces={vi.fn()} />);

    await userEvent.setup({ delay: null }).click(screen.getByRole("button", { name: "Créer le client" }));

    expect(await screen.findAllByText("Champ obligatoire.")).toHaveLength(2);
    expect(screen.getByLabelText(/^nom/i)).toHaveAttribute("aria-invalid", "true");
    expect(envoyer).not.toHaveBeenCalled();
  });

  it("refuse un téléphone qui n'est pas français et un e-mail mal formé", async () => {
    const envoyer = vi.fn();
    render(<ClientForm mode="creation" envoyer={envoyer} onSucces={vi.fn()} />);
    const user = await remplir("Laurent", "12 34");
    await user.type(screen.getByLabelText(/e-mail/i), "claire@");

    await user.click(screen.getByRole("button", { name: "Créer le client" }));

    expect(await screen.findByText("Numéro de téléphone français invalide.")).toBeInTheDocument();
    expect(screen.getByText("Adresse e-mail invalide.")).toBeInTheDocument();
    expect(envoyer).not.toHaveBeenCalled();
  });

  it("laisse la case des rappels décochée par défaut et envoie des valeurs nettoyées", async () => {
    const envoyer = vi.fn<(e: ClientEntree, c: boolean) => Promise<Client>>().mockResolvedValue(CLIENT);
    const onSucces = vi.fn();
    render(<ClientForm mode="creation" envoyer={envoyer} onSucces={onSucces} />);
    expect(screen.getByRole("checkbox", { name: /rappels d'entretien/ })).not.toBeChecked();

    const user = await remplir("  Laurent ", "06 12 34 56 78");
    await user.click(screen.getByRole("button", { name: "Créer le client" }));

    await vi.waitFor(() => expect(onSucces).toHaveBeenCalledWith(CLIENT));
    expect(envoyer).toHaveBeenCalledWith({ nom: "Laurent", prenom: null, telephone: "06 12 34 56 78", email: null, consentement_rappels: false }, false);
  });

  it("rattache les erreurs renvoyées par l'API aux champs", async () => {
    const envoyer = vi.fn().mockRejectedValue(new ApiError(422, "validation", "Certains champs sont invalides.", { email: "Adresse e-mail invalide." }));
    render(<ClientForm mode="creation" envoyer={envoyer} onSucces={vi.fn()} />);
    const user = await remplir("Laurent", "0612345678");
    await user.type(screen.getByLabelText(/e-mail/i), "claire@exemple.zz");

    await user.click(screen.getByRole("button", { name: "Créer le client" }));

    expect(await screen.findByText("Adresse e-mail invalide.")).toBeInTheDocument();
    expect(screen.getByLabelText(/e-mail/i)).toHaveAttribute("aria-invalid", "true");
  });
});

describe("alerte de doublon", () => {
  it("ouvre une fenêtre accessible listant les clients puis renvoie avec confirmation", async () => {
    const envoyer = vi.fn<(e: ClientEntree, c: boolean) => Promise<Client>>().mockRejectedValueOnce(doublon()).mockResolvedValueOnce(CLIENT);
    const onSucces = vi.fn();
    render(<ClientForm mode="creation" envoyer={envoyer} onSucces={onSucces} />);
    const user = await remplir("Laurent", "0612345678");
    await user.click(screen.getByRole("button", { name: "Créer le client" }));

    const dialogue = await screen.findByRole("dialog", { name: "Téléphone déjà enregistré" });
    expect(dialogue).toHaveAttribute("aria-modal", "true");
    expect(dialogue).toHaveFocus();
    expect(within(dialogue).getByRole("link", { name: /Marc Laurent/ })).toHaveAttribute("href", "/clients/3");

    await user.click(within(dialogue).getByRole("button", { name: "Créer quand même" }));

    await vi.waitFor(() => expect(onSucces).toHaveBeenCalledWith(CLIENT));
    expect(envoyer).toHaveBeenLastCalledWith(expect.objectContaining({ telephone: "0612345678" }), true);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("se ferme avec Échap, garde le focus à l'intérieur et le rend au bouton", async () => {
    const envoyer = vi.fn().mockRejectedValue(doublon());
    render(<ClientForm mode="modification" valeursInitiales={{ nom: "Laurent", prenom: "", telephone: "0612345678", email: "", consentement_rappels: false }} envoyer={envoyer} onSucces={vi.fn()} />);
    const user = userEvent.setup({ delay: null });
    const bouton = screen.getByRole("button", { name: "Enregistrer" });
    await user.click(bouton);
    const dialogue = await screen.findByRole("dialog");

    await user.tab();
    expect(within(dialogue).getByRole("link")).toHaveFocus();
    await user.tab();
    await user.tab();
    expect(within(dialogue).getByRole("button", { name: "Enregistrer quand même" })).toHaveFocus();
    await user.tab();
    expect(within(dialogue).getByRole("link")).toHaveFocus();

    await user.keyboard("{Escape}");

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(bouton).toHaveFocus();
    expect(envoyer).toHaveBeenCalledTimes(1);
  });

  it("rend le focus au bouton d'envoi même si le navigateur le lui a retiré pendant l'envoi", async () => {
    // Un navigateur retire le focus d'un bouton désactivé (pendant l'envoi) : il part sur <body>
    // avant l'ouverture de la fenêtre. jsdom ne le fait pas (et ignore blur() sur un élément
    // désactivé) : on le simule.
    const envoyer = vi.fn().mockImplementation(async () => {
      const actif = document.activeElement as HTMLButtonElement;
      expect(actif).toBeDisabled();
      actif.disabled = false;
      actif.blur();
      actif.disabled = true;
      expect(document.activeElement).toBe(document.body);
      throw doublon();
    });
    render(<ClientForm mode="creation" envoyer={envoyer} onSucces={vi.fn()} />);
    const user = await remplir("Laurent", "0612345678");
    const bouton = screen.getByRole("button", { name: "Créer le client" });
    bouton.focus();
    await user.keyboard("{Enter}");
    await screen.findByRole("dialog");
    expect(envoyer).toHaveBeenCalledTimes(1);

    await user.keyboard("{Escape}");

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(bouton).toHaveFocus();
  });
});

describe("téléphone", () => {
  it("normalise comme l'API et s'affiche par paires", () => {
    expect(normaliserTelephone("06.12.34.56.78")).toBe("0612345678");
    expect(normaliserTelephone("+33 6 12 34 56 78")).toBe("0612345678");
    expect(normaliserTelephone("0033612345678")).toBe("0612345678");
    expect(normaliserTelephone("0012345678")).toBeNull();
    expect(formatTelephone("0612345678")).toBe(["06", "12", "34", "56", "78"].join(NBSP));
  });
});
