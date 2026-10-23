import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { KpiTile } from "@/components/ui/KpiTile";
import { Plate } from "@/components/ui/Plate";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { BADGE_OT, statutSuivant } from "@/lib/statuts";

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
