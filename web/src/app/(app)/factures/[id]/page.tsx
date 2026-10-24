import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { FicheFacture } from "@/components/facturation/FicheFacture";
import { RequireRole } from "@/components/session/RequireRole";

export const metadata: Metadata = { title: "Facture" };

// Page réservée au gérant (l'API répond 403 au mécanicien).
export default async function PageFacture({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const factureId = Number(id);
  if (!Number.isInteger(factureId) || factureId < 1) notFound();
  return (
    <RequireRole roles={["gerant"]}>
      <FicheFacture factureId={factureId} />
    </RequireRole>
  );
}
