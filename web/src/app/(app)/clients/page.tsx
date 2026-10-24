import type { Metadata } from "next";
import { ClientsListe } from "@/components/clients/ClientsListe";
import { RequireRole } from "@/components/session/RequireRole";

export const metadata: Metadata = { title: "Clients" };

type Recherche = Record<string, string | string[] | undefined>;

export default async function Clients({ searchParams }: { searchParams: Promise<Recherche> }) {
  const { page } = await searchParams;
  const numero = Math.max(1, Number.parseInt(typeof page === "string" ? page : "1", 10) || 1);
  return (
    <RequireRole roles={["gerant"]}>
      <ClientsListe page={numero} />
    </RequireRole>
  );
}
