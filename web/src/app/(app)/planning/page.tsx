import type { Metadata } from "next";
import { Planning } from "@/components/planning/Planning";
import { aujourdHui } from "@/lib/vehicules";

export const metadata: Metadata = { title: "Planning atelier" };

type Recherche = Record<string, string | string[] | undefined>;

// Lecture seule, gérant et mécanicien ; ?jour=AAAA-MM-JJ, aujourd'hui (Paris) par défaut.
export default async function PagePlanning({ searchParams }: { searchParams: Promise<Recherche> }) {
  const { jour } = await searchParams;
  const valide = typeof jour === "string" && /^\d{4}-\d{2}-\d{2}$/.test(jour) && !Number.isNaN(Date.parse(jour));
  return <Planning jour={valide ? jour : aujourdHui()} />;
}
