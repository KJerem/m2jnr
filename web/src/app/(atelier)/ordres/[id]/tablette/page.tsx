import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { VueTablette } from "@/components/atelier/VueTablette";

export const metadata: Metadata = { title: "Vue tablette atelier" };

export default async function PageTablette({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const ordreId = Number(id);
  if (!Number.isInteger(ordreId) || ordreId < 1) notFound();
  return <VueTablette ordreId={ordreId} />;
}
