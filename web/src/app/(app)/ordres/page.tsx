import type { Metadata } from "next";
import { OrdresListe } from "@/components/ordres/OrdresListe";
import { numeroDePage, texteDeRecherche, type Recherche } from "@/lib/pages";
import { lireStatutOT } from "@/lib/statuts";

export const metadata: Metadata = { title: "Ordres de travail" };

export default async function Ordres({ searchParams }: { searchParams: Promise<Recherche> }) {
  const params = await searchParams;
  const page = numeroDePage(params.page);
  const q = texteDeRecherche(params.q);
  const statut = lireStatutOT(params.statut);
  return <OrdresListe key={`${statut}-${q}-${page}`} page={page} statut={statut} q={q} />;
}
