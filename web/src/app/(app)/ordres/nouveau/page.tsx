import type { Metadata } from "next";
import { NouvelOrdre } from "@/components/ordres/NouvelOrdre";
import { RequireRole } from "@/components/session/RequireRole";

export const metadata: Metadata = { title: "Nouvel ordre de travail" };

type Recherche = Record<string, string | string[] | undefined>;

export default async function PageNouvelOrdre({ searchParams }: { searchParams: Promise<Recherche> }) {
  const { vehicule_id } = await searchParams;
  const id = Number.parseInt(typeof vehicule_id === "string" ? vehicule_id : "", 10);
  return (
    <RequireRole roles={["gerant"]}>
      <NouvelOrdre vehiculeId={Number.isInteger(id) && id > 0 ? id : null} />
    </RequireRole>
  );
}
