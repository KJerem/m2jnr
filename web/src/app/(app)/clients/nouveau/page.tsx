import type { Metadata } from "next";
import { NouveauClient } from "@/components/clients/NouveauClient";
import { RequireRole } from "@/components/session/RequireRole";

export const metadata: Metadata = { title: "Nouveau client" };

export default function PageNouveauClient() {
  return (
    <RequireRole roles={["gerant"]}>
      <NouveauClient />
    </RequireRole>
  );
}
