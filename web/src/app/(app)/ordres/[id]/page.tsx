import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { FicheOrdre } from "@/components/ordres/FicheOrdre";

export const metadata: Metadata = { title: "Ordre de travail" };

// Lisible par le gérant et le mécanicien ; modification réservée au gérant.
export default async function PageOrdre({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const ordreId = Number(id);
  if (!Number.isInteger(ordreId) || ordreId < 1) notFound();
  return <FicheOrdre ordreId={ordreId} />;
}
