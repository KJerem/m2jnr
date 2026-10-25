import type { Metadata } from "next";
import { ClientsVehicules } from "@/components/clients/ClientsVehicules";
import { RequireRole } from "@/components/session/RequireRole";
import { numeroDePage, texteDeRecherche, type Recherche } from "@/lib/pages";

export const metadata: Metadata = { title: "Clients & véhicules" };

// Page réservée au gérant (l'API répond 403 au mécanicien) : onglet « Clients ».
export default async function Clients({ searchParams }: { searchParams: Promise<Recherche> }) {
  const params = await searchParams;
  const page = numeroDePage(params.page);
  const q = texteDeRecherche(params.q);
  return (
    <RequireRole roles={["gerant"]}>
      <ClientsVehicules key={`clients-${q}-${page}`} onglet="clients" page={page} q={q} />
    </RequireRole>
  );
}
