import type { Metadata } from "next";
import { DevisFactures } from "@/components/facturation/DevisFactures";
import { RequireRole } from "@/components/session/RequireRole";
import { filtrePaiement } from "@/lib/factures";
import { numeroDePage, texteDeRecherche, type Recherche } from "@/lib/pages";

export const metadata: Metadata = { title: "Devis & factures" };

// Page réservée au gérant (l'API répond 403 au mécanicien) : onglet « Factures ».
export default async function Factures({ searchParams }: { searchParams: Promise<Recherche> }) {
  const params = await searchParams;
  const page = numeroDePage(params.page);
  const paiement = filtrePaiement(params.paiement);
  const q = texteDeRecherche(params.q);
  return (
    <RequireRole roles={["gerant"]}>
      <DevisFactures key={`factures-${paiement}-${q}-${page}`} onglet="factures" page={page} paiement={paiement} q={q} />
    </RequireRole>
  );
}
