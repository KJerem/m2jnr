"use client";

import { useState } from "react";
import { Onglets } from "@/components/ui/Onglets";
import { ListeDevis } from "./ListeDevis";
import { ListeFactures } from "./ListeFactures";

export type OngletFacturation = "devis" | "factures";

const CHEMINS: Record<OngletFacturation, string> = { devis: "/devis", factures: "/factures" };

/**
 * Page « Devis & factures » (gérant) : deux onglets, chacun avec son adresse (/devis,
 * /factures). Changer d'onglet met l'adresse à jour sans recharger la page.
 */
export function DevisFactures({ onglet, page }: { onglet: OngletFacturation; page: number }) {
  const [actif, setActif] = useState<OngletFacturation>(onglet);

  function changer(id: string) {
    const suivant: OngletFacturation = id === "factures" ? "factures" : "devis";
    setActif(suivant);
    window.history.replaceState(null, "", CHEMINS[suivant]);
  }

  // La page demandée ne vaut que pour l'onglet ouvert par l'adresse ; l'autre repart de 1.
  const pageDe = (id: OngletFacturation) => (id === onglet ? page : 1);

  return (
    <>
      <header className="page-head">
        <div>
          <h1 className="display">Devis &amp; factures</h1>
          <p className="caption sub">Les devis se rédigent depuis la fiche d&apos;un ordre de travail ; la facture s&apos;établit quand l&apos;intervention est terminée.</p>
        </div>
      </header>
      <Onglets
        label="Devis et factures"
        actif={actif}
        onChange={changer}
        onglets={[
          { id: "devis", libelle: "Devis", contenu: <ListeDevis page={pageDe("devis")} /> },
          { id: "factures", libelle: "Factures", contenu: <ListeFactures page={pageDe("factures")} /> },
        ]}
      />
    </>
  );
}
