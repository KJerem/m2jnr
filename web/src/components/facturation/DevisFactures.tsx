"use client";

import { usePathname } from "next/navigation";
import { Onglets } from "@/components/ui/Onglets";
import { ListeDevis } from "./ListeDevis";
import type { StatutPaiement } from "@/lib/factures";
import { ListeFactures } from "./ListeFactures";

export type OngletFacturation = "devis" | "factures";

const CHEMINS: Record<OngletFacturation, string> = { devis: "/devis", factures: "/factures" };

/**
 * Page « Devis & factures » (gérant) : deux onglets, chacun avec son adresse (/devis,
 * /factures). Changer d'onglet met l'adresse à jour sans recharger la page.
 *
 * L'onglet affiché se déduit de l'adresse (usePathname, que Next.js synchronise avec
 * replaceState) et non d'un état local : revenir sur /devis par le menu, qui réutilise la
 * page déjà affichée, montrait encore l'onglet « Factures » (revue du sprint 3).
 */
export function DevisFactures({ onglet, page, paiement = "toutes" }: { onglet: OngletFacturation; page: number; paiement?: StatutPaiement | "toutes" }) {
  const chemin = usePathname();
  const actif: OngletFacturation = chemin === CHEMINS.factures ? "factures" : chemin === CHEMINS.devis ? "devis" : onglet;

  function changer(id: string) {
    const suivant: OngletFacturation = id === "factures" ? "factures" : "devis";
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
          { id: "factures", libelle: "Factures", contenu: <ListeFactures page={pageDe("factures")} paiement={onglet === "factures" ? paiement : "toutes"} /> },
        ]}
      />
    </>
  );
}
