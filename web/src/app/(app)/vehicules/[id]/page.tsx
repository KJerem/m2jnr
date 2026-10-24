import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { FicheVehicule } from "@/components/vehicules/FicheVehicule";

export const metadata: Metadata = { title: "Fiche véhicule" };

// Lisible par le gérant et le mécanicien ; seule la modification est réservée au gérant.
export default async function PageFicheVehicule({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const vehiculeId = Number(id);
  if (!Number.isInteger(vehiculeId) || vehiculeId < 1) notFound();
  return <FicheVehicule vehiculeId={vehiculeId} />;
}
