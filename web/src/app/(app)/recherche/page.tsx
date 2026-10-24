import type { Metadata } from "next";
import { PageRecherche } from "@/components/recherche/PageRecherche";
import { RequireRole } from "@/components/session/RequireRole";
import type { Recherche } from "@/lib/pages";

export const metadata: Metadata = { title: "Recherche" };

// Page réservée au gérant (l'API répond 403 au mécanicien) : /recherche?q=gh482kl.
export default async function PageDeRecherche({ searchParams }: { searchParams: Promise<Recherche> }) {
  const { q } = await searchParams;
  const saisie = typeof q === "string" ? q : (q?.[0] ?? "");
  return (
    <RequireRole roles={["gerant"]}>
      <PageRecherche key={saisie} q={saisie} />
    </RequireRole>
  );
}
