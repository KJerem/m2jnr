import type { Metadata } from "next";
import { PageRendezVous } from "@/components/rendez-vous/PageRendezVous";
import { RequireRole } from "@/components/session/RequireRole";

export const metadata: Metadata = { title: "Rendez-vous" };

export default function RendezVous() {
  return (
    <RequireRole roles={["gerant"]}>
      <PageRendezVous />
    </RequireRole>
  );
}
