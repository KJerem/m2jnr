import { usePathname, useSearchParams } from "next/navigation";
import { useState } from "react";
import type { Recherche } from "./pages";

/** Paramètres de l'adresse sous la forme que reçoivent les pages (`searchParams`). */
export function parametresDe(params: URLSearchParams): Recherche {
  const resultat: Recherche = {};
  for (const [cle, valeur] of params.entries()) {
    const deja = resultat[cle];
    resultat[cle] = deja === undefined ? valeur : [...(Array.isArray(deja) ? deja : [deja]), valeur];
  }
  return resultat;
}

const memes = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);

/**
 * Filtres d'une liste (recherche ?q=, statut, page…) lus dans l'adresse et mis à jour sans
 * recharger la page (revue du sprint 5, stories S1.5 et S8.2).
 *
 * L'adresse fait foi : `useSearchParams` suit `replaceState`, le retour arrière, l'avance et
 * les liens du menu. Les filtres reçus du serveur (`defaut`) ne servent que si l'adresse est
 * celle d'une autre liste (onglet voisin de « Clients & véhicules » ou de « Devis &
 * factures »). Après un retour arrière, Next.js réaffiche la page avec les paramètres de son
 * premier rendu (sans ?q=) : la liste lisait ces paramètres périmés et perdait sa recherche.
 *
 * `changer` écrit l'adresse avec `replaceState` ; jusqu'à ce que Next.js la répercute dans
 * `useSearchParams`, les filtres demandés sont gardés en attente, et abandonnés si l'adresse
 * a changé entre-temps par une autre voie (navigation).
 */
export function useFiltresAdresse<T>(chemin: string, defaut: T, lire: (parametres: Recherche) => T, lien: (filtres: T) => string): [T, (suivant: T) => void] {
  const params = useSearchParams();
  const cheminCourant = usePathname();
  const adresse = cheminCourant === chemin ? lire(parametresDe(params)) : defaut;
  const [attente, setAttente] = useState<{ filtres: T; lien: string } | null>(null);

  let filtres = adresse;
  if (attente !== null) {
    const ecrite = typeof window === "undefined" || `${window.location.pathname}${window.location.search}` === attente.lien;
    if (!ecrite || memes(adresse, attente.filtres)) {
      // Adresse répercutée par Next.js, ou changée depuis par une navigation : elle fait foi.
      setAttente(null);
    } else {
      filtres = attente.filtres;
    }
  }

  function changer(suivant: T) {
    const cible = lien(suivant);
    setAttente({ filtres: suivant, lien: cible });
    window.history.replaceState(null, "", cible);
  }

  return [filtres, changer];
}
