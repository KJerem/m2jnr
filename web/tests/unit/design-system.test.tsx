import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AppShell } from "@/components/layout/AppShell";
import { SESSION_KEY } from "@/components/session/useSession";
import { KpiTile } from "@/components/ui/KpiTile";
import { Pagination } from "@/components/ui/Pagination";
import { Plate } from "@/components/ui/Plate";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { BADGE_OT, statutSuivant } from "@/lib/statuts";

vi.mock("next/navigation", () => ({ usePathname: () => "/clients", useRouter: () => ({ replace: vi.fn() }) }));

describe("StatusBadge", () => {
  it("affiche la pastille et le mot, jamais la couleur seule", () => {
    const { container } = render(<StatusBadge status="en-cours" />);
    expect(screen.getByText("En cours")).toBeInTheDocument();
    expect(container.querySelector(".et-status-en-cours")).not.toBeNull();
    expect(container.querySelector(".et-dot")).toHaveAttribute("aria-hidden", "true");
  });

  it("donne une forme de pastille différente à Urgent (losange) et En attente (anneau)", () => {
    const { container } = render(
      <>
        <StatusBadge status="urgent" />
        <StatusBadge status="attente" />
      </>,
    );
    expect(container.querySelector(".et-status-urgent .et-dot-diamond")).not.toBeNull();
    expect(container.querySelector(".et-status-attente .et-dot-ring")).not.toBeNull();
  });
});

describe("Plate", () => {
  it("expose l'immatriculation aux lecteurs d'écran", () => {
    render(<Plate number="GH-482-KL" />);
    expect(screen.getByRole("img", { name: "Immatriculation GH-482-KL" })).toBeInTheDocument();
  });
});

describe("KpiTile", () => {
  it("affiche libellé, valeur et tendance", () => {
    render(<KpiTile label="Véhicules à l'atelier" value={12} delta="+3 vs hier" trend="good" />);
    expect(screen.getByText("Véhicules à l'atelier")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("+3 vs hier")).toHaveClass("et-kpi-good");
  });
});

describe("statuts d'OT", () => {
  it("associe chaque statut métier à un badge du design system", () => {
    expect(BADGE_OT).toEqual({ a_faire: "attente", en_cours: "en-cours", termine: "pret", livre: "livre" });
  });

  it("n'autorise que l'étape suivante", () => {
    expect(statutSuivant("a_faire")).toBe("en_cours");
    expect(statutSuivant("termine")).toBe("livre");
    expect(statutSuivant("livre")).toBeNull();
  });
});

describe("cibles tactiles de 44 px", () => {
  // « sm » (36 px) est réservé au desktop : ces boutons restent utilisés à 1024 px (tablette).
  it("pagination en taille md", () => {
    render(<Pagination page={2} taille={20} total={60} lien={(p) => `/clients?page=${p}`} libelle="clients" />);
    for (const nom of ["Précédent", "Suivant"]) {
      const bouton = screen.getByRole("link", { name: nom });
      expect(bouton).toHaveClass("et-btn");
      expect(bouton).not.toHaveClass("et-btn-sm");
    }
  });

  it("déconnexion et bascule de thème en taille md", () => {
    vi.stubGlobal("matchMedia", () => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
    const client = new QueryClient();
    client.setQueryData(SESSION_KEY, { utilisateur: { id: 1, email: "nadia@garage.test", prenom: "Nadia", nom: "Benali", nom_affiche: "Nadia Benali", role: "gerant" } });
    render(
      <QueryClientProvider client={client}>
        <AppShell>contenu</AppShell>
      </QueryClientProvider>,
    );
    for (const nom of [/Se déconnecter/, /Passer au thème/]) {
      const bouton = screen.getByRole("button", { name: nom });
      expect(bouton).toHaveClass("et-btn");
      expect(bouton).not.toHaveClass("et-btn-sm");
    }
    vi.unstubAllGlobals();
  });
});
