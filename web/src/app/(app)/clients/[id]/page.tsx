import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { FicheClient } from "@/components/clients/FicheClient";
import { RequireRole } from "@/components/session/RequireRole";

export const metadata: Metadata = { title: "Fiche client" };

export default async function PageFicheClient({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const clientId = Number(id);
  if (!Number.isInteger(clientId) || clientId < 1) notFound();
  return (
    <RequireRole roles={["gerant"]}>
      <FicheClient clientId={clientId} />
    </RequireRole>
  );
}
