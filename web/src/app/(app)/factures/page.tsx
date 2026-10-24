import type { Metadata } from "next";
import { DevisFactures } from "@/components/facturation/DevisFactures";
import { RequireRole } from "@/components/session/RequireRole";
import { numeroDePage, type Recherche } from "@/lib/pages";

export const metadata: Metadata = { title: "Devis & factures" };

// Page réservée au gérant (l'API répond 403 au mécanicien) : onglet « Factures ».
export default async function Factures({ searchParams }: { searchParams: Promise<Recherche> }) {
  const page = numeroDePage((await searchParams).page);
  return (
    <RequireRole roles={["gerant"]}>
      <DevisFactures key={`factures-${page}`} onglet="factures" page={page} />
    </RequireRole>
  );
}
