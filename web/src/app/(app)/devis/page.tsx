import type { Metadata } from "next";
import { DevisFactures } from "@/components/facturation/DevisFactures";
import { RequireRole } from "@/components/session/RequireRole";
import { numeroDePage, texteDeRecherche, type Recherche } from "@/lib/pages";

export const metadata: Metadata = { title: "Devis & factures" };

// Page réservée au gérant (l'API répond 403 au mécanicien) : onglet « Devis ».
export default async function Devis({ searchParams }: { searchParams: Promise<Recherche> }) {
  const params = await searchParams;
  const page = numeroDePage(params.page);
  const q = texteDeRecherche(params.q);
  return (
    <RequireRole roles={["gerant"]}>
      <DevisFactures key={`devis-${q}-${page}`} onglet="devis" page={page} q={q} />
    </RequireRole>
  );
}
