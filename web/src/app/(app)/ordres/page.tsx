import type { Metadata } from "next";
import { OrdresListe } from "@/components/ordres/OrdresListe";
import { STATUTS_OT, type StatutOT } from "@/lib/statuts";

export const metadata: Metadata = { title: "Ordres de travail" };

type Recherche = Record<string, string | string[] | undefined>;

export default async function Ordres({ searchParams }: { searchParams: Promise<Recherche> }) {
  const { page, statut } = await searchParams;
  const numero = Math.max(1, Number.parseInt(typeof page === "string" ? page : "1", 10) || 1);
  const filtre = typeof statut === "string" && (STATUTS_OT as string[]).includes(statut) ? (statut as StatutOT) : null;
  return <OrdresListe page={numero} statut={filtre} />;
}
