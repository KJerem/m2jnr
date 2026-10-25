"use client";

import { usePathname } from "next/navigation";
import { useState } from "react";
import { ButtonLink } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { Onglets } from "@/components/ui/Onglets";
import { VehiculesListe } from "@/components/vehicules/VehiculesListe";
import { ClientsListe } from "./ClientsListe";

export type OngletClients = "clients" | "vehicules";

const CHEMINS: Record<OngletClients, string> = { clients: "/clients", vehicules: "/vehicules" };

/**
 * Page « Clients & véhicules » du gérant (story S1.5) : deux onglets, chacun avec son adresse
 * (/clients, /vehicules) et sa recherche, comme « Devis & factures ». L'onglet affiché se
 * déduit de l'adresse ; changer d'onglet met l'adresse à jour sans recharger la page.
 */
export function ClientsVehicules({ onglet, page, q }: { onglet: OngletClients; page: number; q: string }) {
  const chemin = usePathname();
  const actif: OngletClients = chemin === CHEMINS.vehicules ? "vehicules" : chemin === CHEMINS.clients ? "clients" : onglet;

  // Après un changement d'onglet, l'adresse ne porte plus ni page ni recherche.
  const [change, setChange] = useState(false);

  function changer(id: string) {
    setChange(true);
    window.history.replaceState(null, "", CHEMINS[id === "vehicules" ? "vehicules" : "clients"]);
  }

  // Page et recherche ne valent que pour l'onglet ouvert par l'adresse ; l'autre repart de zéro.
  const de = (id: OngletClients) => (id === onglet && !change ? { page, q } : { page: 1, q: "" });

  return (
    <>
      <header className="page-head">
        <div>
          <h1 className="display">Clients &amp; véhicules</h1>
          <p className="caption sub">Fiches clients et véhicules rattachés.</p>
        </div>
        <ButtonLink href="/clients/nouveau" variant="primary">
          <Icon name="plus" />
          Nouveau client
        </ButtonLink>
      </header>
      <Onglets
        label="Clients et véhicules"
        actif={actif}
        onChange={changer}
        onglets={[
          { id: "clients", libelle: "Clients", contenu: <ClientsListe {...de("clients")} /> },
          { id: "vehicules", libelle: "Véhicules", contenu: <VehiculesListe {...de("vehicules")} /> },
        ]}
      />
    </>
  );
}
