import type { Metadata } from "next";
import { EmployesListe } from "@/components/employes/EmployesListe";
import { RequireRole } from "@/components/session/RequireRole";
import { lireRole, lireStatut } from "@/lib/employes";
import { numeroDePage, texteDeRecherche, type Recherche } from "@/lib/pages";

export const metadata: Metadata = { title: "Employés" };

// Page réservée au gérant (l'API répond 403 au mécanicien sur /utilisateurs).
export default async function Employes({ searchParams }: { searchParams: Promise<Recherche> }) {
  const params = await searchParams;
  const page = numeroDePage(params.page);
  const initial = { q: texteDeRecherche(params.q), role: lireRole(params.role), statut: lireStatut(params.statut), page };
  return (
    <RequireRole roles={["gerant"]}>
      <EmployesListe key={page} initial={initial} />
    </RequireRole>
  );
}
