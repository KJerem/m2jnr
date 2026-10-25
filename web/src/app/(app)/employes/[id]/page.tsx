import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { FicheEmploye } from "@/components/employes/FicheEmploye";
import { RequireRole } from "@/components/session/RequireRole";

export const metadata: Metadata = { title: "Fiche employé" };

export default async function PageFicheEmploye({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const employeId = Number(id);
  if (!Number.isInteger(employeId) || employeId < 1) notFound();
  return (
    <RequireRole roles={["gerant"]}>
      <FicheEmploye key={employeId} employeId={employeId} />
    </RequireRole>
  );
}
