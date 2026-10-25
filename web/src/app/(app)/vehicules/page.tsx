import type { Metadata } from "next";
import { RequireRole } from "@/components/session/RequireRole";
import { PageVehicules } from "@/components/vehicules/PageVehicules";
import { numeroDePage, texteDeRecherche, type Recherche } from "@/lib/pages";

export const metadata: Metadata = { title: "Véhicules" };

// Gérant (onglet de « Clients & véhicules ») et mécanicien (liste seule) : l'API sert la liste
// aux deux rôles, sans coordonnées du propriétaire.
export default async function Vehicules({ searchParams }: { searchParams: Promise<Recherche> }) {
  const params = await searchParams;
  const page = numeroDePage(params.page);
  const q = texteDeRecherche(params.q);
  return (
    <RequireRole roles={["gerant", "mecanicien"]}>
      <PageVehicules key={`vehicules-${q}-${page}`} page={page} q={q} />
    </RequireRole>
  );
}
