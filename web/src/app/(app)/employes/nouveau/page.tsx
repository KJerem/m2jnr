import type { Metadata } from "next";
import { NouvelEmploye } from "@/components/employes/NouvelEmploye";
import { RequireRole } from "@/components/session/RequireRole";

export const metadata: Metadata = { title: "Nouvel employé" };

export default function PageNouvelEmploye() {
  return (
    <RequireRole roles={["gerant"]}>
      <NouvelEmploye />
    </RequireRole>
  );
}
